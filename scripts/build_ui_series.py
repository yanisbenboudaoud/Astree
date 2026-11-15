"""Données précalculées de l'interface Astrée (spec de l'interface, annexe B).

    .venv\\Scripts\\python -X utf8 scripts\\build_ui_series.py

Lit les mêmes fichiers que le pipeline (``alphaforge_starter/``, ``personas/``,
``config/``, ``donnees_externes/``) et **réutilise ses fonctions de calcul**
(``pipeline.simulation``, ``pipeline.indicateurs``, ``pipeline.greffier``) :
l'interface affiche exactement les chiffres que le Tribunal citerait. Le script
écrit du JSON dans ``frontend/src/data/generated/`` :

- ``calendrier.json`` : séances retenues pour les courbes (une par semaine) ;
- ``univers.json`` : les 31 titres, libellés français, indicateurs en CAD, documents ESG ;
- ``profils/<id>.json`` : portefeuille actuel, indicateurs, courbe de valeur, Pacte ;
- ``decisions/<id>/<ticker>.json`` : une position de 0 à 50 %, par pas de 1 point ;
- ``paniers/<id>.json`` : chaque composition du panier de démonstration, par pas de 5 points.

Rien n'est estimé dans le navigateur : le curseur et le panier lisent ces tables.
"""

from __future__ import annotations

import argparse
import base64
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from pipeline.categories import TitreHorsUnivers, categories_du_titre, charger_categories  # noqa: E402
from pipeline.correlations import calculer_matrice_correlations  # noqa: E402
from pipeline.documents import charger_corpus  # noqa: E402
from pipeline.donnees import charger_donnees, charger_univers, date_extraction  # noqa: E402
from pipeline.greffier import verifier_pacte  # noqa: E402
from pipeline.indicateurs import (  # noqa: E402
    calculer_pire_baisse,
    calculer_rendement_2022,
    calculer_rendement_annualise,
    calculer_temps_recuperation,
    calculer_volatilite_annuelle,
)
from pipeline.pacte import charger_pacte  # noqa: E402
from pipeline.simulation import poids_apres_decision, valeurs_avant_apres  # noqa: E402

DONNEES_FRONT = RACINE / "frontend" / "src" / "data"
SORTIE = DONNEES_FRONT / "generated"
DOSSIER_PERSONAS = RACINE / "personas"

TAILLES = range(0, 51)  # position : 0 à 50 % par pas de 1 point (annexe B, règle 8)
PAS_PANIER = 5  # panier : pas de 5 points (annexe D.4)
DECIMALES = 6  # valeurs brutes, comme les pièces du contrat
ECHELLE_RECUL = 1000  # recul stocké en dixièmes de point : −0,2897 → −290
TYPES_CALCULABLES = ("pire_baisse_max", "plafond")


# --- Calculs élémentaires --------------------------------------------------------


def brut(valeur: float) -> float:
    return round(float(valeur), DECIMALES)


def recul_depuis_sommet(valeurs: pd.Series) -> pd.Series:
    """Recul depuis le sommet : V / max cumulé de V − 1 (annexe B, règle 5)."""
    return valeurs / valeurs.cummax() - 1


def indicateurs(valeurs: pd.Series) -> dict[str, Any]:
    """Les indicateurs de l'annexe B, calculés par les fonctions du pipeline."""
    recul = recul_depuis_sommet(valeurs)
    return {
        "rendement": brut(calculer_rendement_annualise(valeurs)),
        "volatilite": brut(calculer_volatilite_annuelle(valeurs)),
        "chuteMax": brut(calculer_pire_baisse(valeurs)),
        "dateChuteMax": recul.idxmin().date().isoformat(),
        "rejeu2022": brut(calculer_rendement_2022(valeurs)),
    }


def positions_hebdomadaires(index: pd.DatetimeIndex) -> np.ndarray:
    """Position de la dernière séance de chaque semaine (annexe B, règle 7)."""
    iso = index.isocalendar()
    rangs = pd.Series(np.arange(len(index)), index=index)
    return rangs.groupby([iso.year.values, iso.week.values]).last().sort_values().to_numpy()


def encoder_recul(recul: np.ndarray) -> str:
    """Série de reculs hebdomadaires en entiers 16 bits (dixièmes de point), en base64."""
    entiers = np.round(np.asarray(recul) * ECHELLE_RECUL).astype("<i2")
    return base64.b64encode(entiers.tobytes()).decode("ascii")


def seances_sous_limite(recul: pd.Series, seuil: float | None) -> dict[str, Any] | None:
    """Séances où le recul est sous la limite du Pacte (annexe B, règle 9)."""
    if seuil is None:
        return None
    sous = recul[recul < seuil]
    if sous.empty:
        return {"nombre": 0, "du": None, "au": None}
    return {"nombre": int(len(sous)), "du": sous.index[0].date().isoformat(),
            "au": sous.index[-1].date().isoformat()}


# --- Pacte ------------------------------------------------------------------------


def seuil_pire_baisse(regles: list[dict[str, Any]]) -> float | None:
    return next((r["seuil"] for r in regles if r["type"] == "pire_baisse_max"), None)


def part_des_categories(poids: dict[str, float], categories: list[str]) -> float:
    part = 0.0
    for ticker, poids_titre in poids.items():
        try:
            if categories_du_titre(ticker) & set(categories):
                part += poids_titre
        except TitreHorsUnivers:
            pass
    return part


def juger(regles: list[dict[str, Any]], poids: dict[str, float], chute_max: float) -> dict[str, Any]:
    """Statut de chaque règle selon le Greffier du pipeline (``verifier_pacte``), sans pièce documentaire."""
    simulation = {"id": "simulation", "valeurs": {"pire_baisse": chute_max}}
    controles = verifier_pacte(regles, poids, simulation, id_piece_pacte="pacte")
    statuts = {c["regle"]: c["statut"] for c in controles}
    parts = {r["id"]: brut(part_des_categories(poids, r["categories"]))
             for r in regles if r["type"] == "plafond"}
    compatible = all(statuts[r["id"]] == "conforme" for r in regles if r["type"] in TYPES_CALCULABLES)
    return {"statuts": statuts, "parts": parts, "compatible": compatible,
            "messages": {c["regle"]: c["message"] for c in controles}}


# --- Univers ----------------------------------------------------------------------


def groupe_du_titre(ligne: pd.Series) -> str:
    """Groupe affiché dans « Vos positions », déduit de la classe, du secteur et des catégories.

    Règle unique pour tous les profils (aucun nom de profil) : revenu fixe, crypto,
    or, fonds filtré ESG, technologie (catégorie « tech » de config/categories.json),
    puis actions canadiennes ou américaines selon la devise.
    """
    categories = categories_du_titre(ligne["ticker"])
    if ligne["asset_class"] == "etf_bond":
        return "Revenu fixe"
    if "crypto" in categories:
        return "Cryptoactifs"
    if ligne["asset_class"] == "etf_commodity":
        return "Or" if ligne["sector"] == "Gold" else "Matières premières"
    if "ESG" in ligne["sector"]:
        return "Actions filtrées ESG"
    if "tech" in categories:
        return "Technologie"
    return "Actions canadiennes" if ligne["currency"] == "CAD" else "Actions américaines"


def construire_univers(libelles: dict[str, Any]) -> list[dict[str, Any]]:
    univers = charger_univers()
    documents = charger_corpus()["documents"]
    titres = []
    for _, ligne in univers.iterrows():
        ticker = ligne["ticker"]
        prix = charger_donnees([ticker])[ticker]
        recuperation = calculer_temps_recuperation(prix)
        titres.append({
            "ticker": ticker,
            "nom": libelles["noms"].get(ticker, ligne["name"]),
            "nomOriginal": ligne["name"],
            "classe": libelles["classes"].get(ligne["asset_class"], ligne["asset_class"]),
            "classeId": ligne["asset_class"],
            "bourse": libelles["bourses"].get(ligne["market"], ligne["market"]),
            "devise": ligne["currency"],
            "secteur": libelles["secteurs"].get(ligne["sector"], ligne["sector"]),
            "groupe": groupe_du_titre(ligne),
            "categories": sorted(categories_du_titre(ticker)),
            **indicateurs(prix),
            "anneesRecuperation": (brut(recuperation["annees_recuperation"])
                                   if recuperation["annees_recuperation"] is not None else None),
            "documents": [
                {"critere": d["critere"], "valeur": d["valeur"], "valeurAffichee": d["valeur_affichee"],
                 "titre": d["titre"], "source": d["source"], "dateConsultation": d["date_consultation"]}
                for d in documents if d["ticker"] == ticker
            ],
        })
    return titres


# --- Profil -----------------------------------------------------------------------


def valeurs_actuelles(portefeuille: list[dict[str, Any]]) -> pd.Series:
    """Valeurs quotidiennes (départ à 1) du portefeuille actuel, par le simulateur du pipeline."""
    neutre = {"type": "position", "ticker": portefeuille[0]["ticker"], "taille": 0.0,
              "financement": "proportionnel"}
    return valeurs_avant_apres(portefeuille, neutre)[0]


def serie_valeur(valeurs: pd.Series, capital: float, semaines: np.ndarray) -> list[list[Any]]:
    """Courbe de valeur hebdomadaire, dernière valeur = capital fictif, avec le jour exact du creux."""
    echelle = capital / valeurs.iloc[-1]
    rangs = set(semaines.tolist()) | {int(np.argmin(recul_depuis_sommet(valeurs).to_numpy()))}
    return [[valeurs.index[i].date().isoformat(), round(float(valeurs.iloc[i] * echelle))] for i in sorted(rangs)]


def construire_profil(profil: dict[str, Any], univers: dict[str, dict], semaines: np.ndarray) -> dict[str, Any]:
    portefeuille = profil["portefeuille"]
    regles = profil["pacte"]["regles"]
    capital = profil["capital_fictif_cad"]
    valeurs = valeurs_actuelles(portefeuille)
    actuel = indicateurs(valeurs)
    poids = {ligne["ticker"]: ligne["poids"] for ligne in portefeuille}
    jugement = juger(regles, poids, actuel["chuteMax"])
    recul = recul_depuis_sommet(valeurs)
    v_fin = float(valeurs.iloc[-1])

    regles_ui = []
    for regle in regles:
        utilisation = valeur = None
        if regle["type"] == "pire_baisse_max":
            valeur = actuel["chuteMax"]
            utilisation = brut(valeur / regle["seuil"])
        elif regle["type"] == "plafond":
            valeur = jugement["parts"][regle["id"]]
            utilisation = brut(valeur / regle["max"]) if regle["max"] > 0 else None
        regles_ui.append({
            **{cle: regle[cle] for cle in ("id", "type", "libelle", "seuil", "categories", "max", "critere")
               if cle in regle},
            "statut": jugement["statuts"][regle["id"]],
            "message": jugement["messages"][regle["id"]],
            "valeur": valeur,
            "utilisation": utilisation,
        })

    positions = [{
        "ticker": ligne["ticker"],
        "poids": ligne["poids"],
        "valeur": round(ligne["poids"] * capital),
        "groupe": univers[ligne["ticker"]]["groupe"],
    } for ligne in portefeuille]
    poids_groupes: dict[str, float] = {}
    for position in positions:
        poids_groupes[position["groupe"]] = poids_groupes.get(position["groupe"], 0) + position["poids"]
    ordre = sorted(poids_groupes, key=lambda g: -poids_groupes[g])
    positions.sort(key=lambda p: (ordre.index(p["groupe"]), -p["poids"]))

    return {
        "id": profil["id"],
        "nom": profil["nom"],
        "age": profil.get("age"),
        "metier": profil.get("metier"),
        "profilRisque": profil["profil_risque"],
        "horizonAns": profil["horizon_ans"],
        "capital": capital,
        "debut": valeurs.index[0].date().isoformat(),
        "fin": valeurs.index[-1].date().isoformat(),
        "actuel": {
            **actuel,
            "valeurChuteMax": round(float(valeurs[actuel["dateChuteMax"]] * capital / v_fin)),
            "valeurDepart": round(capital / v_fin),
            "gain": round(capital - capital / v_fin),
            "gainPct": brut(v_fin - 1),
            "recul": encoder_recul(recul.to_numpy()[semaines]),
        },
        "serieValeur": serie_valeur(valeurs, capital, semaines),
        "positions": positions,
        "groupes": [{"libelle": g, "poids": brut(poids_groupes[g])} for g in ordre],
        "pacte": {"dateSignature": profil["pacte"]["date_signature"], "regles": regles_ui},
        "decisionDemo": profil.get("decision_demo"),
    }


# --- Tables de décision -------------------------------------------------------------


def entree_decision(portefeuille, decision, regles, semaines) -> dict[str, Any]:
    _, apres = valeurs_avant_apres(portefeuille, decision)
    resultat = indicateurs(apres)
    recul = recul_depuis_sommet(apres)
    jugement = juger(regles, poids_apres_decision(portefeuille, decision), resultat["chuteMax"])
    return {
        **resultat,
        "seances": seances_sous_limite(recul, seuil_pire_baisse(regles)),
        "statuts": jugement["statuts"],
        "parts": jugement["parts"],
        "compatible": jugement["compatible"],
        "recul": encoder_recul(recul.to_numpy()[semaines]),
    }


def max_conforme(entrees: list[dict[str, Any]]) -> int | None:
    """Plus grande taille t telle que toutes les tailles de 0 à t respectent les règles calculables."""
    maximum = None
    for entree in entrees:
        if not entree["compatible"]:
            break
        maximum = entree["taille"]
    return maximum


def table_position(profil: dict[str, Any], ticker: str, semaines: np.ndarray) -> dict[str, Any]:
    portefeuille, regles = profil["portefeuille"], profil["pacte"]["regles"]
    entrees = []
    for taille in TAILLES:
        decision = {"type": "position", "ticker": ticker, "taille": taille / 100, "financement": "proportionnel"}
        entrees.append({"taille": taille, **entree_decision(portefeuille, decision, regles, semaines)})
    return {"profil": profil["id"], "ticker": ticker, "financement": "proportionnel",
            "maxConforme": max_conforme(entrees), "tailles": entrees}


def compositions(nombre_titres: int, total: int):
    """Toutes les répartitions de ``total`` unités sur ``nombre_titres`` titres (zéros permis)."""
    for coupes in itertools.combinations(range(total + nombre_titres - 1), nombre_titres - 1):
        bornes = (-1, *coupes, total + nombre_titres - 1)
        yield tuple(bornes[i + 1] - bornes[i] - 1 for i in range(nombre_titres))


def table_panier(profil: dict[str, Any], candidats: list[str], semaines: np.ndarray) -> dict[str, Any]:
    portefeuille, regles = profil["portefeuille"], profil["pacte"]["regles"]
    unites = 100 // PAS_PANIER
    entrees = {}
    for repartition in compositions(len(candidats), unites):
        panier = [{"ticker": t, "poids": n / unites} for t, n in zip(candidats, repartition) if n]
        decision = {"type": "reallocation", "panier": panier, "part_reallouee": 1.0}
        cle = "-".join(str(n * PAS_PANIER) for n in repartition)
        entrees[cle] = entree_decision(portefeuille, decision, regles, semaines)
    prix = charger_donnees(candidats)
    matrice = calculer_matrice_correlations(prix)
    correlations = [{"a": a, "b": b, "valeur": brut(matrice.loc[a, b])}
                    for a, b in itertools.combinations(candidats, 2)]
    return {"profil": profil["id"], "candidats": candidats, "pas": PAS_PANIER, "partReallouee": 1.0,
            "correlations": correlations, "compositions": entrees}


# --- Écriture -----------------------------------------------------------------------


def ecrire(chemin: Path, contenu: Any, compact: bool = False) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    options = {"separators": (",", ":")} if compact else {"indent": 1}
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, **options) + "\n", encoding="utf-8")


def main(arguments: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parseur.add_argument("--profils", nargs="*", help="identifiants des profils (défaut : tous)")
    options = parseur.parse_args(arguments)

    debut = time.perf_counter()
    libelles = json.loads((DONNEES_FRONT / "libelles.json").read_text(encoding="utf-8"))
    profils_ui = json.loads((DONNEES_FRONT / "profils_ui.json").read_text(encoding="utf-8"))["profils"]
    fichiers = sorted(DOSSIER_PERSONAS.glob("*.json"))
    profils = [charger_pacte(f) for f in fichiers if f.name != "schema_pacte.json"]
    if options.profils:
        profils = [p for p in profils if p["id"] in options.profils]

    univers = construire_univers(libelles)
    par_ticker = {t["ticker"]: t for t in univers}
    reference = valeurs_actuelles(profils[0]["portefeuille"])
    semaines = positions_hebdomadaires(reference.index)
    ecrire(SORTIE / "calendrier.json", {
        "debut": reference.index[0].date().isoformat(),
        "fin": reference.index[-1].date().isoformat(),
        "extraction": date_extraction("prices_daily.csv"),
        "seances": len(reference),
        "semaines": [reference.index[i].date().isoformat() for i in semaines],
        "echelleRecul": ECHELLE_RECUL,
    })
    ecrire(SORTIE / "univers.json", univers)
    ecrire(SORTIE / "categories.json", {nom: definition["libelle"]
                                         for nom, definition in charger_categories().items()})
    print(f"Univers : {len(univers)} titres")

    for profil in profils:
        ecrire(SORTIE / "profils" / f"{profil['id']}.json", construire_profil(profil, par_ticker, semaines))
        mode = profils_ui.get(profil["id"], {}).get("recherche", {}).get("mode")
        if mode is None:
            mode = "panier" if (profil.get("decision_demo") or {}).get("type") == "reallocation" else "position"
        if mode == "panier":
            candidats = profils_ui[profil["id"]]["panierDemo"]
            table = table_panier(profil, candidats, semaines)
            ecrire(SORTIE / "paniers" / f"{profil['id']}.json", table, compact=True)
            print(f"{profil['id']} : {len(table['compositions'])} compositions du panier {candidats}")
        else:
            for ticker in par_ticker:
                ecrire(SORTIE / "decisions" / profil["id"] / f"{ticker}.json",
                       table_position(profil, ticker, semaines), compact=True)
            print(f"{profil['id']} : {len(par_ticker)} titres × {len(TAILLES)} tailles")
    print(f"Terminé en {time.perf_counter() - debut:.0f} s → {SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
