"""Le Pacte vécu (#68) : mesurer la pire baisse tolérée sur de vrais jours de marché.

Les seuils des Pactes sont des hypothèses de l'équipe. Ce module les remplace,
pour la pire baisse, par une **mesure** : l'utilisateur revit de vrais jours de
baisse, en dollars, sans voir la suite, et répond « je reste » ou « je vends ».
Python en tire le seuil ; ses réponses deviennent une pièce de type
``declaree``, que le Procureur et l'Avocat peuvent citer. Aucun LLM.

Méthode (paramètres dans ``config/calibrage.json``) :

1. **Épisodes** : pour chaque niveau de baisse (−5 %, −10 %… −50 %), le premier
   jour où le portefeuille du profil a baissé d'au moins ce niveau depuis un
   sommet ; s'il n'a jamais baissé autant, le premier jour où une série de
   référence l'a fait. L'épisode ne garde les valeurs que **jusqu'à ce jour** :
   rien de la suite n'est montré (pas de biais de l'après-coup).
2. **Dichotomie** : 4 questions au plus départagent les niveaux. Le seuil
   mesuré est la baisse réelle du **dernier jour où l'utilisateur est resté**.
   S'il vend dès le premier niveau, sa limite n'est pas mesurable : le seuil
   du Pacte est conservé, et la pièce le dit.
3. **Questions complémentaires**, déclarées sans changer de règle : la
   **capacité** (le temps qu'il a fallu pour revenir au sommet, comparé à
   l'horizon), un jour de baisse de la **crypto** si le portefeuille en
   contient, et un **arbitrage valeurs contre rendement** pour chaque règle
   ``critere_documentaire``.

Le code ne connaît aucun persona : il lit le portefeuille, le capital,
l'horizon et les règles du profil reçu.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.categories import TitreHorsUnivers, categories_du_titre
from pipeline.donnees import ErreurDonnees, charger_donnees
from pipeline.indicateurs import DECIMALES_VALEURS, JOURS_PAR_AN, calculer_temps_recuperation
from pipeline.simulation import formater_pourcentage, source_des_prix, valeurs_avant_apres
from pipeline.univers import charger_univers

CHEMIN_CONFIG = Path(__file__).resolve().parent.parent / "config" / "calibrage.json"
NOM_OUTIL = "calibrer_pacte"
LIBELLE_PORTEFEUILLE = "Votre portefeuille"
CATEGORIE_CRYPTO = "crypto"
ID_REGLE_AJOUTEE = "pire_baisse_mesuree"  # si le Pacte n'a aucune règle de pire baisse

# Réponses permises, par type de question.
RESTE, VEND = "reste", "vend"
ATTENDRE, PAS_ATTENDRE = "attendre", "pas_attendre"
GARDER, ASSOUPLIR = "garder", "assouplir"
CHOIX = {
    "baisse": (RESTE, VEND),
    "capacite": (ATTENDRE, PAS_ATTENDRE),
    "crypto": (RESTE, VEND),
    "valeurs": (GARDER, ASSOUPLIR),
}

LIMITES = (
    "Une réponse à un épisode passé ne garantit pas le comportement futur : l'effet de "
    "l'expérience simulée est documenté à court terme, pas à long terme (Bradbury, Hens et "
    "Zeisberger, Review of Finance, 2015). Une seule période de données : peu d'épisodes "
    "différents. Les montants supposent le capital au sommet."
)


class ErreurCalibrage(ValueError):
    """Réponses incomplètes ou invalides : le procès n'est pas lancé (aucun appel Bedrock)."""


@dataclass(frozen=True)
class Episode:
    """Un vrai jour de baisse, tel qu'on le montre à l'utilisateur."""

    id: str  # « baisse_10 »
    niveau: float  # niveau visé (−0.10)
    serie: str  # « Votre portefeuille » ou « Nom du titre (TICKER) »
    ticker: str | None  # None pour le portefeuille du profil
    date_sommet: str
    date_jour: str
    baisse: float  # baisse réelle ce jour-là depuis le sommet (≤ niveau)
    annees_retour: float | None  # du sommet au retour au sommet ; None s'il n'est pas revenu
    historique: pd.Series  # valeurs (départ à 1) jusqu'au jour de l'épisode, inclus


@dataclass
class ResultatCalibrage:
    """Ce que le Tribunal reçoit : la pièce, le profil au seuil mesuré, l'étape de trace."""

    piece: dict[str, Any]
    profil: dict[str, Any]
    trace: dict[str, Any]
    seuil: float | None


@lru_cache(maxsize=1)
def charger_config(chemin: Path = CHEMIN_CONFIG) -> dict[str, Any]:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


# --- Épisodes -----------------------------------------------------------------------


def serie_portefeuille(portefeuille: list[dict[str, Any]]) -> pd.Series:
    """Valeurs quotidiennes (départ à 1) du portefeuille actuel, par le simulateur du pipeline."""
    neutre = {"type": "position", "ticker": portefeuille[0]["ticker"], "taille": 0.0,
              "financement": "proportionnel"}
    return valeurs_avant_apres(portefeuille, neutre)[0]


def jour_de_baisse(serie: pd.Series, niveau: float) -> tuple[pd.Timestamp, pd.Timestamp, float] | None:
    """Premier jour où la série a baissé d'au moins ``niveau`` depuis un sommet.

    Returns:
        ``(date du sommet, date du jour, baisse réelle)``, ou None si la série
        n'a jamais baissé autant.
    """
    recul = serie / serie.cummax() - 1
    jours = recul.index[recul <= niveau]
    if jours.empty:
        return None
    jour = jours[0]
    return serie[:jour].idxmax(), jour, float(recul[jour])


def annees_retour_sommet(serie: pd.Series, sommet: pd.Timestamp, jour: pd.Timestamp) -> float | None:
    """Années entre le sommet et le premier retour à ce sommet après le jour de baisse."""
    apres = serie[jour:]
    retours = apres.index[apres >= serie[sommet]]
    return (retours[0] - sommet).days / JOURS_PAR_AN if len(retours) else None


def libelle_titre(ticker: str) -> str:
    nom = next((t["name"] for t in charger_univers() if t["ticker"] == ticker), ticker)
    return f"{nom} ({ticker})"


def episodes_de_baisse(portefeuille: list[dict[str, Any]]) -> list[Episode]:
    """Un épisode par niveau de ``config/calibrage.json``, du moins profond au plus profond.

    Raises:
        ErreurDonnees: aucun jour de marché n'atteint un niveau.
    """
    config = charger_config()
    references = config["series_reference"]
    prix = charger_donnees(references)
    series = [(LIBELLE_PORTEFEUILLE, None, serie_portefeuille(portefeuille))]
    series += [(libelle_titre(t), t, prix[t] / prix[t].iloc[0]) for t in references]

    episodes = []
    for niveau in config["niveaux"]:
        for libelle, ticker, serie in series:
            trouve = jour_de_baisse(serie, niveau)
            if trouve is None:
                continue
            sommet, jour, baisse = trouve
            episodes.append(Episode(
                id=f"baisse_{round(-niveau * 100)}",
                niveau=niveau,
                serie=libelle,
                ticker=ticker,
                date_sommet=sommet.date().isoformat(),
                date_jour=jour.date().isoformat(),
                baisse=round(baisse, DECIMALES_VALEURS),
                annees_retour=_arrondi(annees_retour_sommet(serie, sommet, jour)),
                historique=serie[:jour].copy(),
            ))
            break
        else:
            raise ErreurDonnees(f"Aucun jour de marché ne baisse de {formater_pourcentage(niveau)} : "
                                "ajouter une série plus volatile dans config/calibrage.json")
    return episodes


# --- Dichotomie ---------------------------------------------------------------------


def parcours_dichotomie(nombre: int, reponses_par_rang: dict[int, str]) -> tuple[list[int], int, int, int | None]:
    """Rejoue la dichotomie sur ``nombre`` niveaux avec les réponses connues.

    Returns:
        ``(rangs posés dans l'ordre, dernier rang « reste » ou −1, premier rang
        « vend » ou ``nombre``, prochain rang à poser ou None si c'est fini)``.
    """
    reste, vend, poses = -1, nombre, []
    while vend - reste > 1:
        milieu = (reste + vend) // 2
        reponse = reponses_par_rang.get(milieu)
        if reponse is None:
            return poses, reste, vend, milieu
        poses.append(milieu)
        if reponse == RESTE:
            reste = milieu
        elif reponse == VEND:
            vend = milieu
        else:
            raise ErreurCalibrage(f"Réponse « {reponse} » invalide : « {RESTE} » ou « {VEND} » attendu")
    return poses, reste, vend, None


# --- Questions ----------------------------------------------------------------------


def question_baisse(episode: Episode, capital: float) -> dict[str, Any]:
    return {
        "id": episode.id,
        "type": "baisse",
        "choix": list(CHOIX["baisse"]),
        "serie": episode.serie,
        "date_sommet": episode.date_sommet,
        "date_jour": episode.date_jour,
        "baisse": episode.baisse,
        "valeur_sommet": round(capital),
        "valeur_jour": round(capital * (1 + episode.baisse)),
    }


def episode_de_reference(episodes: list[Episode], reste: int) -> Episode:
    """L'épisode le plus profond où l'utilisateur est resté (le premier s'il n'est resté nulle part)."""
    return episodes[max(reste, 0)]


def question_capacite(episode: Episode, horizon_ans: list) -> dict[str, Any]:
    return {
        "id": "capacite",
        "type": "capacite",
        "choix": list(CHOIX["capacite"]),
        "serie": episode.serie,
        "date_sommet": episode.date_sommet,
        "baisse": episode.baisse,
        "annees_retour": episode.annees_retour,
        "horizon_ans": list(horizon_ans),
    }


def exposition_crypto(portefeuille: list[dict[str, Any]]) -> tuple[str, float] | None:
    """Titre crypto le plus lourd du portefeuille et part totale de la crypto, ou None."""
    lignes = []
    for ligne in portefeuille:
        try:
            if CATEGORIE_CRYPTO in categories_du_titre(ligne["ticker"]):
                lignes.append(ligne)
        except TitreHorsUnivers:
            pass
    if not lignes:
        return None
    principal = max(lignes, key=lambda ligne: ligne["poids"])["ticker"]
    return principal, sum(ligne["poids"] for ligne in lignes)


def question_crypto(portefeuille: list[dict[str, Any]], capital: float) -> dict[str, Any] | None:
    """Le pire jour du titre crypto principal, appliqué à la part crypto du capital."""
    exposition = exposition_crypto(portefeuille)
    if exposition is None:
        return None
    ticker, part = exposition
    serie = charger_donnees([ticker])[ticker]
    recuperation = calculer_temps_recuperation(serie)
    creux = pd.Timestamp(recuperation["date_creux"])
    baisse = round(float(serie[creux] / serie[:creux].max() - 1), DECIMALES_VALEURS)
    montant = capital * part
    return {
        "id": "crypto",
        "type": "crypto",
        "choix": list(CHOIX["crypto"]),
        "serie": libelle_titre(ticker),
        "date_sommet": recuperation["date_sommet"],
        "date_jour": recuperation["date_creux"],
        "baisse": baisse,
        "part": round(part, DECIMALES_VALEURS),
        "valeur_sommet": round(montant),
        "valeur_jour": round(montant * (1 + baisse)),
    }


def questions_valeurs(regles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un arbitrage valeurs contre rendement par règle ``critere_documentaire``."""
    return [{
        "id": f"valeurs_{regle['id']}",
        "type": "valeurs",
        "choix": list(CHOIX["valeurs"]),
        "regle": regle["id"],
        "libelle": regle["libelle"],
    } for regle in regles if regle["type"] == "critere_documentaire"]


def questions_complementaires(profil: dict[str, Any], episodes: list[Episode], reste: int) -> list[dict[str, Any]]:
    """Capacité, crypto (si le portefeuille en contient) et valeurs, dans cet ordre."""
    questions = [question_capacite(episode_de_reference(episodes, reste), profil["horizon_ans"])]
    crypto = question_crypto(profil["portefeuille"], profil["capital_fictif_cad"])
    if crypto:
        questions.append(crypto)
    return questions + questions_valeurs(profil["pacte"]["regles"])


def prochaine_question(profil: dict[str, Any], reponses: dict[str, str],
                       episodes: list[Episode] | None = None) -> dict[str, Any] | None:
    """La question suivante à poser, ou None quand le calibrage est complet."""
    episodes = episodes_de_baisse(profil["portefeuille"]) if episodes is None else episodes
    _, reste, _, prochain = parcours_dichotomie(len(episodes), _par_rang(episodes, reponses))
    if prochain is not None:
        return question_baisse(episodes[prochain], profil["capital_fictif_cad"])
    for question in questions_complementaires(profil, episodes, reste):
        if question["id"] not in reponses:
            return question
    return None


# --- Résultat -----------------------------------------------------------------------


def calibrer(
    profil: dict[str, Any],
    reponses: dict[str, str],
    date_reponses: str,
    id_piece: str,
    etiquette: str = "fait",
) -> ResultatCalibrage:
    """Seuil mesuré, pièce ``declaree`` et profil dont la règle de pire baisse est remplacée.

    Args:
        profil: profil validé par ``charger_pacte``.
        reponses: ``{id de question: réponse}`` (ex. : ``{"baisse_25": "vend"}``).
        date_reponses: date ISO des réponses (horodatage de la pièce).
        id_piece: numéro de la pièce créée (ex. : « P2 »).
        etiquette: ``fait`` pour de vraies réponses, ``fictif`` pour les réponses
            préenregistrées d'un profil de test.

    Raises:
        ErreurCalibrage: réponse manquante, invalide, ou à une question non posée.
    """
    episodes = episodes_de_baisse(profil["portefeuille"])
    poses, reste, vend, prochain = parcours_dichotomie(len(episodes), _par_rang(episodes, reponses))
    complementaires = questions_complementaires(profil, episodes, reste)
    if prochain is not None:
        raise ErreurCalibrage(f"Calibrage incomplet : réponse attendue à « {episodes[prochain].id} »")
    manquantes = [q["id"] for q in complementaires if q["id"] not in reponses]
    if manquantes:
        raise ErreurCalibrage(f"Calibrage incomplet : réponse attendue à « {manquantes[0]} »")
    ordre = [episodes[rang].id for rang in poses] + [q["id"] for q in complementaires]
    non_posees = sorted(set(reponses) - set(ordre))
    if non_posees:
        raise ErreurCalibrage(f"Réponse à une question non posée : « {non_posees[0]} »")
    for question in complementaires:
        if reponses[question["id"]] not in question["choix"]:
            raise ErreurCalibrage(f"Réponse « {reponses[question['id']]} » invalide pour « {question['id']} » : "
                                  f"{' ou '.join(question['choix'])} attendu")

    seuil = episodes[reste].baisse if reste >= 0 else None
    refusee = episodes[vend].baisse if vend < len(episodes) else None
    piece = _piece(profil, episodes, poses, reponses, complementaires, seuil, refusee,
                   date_reponses, id_piece, etiquette)
    trace = {"etape": "calibrage", "outil": NOM_OUTIL,
             "entree": {"questions": ordre, "reponses": [reponses[i] for i in ordre]},
             "sortie": id_piece}
    profil_calibre = appliquer_seuil(profil, seuil, date_reponses, id_piece, etiquette)
    return ResultatCalibrage(piece, profil_calibre, trace, seuil)


def appliquer_seuil(profil: dict[str, Any], seuil: float | None, date_reponses: str,
                    id_piece: str, etiquette: str) -> dict[str, Any]:
    """Copie du profil où la règle de pire baisse porte le seuil mesuré et sa provenance.

    Sans seuil mesurable, le profil est renvoyé tel quel (copie).
    """
    profil = copy.deepcopy(profil)
    if seuil is None:
        return profil
    regles = profil["pacte"]["regles"]
    regle = next((r for r in regles if r["type"] == "pire_baisse_max"), None)
    if regle is None:
        regle = {"id": ID_REGLE_AJOUTEE, "type": "pire_baisse_max"}
        regles.insert(0, regle)
    regle.update({
        "seuil": seuil,
        "libelle": f"Pire baisse tolérée : {formater_pourcentage(seuil)} (mesurée)",
        "justification": "Baisse réelle du dernier jour de marché où l'utilisateur a choisi de rester",
        "provenance": f"Mesurée sur vos réponses du {date_reponses} à de vrais jours de marché",
        "etiquette": etiquette,
        "piece": id_piece,
    })
    return profil


def reponses_demo(profil: dict[str, Any]) -> tuple[dict[str, str], str]:
    """Réponses préenregistrées d'un profil de test (``calibrage_demo``), et leur date.

    Le profil de test répond « je reste » tant que la baisse ne dépasse pas sa
    limite fictive ``reste_jusqu_a`` ; les autres réponses sont lues telles quelles.

    Raises:
        ErreurCalibrage: le profil n'a pas de ``calibrage_demo``.
    """
    demo = profil.get("calibrage_demo")
    if not demo:
        raise ErreurCalibrage(f"Le profil « {profil['id']} » n'a pas de réponses préenregistrées (calibrage_demo)")
    episodes = episodes_de_baisse(profil["portefeuille"])
    reponses: dict[str, str] = {}
    while (question := prochaine_question(profil, reponses, episodes)) is not None:
        if question["type"] == "baisse":
            reponses[question["id"]] = RESTE if question["baisse"] >= demo["reste_jusqu_a"] else VEND
        else:
            reponses[question["id"]] = demo[question["type"]]
    return reponses, demo["date"]


def _par_rang(episodes: list[Episode], reponses: dict[str, str]) -> dict[int, str]:
    return {rang: reponses[e.id] for rang, e in enumerate(episodes) if e.id in reponses}


def _arrondi(valeur: float | None) -> float | None:
    return None if valeur is None else round(valeur, DECIMALES_VALEURS)


def _piece(profil, episodes, poses, reponses, complementaires, seuil, refusee,
           date_reponses, id_piece, etiquette) -> dict[str, Any]:
    capital = profil["capital_fictif_cad"]
    jours = [episodes[rang] for rang in poses]
    valeurs: dict[str, Any] = {
        "date_reponses": date_reponses,
        "capital": capital,
        "dates_sommets": [e.date_sommet for e in jours],
        "dates_jours": [e.date_jour for e in jours],
        "series_jours": [e.serie for e in jours],
        "baisses_jours": [e.baisse for e in jours],
        "valeurs_jours": [round(capital * (1 + e.baisse)) for e in jours],
        "reponses_jours": [reponses[e.id] for e in jours],
        "seuil_mesure": seuil,
        "baisse_refusee": refusee,
    }
    for question in complementaires:
        reponse = reponses[question["id"]]
        if question["type"] == "capacite":
            valeurs.update({"horizon_ans": question["horizon_ans"],
                            "capacite_annees_retour": question["annees_retour"],
                            "capacite_reponse": reponse})
        elif question["type"] == "crypto":
            valeurs.update({"crypto_date_jour": question["date_jour"], "crypto_baisse": question["baisse"],
                            "crypto_valeur_sommet": question["valeur_sommet"],
                            "crypto_valeur_jour": question["valeur_jour"], "crypto_reponse": reponse})
        else:
            valeurs.setdefault("valeurs_regles", []).append(question["regle"])
            valeurs.setdefault("valeurs_reponses", []).append(reponse)

    if seuil is None:
        affichage = f"Vend dès {formater_pourcentage(refusee)} : limite non mesurable, seuil du Pacte conservé"
    elif refusee is None:
        affichage = f"Reste jusqu'à {formater_pourcentage(seuil)} · seuil mesuré {formater_pourcentage(seuil)}"
    else:
        affichage = (f"Reste à {formater_pourcentage(seuil)} · vend à {formater_pourcentage(refusee)} "
                     f"· seuil mesuré {formater_pourcentage(seuil)}")
    provenance = "réponses préenregistrées d'un profil fictif" if etiquette == "fictif" else "vos réponses"
    return {
        "id": id_piece,
        "type": "declaree",
        "etiquette": etiquette,
        "titre": f"Pacte vécu : {len(jours)} jours de marché revécus",
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": affichage,
        "source": f"{provenance.capitalize()} du {date_reponses} ; jours réels de marché : {source_des_prix()}",
        "traitement": "Chaque jour est le premier où la série a baissé d'au moins un niveau (−5 % à −50 %) "
                      "depuis un sommet ; rien après ce jour n'est montré. Questions par dichotomie ; le seuil "
                      "est la baisse réelle du dernier jour où l'utilisateur est resté.",
        "limites": LIMITES,
    }
