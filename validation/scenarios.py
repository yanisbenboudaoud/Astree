"""Scénarios de validation et de sensibilité (issue #15, diapo 8 de la présentation).

« Changez une hypothèse. Changez un scénario. Changez un profil. Votre solution
reste-t-elle cohérente ? » Chaque scénario rejoue la partie **calculée** du
procès (Pacte, simulation, Greffier, taille maximale) sur les vraies données du
dépôt : il est gratuit, sans appel à Bedrock, et donne toujours le même résultat.
Les garde-fous de l'orchestrateur sont joués avec un faux modèle qui demande
exactement les outils voulus, et les vrais outils.

Usage : ``python -m validation`` réécrit ``docs/validation/resultats_scenarios.md``.
"""

from __future__ import annotations

import copy
import json
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest import mock

import pandas as pd

from pipeline import categories as module_categories
from pipeline import frais, liquidite, macro
from pipeline.calibrage import RESTE, VEND, calibrer, episodes_de_baisse, prochaine_question
from pipeline.chiffres import trier_arguments
from pipeline.donnees import ErreurDonnees
from pipeline.greffier import verifier_pacte
from pipeline.indicateurs import calculer_pire_baisse, calculer_volatilite_annuelle
from pipeline.llm import DemandeOutil, TourOutils
from pipeline.orchestrateur import (
    BUDGET_APPELS,
    RAISON_D_OFFICE,
    RAISON_REFUSEE,
    instruire_dossier,
    outils_du_profil,
)
from pipeline.pacte import charger_pacte
from pipeline.simulation import formater_pourcentage, piece_simulation, poids_apres_decision, valeurs_avant_apres
from pipeline.taille_max import rechercher_taille_max

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PERSONAS = RACINE / "personas"
CHEMIN_RAPPORT = RACINE / "docs" / "validation" / "resultats_scenarios.md"
CHEMIN_GRAPHIQUE = CHEMIN_RAPPORT.with_name("sensibilite_seuil.svg")
EXEMPLE_ROBERT = RACINE / "docs" / "exemples" / "contrat_robert.json"

RAISON = "Mesurer le risque propre du titre demandé"


@dataclass(frozen=True)
class Resultat:
    """Une ligne du tableau de résultats."""

    groupe: str
    scenario: str
    attendu: str
    obtenu: str
    ok: bool | None  # None : scénario en attente d'une autre issue


# --- Outils communs ---------------------------------------------------------------

def profil(identifiant: str) -> dict[str, Any]:
    return charger_pacte(DOSSIER_PERSONAS / f"{identifiant}.json")


def position(ticker: str, taille: float, financement: str = "proportionnel") -> dict[str, Any]:
    return {"type": "position", "ticker": ticker, "taille": taille, "financement": financement}


@dataclass
class Jugement:
    """Partie calculée d'un procès : pire baisse après la décision, contrôles, taille maximale."""

    pire_baisse: float
    controles: dict[str, dict[str, Any]]
    taille_max: float | None

    def statut(self, regle: str) -> str:
        return self.controles[regle]["statut"]

    def violations(self) -> list[str]:
        return [regle for regle, controle in self.controles.items() if controle["statut"] == "violation"]


def juger(un_profil: dict[str, Any], decision: dict[str, Any]) -> Jugement:
    """Simulation, Greffier (outil 5) et taille maximale, sans LLM."""
    portefeuille, regles = un_profil["portefeuille"], un_profil["pacte"]["regles"]
    piece = piece_simulation("P2", portefeuille, decision)
    poids = poids_apres_decision(portefeuille, decision)
    controles = verifier_pacte(regles, poids, piece, "P1")
    return Jugement(
        pire_baisse=piece["valeurs"]["pire_baisse"],
        controles={controle["regle"]: controle for controle in controles},
        taille_max=rechercher_taille_max(portefeuille, decision, regles).taille_max,
    )


def regle(un_profil: dict[str, Any], id_regle: str) -> dict[str, Any]:
    return next(r for r in un_profil["pacte"]["regles"] if r["id"] == id_regle)


def pourcent(valeur: float | None) -> str:
    return "aucune" if valeur is None else formater_pourcentage(valeur).lstrip("+")


def resume(jugement: Jugement) -> str:
    violations = jugement.violations()
    texte = f"violations : {', '.join(violations)}" if violations else "aucune violation"
    return f"{texte} ; pire baisse {pourcent(jugement.pire_baisse)} ; taille max {pourcent(jugement.taille_max)}"


@contextmanager
def categories_modifiees(modifier: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    """Remplace temporairement config/categories.json (le fichier n'est pas modifié)."""
    categories = copy.deepcopy(module_categories.charger_categories())
    modifier(categories)
    module_categories._categories_par_ticker.cache_clear()
    try:
        with mock.patch.object(module_categories, "charger_categories", lambda: categories):
            yield
    finally:
        module_categories._categories_par_ticker.cache_clear()


# --- 1. Même décision, profils différents ------------------------------------------

def scenarios_profils() -> list[Resultat]:
    groupe = "1. Même décision, profils différents"
    tsla = position("TSLA", 0.30)
    robert, amira, mateo = profil("robert"), profil("amira"), profil("mateo")
    resultats = []

    jugement = juger(robert, tsla)
    resultats.append(Resultat(
        groupe, "Profil prudent + 30 % TSLA", "violation de pire_baisse_max (seuil −12 %)",
        resume(jugement), jugement.violations() == ["pire_baisse_max"],
    ))

    jugement = juger(amira, tsla)
    resultats.append(Resultat(
        groupe, "Profil audacieux + 30 % TSLA", "aucune violation (environ −42,6 % pour un seuil de −45 %)",
        resume(jugement), jugement.violations() == [] and -0.45 < jugement.pire_baisse < -0.42,
    ))

    jugement = juger(mateo, tsla)
    resultats.append(Resultat(
        groupe, "Profil ESG + 30 % TSLA", "violation de pire_baisse_max (seuil −20 %)",
        resume(jugement), jugement.violations() == ["pire_baisse_max"],
    ))

    jugement = juger(mateo, mateo["decision_demo"])
    resultats.append(Resultat(
        groupe, "Profil ESG + 10 % XOM", "aucune violation financière ; règle ESG à vérifier (source manquante)",
        f"{resume(jugement)} ; controverses_esg : {jugement.statut('controverses_esg')}",
        jugement.violations() == [] and jugement.statut("controverses_esg") == "a_verifier",
    ))

    jugement = juger(amira, amira["decision_demo"])
    attendues = {"pire_baisse_max", "plafond_crypto", "pas_exclusivement_tech"}
    resultats.append(Resultat(
        groupe, "Profil audacieux + panier crypto-tech (100 % réalloué)",
        "3 violations : pire baisse, crypto et tech + crypto",
        resume(jugement), set(jugement.violations()) == attendues,
    ))
    return resultats


# --- 2. Changer un seuil -------------------------------------------------------------

SEUILS = [-0.10, -0.12, -0.15, -0.20, -0.25, -0.30]


def scenarios_seuil() -> list[Resultat]:
    """Seuil de pire baisse du profil prudent, de −10 % à −30 %, pour 30 % TSLA."""
    groupe = "2. Changer un seuil (profil prudent, 30 % TSLA)"
    resultats, tailles = [], []
    for seuil in SEUILS:
        modifie = copy.deepcopy(profil("robert"))
        regle(modifie, "pire_baisse_max")["seuil"] = seuil
        jugement = juger(modifie, position("TSLA", 0.30))
        attendu = "violation" if jugement.pire_baisse < seuil else "conforme"
        tailles.append(jugement.taille_max)
        resultats.append(Resultat(
            groupe, f"Seuil {pourcent(seuil)}", attendu,
            f"{jugement.statut('pire_baisse_max')} ; taille max {pourcent(jugement.taille_max)}",
            jugement.statut("pire_baisse_max") == attendu,
        ))
    croissantes = all(a <= b for a, b in zip(tailles, tailles[1:]))
    resultats.append(Resultat(
        groupe, "Taille max quand le seuil s'assouplit", "croît (ou reste égale)",
        " → ".join(pourcent(t) for t in tailles), croissantes,
    ))
    return resultats


# --- Graphique : taille maximale selon le seuil ---------------------------------------

# Seuils de pire baisse testés pour le graphique : de −8 % à −30 %, par pas de 1 point.
SEUILS_GRAPHIQUE = [-i / 100 for i in range(8, 31)]
TAILLE_DEMANDEE = 0.30


@lru_cache(maxsize=1)
def sensibilite_seuil() -> tuple[tuple[float, float | None], ...]:
    """Taille maximale compatible pour chaque seuil (profil prudent, 30 % TSLA proportionnel)."""
    points = []
    for seuil in SEUILS_GRAPHIQUE:
        modifie = copy.deepcopy(profil("robert"))
        regle(modifie, "pire_baisse_max")["seuil"] = seuil
        recherche = rechercher_taille_max(modifie["portefeuille"], position("TSLA", TAILLE_DEMANDEE),
                                          modifie["pacte"]["regles"])
        points.append((seuil, recherche.taille_max))
    return tuple(points)


# Couleurs : palette de référence de la méthode de visualisation (une seule série, bleu),
# encres et filets recessifs ; mode sombre propre, pas une inversion automatique.
STYLE_GRAPHIQUE = """
  .fond{fill:#fcfcfb} .encre{fill:#0b0b0b} .encre2{fill:#52514e} .discret{fill:#898781}
  .grille{stroke:#e1e0d9;stroke-width:1} .axe{stroke:#c3c2b7;stroke-width:1}
  .ligne{fill:none;stroke:#2a78d6;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
  .point{fill:#2a78d6;stroke:#fcfcfb;stroke-width:2}
  @media (prefers-color-scheme: dark){
    .fond{fill:#1a1a19} .encre{fill:#f0efec} .encre2{fill:#c3c2b7}
    .grille{stroke:#2c2c2a} .axe{stroke:#383835}
    .ligne{stroke:#3987e5} .point{fill:#3987e5;stroke:#1a1a19}
  }
  text{font-family:system-ui,-apple-system,'Segoe UI',sans-serif}
"""


def _pct(valeur: float) -> str:
    return pourcent(valeur).replace(",0 %", " %")


def graphique_svg(points: tuple[tuple[float, float | None], ...]) -> str:
    """Courbe « taille maximale compatible » selon le seuil de pire baisse, en SVG statique."""
    largeur, hauteur = 640, 380
    gauche, droite, haut, bas = 64, 48, 72, 56
    zone_l, zone_h = largeur - gauche - droite, hauteur - haut - bas
    x_min, x_max, y_max = 0.08, 0.30, TAILLE_DEMANDEE

    def x(seuil: float) -> float:
        return round(gauche + (abs(seuil) - x_min) / (x_max - x_min) * zone_l, 1)

    def y(taille: float) -> float:
        return round(haut + zone_h - taille / y_max * zone_h, 1)

    valides = [(s, t) for s, t in points if t is not None]
    chemin = " ".join(f"{'M' if i == 0 else 'L'}{x(s)},{y(t)}" for i, (s, t) in enumerate(valides))
    prudent = next(((s, t) for s, t in valides if round(s, 2) == -0.12), None)
    lignes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}" width="{largeur}" '
        f'height="{hauteur}" role="img" aria-labelledby="titre desc">',
        '<title id="titre">Taille maximale compatible selon le seuil de pire baisse</title>',
        '<desc id="desc">Profil prudent, décision : 30 % en TSLA, financement proportionnel. Plus le seuil '
        'de pire baisse toléré est bas, plus la position compatible avec le Pacte est grande : '
        + ", ".join(f"{_pct(s)} donne {_pct(t)}" for s, t in valides) + ".</desc>",
        f"<style>{STYLE_GRAPHIQUE}</style>",
        f'<rect class="fond" width="{largeur}" height="{hauteur}"/>',
        f'<text class="encre" x="{gauche}" y="28" font-size="16" font-weight="600">'
        "Taille maximale compatible selon le seuil de pire baisse</text>",
        f'<text class="encre2" x="{gauche}" y="48" font-size="13">'
        "Profil prudent · 30 % en TSLA, financement proportionnel · 2021-11-12 → 2026-11-12</text>",
    ]
    for taille in (0.0, 0.10, 0.20, 0.30):
        lignes.append(f'<line class="{"axe" if taille == 0 else "grille"}" x1="{gauche}" y1="{y(taille)}" '
                      f'x2="{largeur - droite}" y2="{y(taille)}"/>')
        lignes.append(f'<text class="discret" x="{gauche - 8}" y="{y(taille) + 4}" font-size="12" '
                      f'text-anchor="end">{_pct(taille)}</text>')
    for i in range(8, 31, 2):
        lignes.append(f'<text class="discret" x="{x(-i / 100)}" y="{haut + zone_h + 20}" font-size="12" '
                      f'text-anchor="middle">{_pct(-i / 100)}</text>')
    lignes.append(f'<text class="encre2" x="{gauche + zone_l / 2}" y="{hauteur - 10}" font-size="12" '
                  'text-anchor="middle">Seuil de pire baisse toléré par le Pacte (plus à droite = plus tolérant)</text>')
    lignes.append(f'<text class="encre2" x="{largeur - droite}" y="{y(y_max) - 8}" font-size="12" '
                  'text-anchor="end">Taille demandée : 30 %</text>')
    lignes.append(f'<path class="ligne" d="{chemin}"/>')
    if prudent:
        px, py = x(prudent[0]), y(prudent[1])
        lignes.append(f'<circle class="point" cx="{px}" cy="{py}" r="5"/>')
        lignes.append(f'<text class="encre" x="{px + 12}" y="{py + 22}" font-size="12">'
                      f"Seuil du profil prudent ({_pct(prudent[0])}) : {_pct(prudent[1])} au maximum</text>")
    lignes.append("</svg>")
    return "\n".join(lignes) + "\n"


def section_graphique(points: tuple[tuple[float, float | None], ...]) -> list[str]:
    """Le graphique dans le rapport, avec ses valeurs en tableau (lecture sans couleur)."""
    lignes = [
        "", "## Graphique : taille maximale compatible selon le seuil", "",
        f"![Taille maximale compatible selon le seuil de pire baisse]({CHEMIN_GRAPHIQUE.name})", "",
        "Profil prudent, 30 % en TSLA, financement proportionnel. Chaque point est calculé par "
        "`rechercher_taille_max` (#21) avec un seuil de pire baisse différent.", "",
        "<details><summary>Valeurs du graphique</summary>", "",
        "| Seuil de pire baisse | Taille maximale compatible |", "|---|---|",
    ]
    lignes += [f"| {pourcent(s)} | {pourcent(t)} |" for s, t in points]
    lignes += ["", "</details>"]
    return lignes


# --- 3. Changer une hypothèse ---------------------------------------------------------

PLAFONDS_TECH_CRYPTO = [0.50, 0.60, 0.65, 0.75, 0.90]


def scenarios_hypotheses() -> list[Resultat]:
    groupe = "3. Changer une hypothèse"
    resultats = []
    nvda = position("NVDA", 0.30)

    # Plafond « tech + crypto » du profil audacieux (hypothèse de #23 : 75 %).
    for maximum in PLAFONDS_TECH_CRYPTO:
        modifie = copy.deepcopy(profil("amira"))
        regle(modifie, "pas_exclusivement_tech")["max"] = maximum
        jugement = juger(modifie, nvda)
        controle = jugement.controles["pas_exclusivement_tech"]
        attendu = "violation" if maximum < 0.65 else "conforme"  # part tech + crypto après : 65 %
        resultats.append(Resultat(
            groupe, f"Profil audacieux + 30 % NVDA, plafond tech + crypto {pourcent(maximum)}", attendu,
            f"{controle['message']} ; taille max {pourcent(jugement.taille_max)}",
            controle["statut"] == attendu,
        ))

    # Catégories de config/categories.json.
    amira = profil("amira")
    reference = juger(amira, nvda).controles["pas_exclusivement_tech"]["message"]
    with categories_modifiees(lambda c: c["tech"]["ajouts"].remove("QQQ")):
        sans_qqq = juger(amira, nvda).controles["pas_exclusivement_tech"]
    resultats.append(Resultat(
        groupe, "QQQ retiré de la catégorie tech (profil audacieux + 30 % NVDA)",
        "part tech + crypto en baisse de la part de QQQ ; toujours conforme",
        f"avant : {reference} | après : {sans_qqq['message']}", sans_qqq["statut"] == "conforme",
    ))

    tsla = position("TSLA", 0.60)
    avant = juger(amira, tsla).controles["pas_exclusivement_tech"]
    with categories_modifiees(lambda c: c["tech"]["ajouts"].append("TSLA")):
        apres = juger(amira, tsla).controles["pas_exclusivement_tech"]
    resultats.append(Resultat(
        groupe, "TSLA ajouté à la catégorie tech (profil audacieux + 60 % TSLA)",
        "conforme sans TSLA en tech ; violation avec",
        f"avant : {avant['statut']} ({avant['message']}) | après : {apres['statut']} ({apres['message']})",
        avant["statut"] == "conforme" and apres["statut"] == "violation",
    ))
    return resultats


# --- 4. Changer la période -------------------------------------------------------------

def scenarios_periode() -> list[Resultat]:
    """Période complète contre 2022 seule (dernière séance de 2021 → dernière de 2022)."""
    groupe = "4. Changer la période (profil prudent, 30 % TSLA)"
    actuel, apres = valeurs_avant_apres(profil("robert")["portefeuille"], position("TSLA", 0.30))
    resultats = []
    for nom, valeurs in (("actuel", actuel), ("après la décision", apres)):
        annee = valeurs[(valeurs.index >= "2021-12-31") & (valeurs.index <= "2022-12-30")]
        pb_complete, pb_2022 = calculer_pire_baisse(valeurs), calculer_pire_baisse(annee)
        vol_complete, vol_2022 = calculer_volatilite_annuelle(valeurs), calculer_volatilite_annuelle(annee)
        resultats.append(Resultat(
            groupe, f"Portefeuille {nom} : pire baisse",
            "identique : la pire baisse de la période est atteinte en 2022",
            f"période complète {pourcent(pb_complete)} ; 2022 seule {pourcent(pb_2022)}",
            round(pb_complete, 4) == round(pb_2022, 4),
        ))
        resultats.append(Resultat(
            groupe, f"Portefeuille {nom} : volatilité annualisée", "plus élevée en 2022 (année de crise)",
            f"période complète {pourcent(vol_complete)} ; 2022 seule {pourcent(vol_2022)}",
            vol_2022 > vol_complete,
        ))
    return resultats


# --- 5. Robustesse du Greffier -------------------------------------------------------------

def scenarios_greffier() -> list[Resultat]:
    """Un argument du faux contrat, puis des versions fautives injectées (chiffres, puis cadre).

    Chaque argument passe par ``trier_arguments``, comme dans un procès : chiffres
    (``verifier_chiffres``) et cadre « simulation seulement » (``cadre_simulation``, #60).
    """
    groupe = "5. Robustesse du Greffier (verifier_chiffres et cadre_simulation)"
    contrat = json.loads(EXEMPLE_ROBERT.read_text(encoding="utf-8"))
    dossier = {"decision": contrat["decision"], "pieces": contrat["pieces"],
               "periode": ["2021-11-12", "2026-11-12"]}
    cas = [
        ("Argument d'origine", "La pire chute observée passe de −7,8 % à −29,0 %.", ["P1"], True),
        ("Chiffre inventé", "La pire chute observée passe de −7,8 % à −31,0 %.", ["P1"], False),
        ("Arrondi faux", "La pire chute observée passe de −7,8 % à −29,03 %.", ["P1"], False),
        ("Mauvaise pièce citée", "La pire chute observée passe de −7,8 % à −29,0 %.", ["P3"], False),
        ("Signe manquant", "Si 2022 se répétait, le portefeuille ferait 2,6 %.", ["P2"], False),
        ("Nombre dérivé", "La pire chute serait 21 points de plus qu'aujourd'hui.", ["P1"], False),
        ("Conseil personnalisé", "La pire chute passe à −29,0 % : vous devriez vendre TSLA.", ["P1"], False),
        ("Impératif", "Limitez TSLA : la pire chute passe de −7,8 % à −29,0 %.", ["P1"], False),
        ("Promesse", "Le rendement annualisé de +12,0 % va continuer à progresser.", ["P1"], False),
        ("Prévision au futur", "Avec 30 % en TSLA, la pire chute de −29,0 % se répétera.", ["P1"], False),
        ("Promesse niée", "Le rendement annualisé passe à +12,0 %, mais le passé ne prédit pas l'avenir.", ["P1"], True),
        ("Citation du Pacte", "Vous avez écrit : « Préserver mon capital ».", ["P3"], True),
    ]
    resultats = []
    for nom, texte, pieces, doit_passer in cas:
        tri = trier_arguments([{"etiquette": "fait", "texte": texte, "pieces": pieces}], "requisitoire", dossier)
        obtenu = "accepté" if tri.valides else f"rejeté : {tri.rejetes[0]['raison']}"
        resultats.append(Resultat(
            groupe, f"{nom} : « {texte} » ({', '.join(pieces)})", "accepté" if doit_passer else "rejeté",
            obtenu, bool(tri.valides) is doit_passer,
        ))
    return resultats


# --- 6. Garde-fous de l'orchestrateur -------------------------------------------------------

class ModeleScripte:
    """Faux modèle : rejoue des tours écrits à l'avance (aucun appel à Bedrock)."""

    def __init__(self, tours: list[list[DemandeOutil]]):
        self.tours = list(tours)

    def __call__(self, systeme, conversation, outils):
        demandes = self.tours.pop(0) if self.tours else []
        return TourOutils(message_assistant={"role": "assistant", "content": []}, demandes=demandes, texte="")


def demande(numero: int, nom: str, raison: str = RAISON, **entree) -> DemandeOutil:
    return DemandeOutil(id=f"s{numero}", nom=nom, entree={**entree, "raison": raison})


def scenarios_orchestrateur() -> list[Resultat]:
    """Vrais outils du profil prudent, faux modèle qui force chaque situation."""
    groupe = "6. Garde-fous de l'orchestrateur"
    robert = profil("robert")
    decision = {**position("TSLA", 0.30), "libelle": "30 % en TSLA"}

    def instruire(tours):
        return instruire_dossier(decision, robert, premier_numero=2, outils=outils_du_profil(robert),
                                 converser=ModeleScripte(tours))

    tickers = ["TSLA", "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "PG", "XOM"]
    resultat = instruire([[demande(i, "indicateurs_actif", ticker=t)] for i, t in enumerate(tickers)])
    resultats = [Resultat(
        groupe, f"Le modèle demande {len(tickers)} outils", f"{BUDGET_APPELS} appels au maximum",
        f"{resultat.appels} appels exécutés", resultat.appels == BUDGET_APPELS,
    )]

    resultat = instruire([[demande(1, "indicateurs_actif", ticker="TSLA")]])
    office = [e for e in resultat.trace if e["raison"] == RAISON_D_OFFICE]
    resultats.append(Resultat(
        groupe, "Le modèle oublie la simulation de la décision", "simulation ajoutée d'office par Python",
        f"{len(office)} pièce ajoutée d'office ({office[0]['sortie'] if office else 'aucune'})",
        len(office) == 1 and resultat.piece_simulation is not None,
    ))

    resultat = instruire([[demande(1, "verifier_chiffres", texte="…")]])
    refus = resultat.trace[0]
    resultats.append(Resultat(
        groupe, "Le modèle appelle un outil du Greffier", "refusé (hors liste blanche)",
        refus["sortie"], refus["raison"] == RAISON_REFUSEE and "non autorisé" in refus["sortie"],
    ))

    resultat = instruire([[demande(1, "indicateurs_actif", raison="Seuil de 12 % dépassé", ticker="TSLA")]])
    refus = resultat.trace[0]
    resultats.append(Resultat(
        groupe, "Le modèle écrit un chiffre dans sa raison", "refusé (raison sans chiffre)",
        refus["sortie"], refus["raison"] == RAISON_REFUSEE,
    ))
    return resultats


# --- 7. Profil inventé ---------------------------------------------------------------------

PROFIL_INVENTE = {
    "id": "profil_invente",
    "nom": "Profil inventé",
    "etiquette": "fictif",
    "profil_risque": "modere_a_eleve",
    "horizon_ans": [10, None],
    "capital_fictif_cad": 75000,
    "portefeuille": [{"ticker": "SPY", "poids": 0.5}, {"ticker": "XIU.TO", "poids": 0.3},
                     {"ticker": "XBB.TO", "poids": 0.2}],
    "decision_demo": {"type": "position", "ticker": "NVDA", "taille": 0.25, "financement": "depuis_SPY"},
    "pacte": {
        "date_signature": "2026-11-14",
        "regles": [
            {"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.25,
             "libelle": "Pire baisse tolérée : −25 %", "justification": "Hypothèse de test."},
            {"id": "plafond_tech", "type": "plafond", "categories": ["tech"], "max": 0.20,
             "libelle": "Tech : 20 % au maximum", "justification": "Hypothèse de test."},
            {"id": "sans_crypto", "type": "plafond", "categories": ["crypto"], "max": 0.0,
             "libelle": "Crypto exclue", "justification": "Hypothèse de test."},
            {"id": "local", "type": "qualitative", "libelle": "Favoriser le Canada",
             "justification": "Hypothèse de test."},
        ],
    },
}


def scenarios_profil_invente() -> list[Resultat]:
    """Un 4e Pacte, écrit dans un fichier temporaire, jugé sans changer le code."""
    groupe = "7. Profil inventé (4e Pacte, un seul fichier JSON)"
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "profil_invente.json"
        chemin.write_text(json.dumps(PROFIL_INVENTE, ensure_ascii=False), encoding="utf-8")
        invente = charger_pacte(chemin)
    jugement = juger(invente, invente["decision_demo"])
    statuts = {regle_id: controle["statut"] for regle_id, controle in jugement.controles.items()}
    return [Resultat(
        groupe, "25 % NVDA financés depuis SPY", "un contrôle par règle ; plafond tech (20 %) en violation",
        f"{resume(jugement)} ; " + ", ".join(f"{r} : {s}" for r, s in statuts.items()),
        len(statuts) == 4 and statuts["plafond_tech"] == "violation" and statuts["local"] == "a_verifier",
    )]


# --- Exécution et rapport -------------------------------------------------------------------

# --- 9. Le Pacte vécu (#68) ---------------------------------------------------------

LIMITES_VECUES = [0.0, -0.08, -0.12, -0.20, -0.32, -0.60]


def reponses_jusqu_a(un_profil: dict[str, Any], limite: float) -> dict[str, str]:
    """Un utilisateur fictif qui reste tant que la baisse du jour ne dépasse pas ``limite``."""
    episodes, reponses = episodes_de_baisse(un_profil["portefeuille"]), {}
    while (question := prochaine_question(un_profil, reponses, episodes)) is not None:
        if question["type"] == "baisse":
            reponses[question["id"]] = RESTE if question["baisse"] >= limite else VEND
        else:
            reponses[question["id"]] = question["choix"][0]
    return reponses


def scenarios_pacte_vecu() -> list[Resultat]:
    """Le seuil mesuré suit les réponses, et le Greffier juge 30 % TSLA avec ce seuil."""
    groupe = "9. Pacte vécu (profil prudent, 30 % TSLA)"
    resultats = []
    for limite in LIMITES_VECUES:
        reponses = reponses_jusqu_a(profil("robert"), limite)
        mesure = calibrer(profil("robert"), reponses, "2026-11-15", "P2")
        if mesure.seuil is None:
            attendu, obtenu = "seuil du Pacte conservé", f"seuil {pourcent(regle(mesure.profil, 'pire_baisse_max')['seuil'])}"
            ok = regle(mesure.profil, "pire_baisse_max")["seuil"] == regle(profil("robert"), "pire_baisse_max")["seuil"]
        else:
            jugement = juger(mesure.profil, position("TSLA", 0.30))
            statut = "violation" if jugement.pire_baisse < mesure.seuil else "conforme"
            attendu = f"seuil ≥ {pourcent(limite)} ; {statut}"
            obtenu = (f"seuil {pourcent(mesure.seuil)} en {len([q for q in reponses if q.startswith('baisse_')])} "
                      f"questions ; {jugement.statut('pire_baisse_max')}")
            ok = mesure.seuil >= limite and jugement.statut("pire_baisse_max") == statut
        resultats.append(Resultat(groupe, f"Reste jusqu'à {pourcent(limite)}", attendu, obtenu, ok))
    return resultats


# --- 10. Pouvoir d'achat et taux (données macro, #111) ------------------------------------

def scenarios_macro() -> list[Resultat]:
    """Inflation, rendement réel et ratio de Sharpe ajoutés aux pièces de simulation."""
    groupe = "10. Pouvoir d'achat et taux (profil prudent, 30 % TSLA)"
    portefeuille, decision = profil("robert")["portefeuille"], position("TSLA", 0.30)
    rejeu = piece_simulation("P3", portefeuille, decision, periode="2022")["valeurs"]
    complete = piece_simulation("P2", portefeuille, decision)["valeurs"]
    fisher = (1 + rejeu["rendement_2022_actuel"]) / (1 + rejeu["inflation_2022"]) - 1
    resultats = [
        Resultat(groupe, "Rendement réel 2022 du portefeuille actuel (relation de Fisher)",
                 "(1 + rendement) ÷ (1 + inflation) − 1, plus bas que le rendement en dollars",
                 f"{pourcent(rejeu['rendement_2022_actuel'])} en dollars, inflation {pourcent(rejeu['inflation_2022'])}, "
                 f"{pourcent(rejeu['rendement_reel_2022_actuel'])} réel",
                 round(fisher, 6) == rejeu["rendement_reel_2022_actuel"]
                 and rejeu["rendement_reel_2022_actuel"] < rejeu["rendement_2022_actuel"]),
        Resultat(groupe, "Contexte de 2022 : taux directeur de la Banque du Canada",
                 "en hausse sur l'année (début < moyenne < fin)",
                 f"{pourcent(rejeu['taux_directeur_debut_2022'])} → {pourcent(rejeu['taux_directeur_fin_2022'])}, "
                 f"moyenne {pourcent(rejeu['taux_directeur_moyen_2022'])}",
                 rejeu["taux_directeur_debut_2022"] < rejeu["taux_directeur_moyen_2022"] < rejeu["taux_directeur_fin_2022"]),
        Resultat(groupe, "Ratio de Sharpe avant et après la décision",
                 "plus bas après : rendement plus élevé, mais risque beaucoup plus fort",
                 f"{complete['ratio_sharpe_actuel']:.2f} → {complete['ratio_sharpe']:.2f}".replace(".", ","),
                 complete["ratio_sharpe"] < complete["ratio_sharpe_actuel"]),
    ]
    reel_actuel = (1 + complete["rendement_annuel_actuel"]) / (1 + complete["inflation_annuelle"]) - 1
    reel_apres = (1 + complete["rendement_annuel"]) / (1 + complete["inflation_annuelle"]) - 1
    resultats.append(Resultat(
        groupe, "Rendement réel annualisé de la période, avant et après la décision (#113)",
        "(1 + rendement) ÷ (1 + inflation) − 1 pour les deux portefeuilles",
        f"{pourcent(complete['rendement_annuel_actuel'])} → {pourcent(complete['rendement_annuel'])} en dollars ; "
        f"{pourcent(complete['rendement_reel_annuel_actuel'])} → {pourcent(complete['rendement_reel_annuel'])} "
        f"après une inflation de {pourcent(complete['inflation_annuelle'])}/an",
        round(reel_actuel, 6) == complete["rendement_reel_annuel_actuel"]
        and round(reel_apres, 6) == complete["rendement_reel_annuel"],
    ))
    # Un IPC d'octobre 2026 ajouté au fichier : publié fin novembre, après l'extraction (13 novembre).
    series = macro._series()
    ipc = series[macro.SERIE_INFLATION].copy()
    ipc[pd.Timestamp("2026-10-01")] = 0.50
    with mock.patch("pipeline.macro._series", return_value={**series, macro.SERIE_INFLATION: ipc.sort_index()}):
        avec_octobre = piece_simulation("P2", portefeuille, decision)
    resultats.append(Resultat(
        groupe, "IPC présent dans le fichier mais pas encore publié (#113)",
        "ignoré : la mesure s'arrête au dernier mois publié à l'extraction",
        f"inflation {pourcent(avec_octobre['valeurs']['inflation_annuelle'])}/an, IPC jusqu'à "
        f"{'2026-09' if 'à 2026-09' in avec_octobre['traitement'] else 'un mois non publié'}",
        avec_octobre["valeurs"]["inflation_annuelle"] == complete["inflation_annuelle"]
        and "à 2026-09" in avec_octobre["traitement"],
    ))
    with mock.patch("pipeline.macro._series", side_effect=ErreurDonnees("macro_rates.csv absent")):
        sans = piece_simulation("P2", portefeuille, decision)
    resultats.append(Resultat(
        groupe, "Données macro indisponibles (fichier absent du bucket)",
        "la pièce obligatoire reste produite, sans valeurs macro",
        "pièce sans inflation ni ratio de Sharpe" if "inflation_annuelle" not in sans["valeurs"] else "valeurs macro présentes",
        "inflation_annuelle" not in sans["valeurs"] and sans["valeurs"]["pire_baisse"] == complete["pire_baisse"],
    ))
    return resultats


# --- 11. Frais de gestion des FNB (#114) -------------------------------------------------

def scenarios_frais() -> list[Resultat]:
    """Coût annuel des frais des FNB, ajouté à la pièce de simulation sans être déduit."""
    groupe = "11. Frais de gestion des FNB (profil prudent, 30 % TSLA)"
    robert = profil("robert")
    portefeuille, decision = robert["portefeuille"], position("TSLA", 0.30)
    valeurs = piece_simulation("P2", portefeuille, decision, capital=robert["capital_fictif_cad"])["valeurs"]
    a_la_main = sum(ligne["poids"] * (frais.ratio_frais(ligne["ticker"]) or 0) for ligne in portefeuille)
    resultats = [
        Resultat(groupe, "Coût annuel des frais du portefeuille actuel",
                 "moyenne des ratios des FNB pondérée par les poids ; actions sans frais de gestion",
                 f"{formater_pourcentage(valeurs['frais_annuels_actuels'], 3).lstrip('+')} par an, "
                 f"soit {valeurs['frais_annuels_cad_actuels']} $",
                 round(a_la_main, 6) == valeurs["frais_annuels_actuels"]),
        Resultat(groupe, "Coût annuel après la décision",
                 "plus bas : TSLA, action détenue en direct, n'a pas de frais de gestion",
                 f"{valeurs['frais_annuels_cad_actuels']} $ → {valeurs['frais_annuels_cad']} $ par an",
                 valeurs["frais_annuels"] < valeurs["frais_annuels_actuels"]),
    ]
    sans_tlt = {**frais.charger_frais(), "fnb": [f for f in frais.charger_frais()["fnb"] if f["ticker"] != "TLT"]}
    with mock.patch("pipeline.frais.charger_frais", return_value=sans_tlt):
        inconnu = piece_simulation("P2", portefeuille, position("TLT", 0.10), capital=robert["capital_fictif_cad"])["valeurs"]
    resultats.append(Resultat(
        groupe, "FNB absent du relevé des frais (10 % en TLT)",
        "jamais deviné : aucun coût après la décision, le titre est signalé",
        f"frais_inconnus : {', '.join(inconnu.get('frais_inconnus', []))}",
        inconnu.get("frais_inconnus") == ["TLT"] and "frais_annuels" not in inconnu,
    ))
    return resultats


# --- 12. Risque de liquidité (volumes, #117) ---------------------------------------------

def scenarios_liquidite() -> list[Resultat]:
    """Jours de bourse pour revendre chaque ligne, à partir des volumes de prices_daily.csv."""
    groupe = "12. Risque de liquidité (volumes Yahoo Finance)"
    robert = profil("robert")
    piece = liquidite.piece_liquidite("P4", robert["portefeuille"], position("TSLA", 0.30), robert["capital_fictif_cad"])
    v = piece["valeurs"]
    resultats = [
        Resultat(groupe, "Profil prudent, 30 % TSLA : quelle ligne serait la plus longue à revendre ?",
                 "le petit FNB obligataire (ZST.TO), pas TSLA, très échangé",
                 f"{v['titre_le_moins_liquide']} : {f'{v["jours_pour_vendre_max"]:.2f}'.replace('.', ',')} jour, "
                 f"part de {pourcent(v['part_volume_quotidien_ZST.TO'])} des échanges ; TSLA : "
                 f"{f'{v["jours_pour_vendre_TSLA"]:.5f}'.replace('.', ',')} jour",
                 v["titre_le_moins_liquide"] == "ZST.TO" and v["jours_pour_vendre_TSLA"] < v["jours_pour_vendre_max"]),
    ]
    amira = profil("amira")
    btc = liquidite.piece_liquidite("P4", amira["portefeuille"], amira["decision_demo"], amira["capital_fictif_cad"],
                                    ["BTC-USD"])["valeurs"]["valeur_echangee_moyenne_millions_cad_BTC-USD"]
    resultats.append(Resultat(
        groupe, "Volume crypto (Yahoo le donne en dollars, pas en unités)",
        "pas multiplié par le prix : quelques dizaines de milliers de millions $ par jour, pas des milliards de milliards",
        f"BTC-USD : {btc:,.0f} millions $ CAD par jour".replace(",", " "),
        1e3 < btc < 1e6,
    ))
    lignes = liquidite.charger_volumes(["ZST.TO", "XBB.TO"])
    lignes.loc[lignes["ticker"] == "ZST.TO", "volume"] = float("nan")
    with mock.patch("pipeline.liquidite.charger_volumes", return_value=lignes):
        sans = liquidite.piece_liquidite("P4", robert["portefeuille"], None, robert["capital_fictif_cad"],
                                         ["ZST.TO", "XBB.TO"])["valeurs"]
    resultats.append(Resultat(
        groupe, "Titre sans volume (colonne vide)", "signalé comme absent, jamais remplacé par 0",
        f"titres sans volume : {', '.join(sans.get('titres_sans_volume', []))} ; "
        + ("aucune valeur pour ZST.TO" if not any(c.endswith("_ZST.TO") for c in sans) else "des valeurs pour ZST.TO"),
        sans.get("titres_sans_volume") == ["ZST.TO"] and not any(c.endswith("_ZST.TO") for c in sans),
    ))
    return resultats


GROUPES = [
    scenarios_profils,
    scenarios_seuil,
    scenarios_hypotheses,
    scenarios_periode,
    scenarios_greffier,
    scenarios_orchestrateur,
    scenarios_profil_invente,
    scenarios_pacte_vecu,
    scenarios_macro,
    scenarios_frais,
    scenarios_liquidite,
]


def executer_scenarios() -> list[Resultat]:
    return [resultat for groupe in GROUPES for resultat in groupe()]


def rapport_markdown(resultats: list[Resultat]) -> str:
    """Tableau des résultats pour la documentation technique."""
    reussis = sum(1 for r in resultats if r.ok)
    echecs = sum(1 for r in resultats if r.ok is False)
    attente = sum(1 for r in resultats if r.ok is None)
    lignes = [
        "# Résultats des scénarios de validation et de sensibilité",
        "",
        "Fichier généré par `python -m validation` (issue #15) : ne pas le modifier à la main.",
        "Partie calculée du procès (Pacte, simulation, Greffier, taille maximale) sur les données du dépôt,",
        "sans appel à Bedrock ; garde-fous de l'orchestrateur joués avec un faux modèle et les vrais outils.",
        "",
        f"**Bilan : {reussis} réussis, {echecs} en échec, {attente} en attente.**",
    ]
    groupe_courant = None
    for r in resultats:
        if r.groupe != groupe_courant:
            groupe_courant = r.groupe
            lignes += ["", f"## {r.groupe}", "", "| Scénario | Attendu | Obtenu | |", "|---|---|---|---|"]
        symbole = {True: "✅", False: "❌", None: "⏸"}[r.ok]
        lignes.append(f"| {_cellule(r.scenario)} | {_cellule(r.attendu)} | {_cellule(r.obtenu)} | {symbole} |")
    lignes += section_graphique(sensibilite_seuil())
    return "\n".join(lignes) + "\n"


def _cellule(texte: str) -> str:
    return texte.replace("|", "\\|").replace("\n", " ")


def ecrire_rapport(resultats: list[Resultat], chemin: Path = CHEMIN_RAPPORT) -> Path:
    """Écrit le rapport Markdown et, à côté, le graphique SVG qu'il affiche."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(rapport_markdown(resultats), encoding="utf-8")
    chemin.with_name(CHEMIN_GRAPHIQUE.name).write_text(graphique_svg(sensibilite_seuil()), encoding="utf-8")
    return chemin
