"""Données affichées par l'interface Astrée, calculées par les fonctions du pipeline.

Déplacé de ``scripts/build_ui_series.py`` (#86) pour servir à deux endroits :
- le script, qui précalcule ces données pour les profils de ``personas/`` ;
- la Lambda (routes ``/profil`` et ``/table``, #86), qui les calcule pour un profil
  créé par le questionnaire : les écrans Portefeuille, Décision et « Revivez 4 jours »
  lisent alors exactement les mêmes formats.

Rien n'est estimé dans le navigateur : il ne fait que lire ces tables. Aucun LLM.
"""

from __future__ import annotations

import base64
import itertools
from typing import Any

import numpy as np
import pandas as pd

from pipeline.calibrage import (
    LIMITES as LIMITES_CALIBRAGE,
    calibrer,
    episodes_de_baisse,
    question_baisse,
    question_crypto,
    questions_valeurs,
    reponses_demo,
)
from pipeline.categories import TitreHorsUnivers, categories_du_titre
from pipeline.correlations import calculer_matrice_correlations
from pipeline.donnees import charger_donnees, charger_univers
from pipeline.greffier import verifier_pacte
from pipeline.indicateurs import (
    calculer_pire_baisse,
    calculer_rendement_2022,
    calculer_rendement_annualise,
    calculer_volatilite_annuelle,
)
from pipeline.simulation import poids_apres_decision, source_des_prix, valeurs_avant_apres

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


# --- Pacte vécu (#68) ---------------------------------------------------------------


def historique_episode(historique: pd.Series, date_sommet: str, capital: float) -> list[list[Any]]:
    """Valeur en dollars (capital au sommet) une séance sur cinq, jusqu'au jour de l'épisode inclus."""
    echelle = capital / float(historique[date_sommet])
    rangs = sorted(set(range(0, len(historique), 5)) | {historique.index.get_loc(pd.Timestamp(date_sommet)),
                                                        len(historique) - 1})
    return [[historique.index[i].date().isoformat(), round(float(historique.iloc[i] * echelle))] for i in rangs]


def construire_calibrage(profil: dict[str, Any]) -> dict[str, Any]:
    """Tout ce que l'écran « Revivez 4 jours » montre, calculé par pipeline.calibrage.

    Le navigateur ne rejoue que la dichotomie : le seuil qu'il affiche est la baisse
    réelle d'un de ces jours, et le Tribunal le recalcule en Python à partir des réponses.
    """
    capital = profil["capital_fictif_cad"]
    episodes = episodes_de_baisse(profil["portefeuille"])
    demo = None
    if profil.get("calibrage_demo"):
        reponses, date = reponses_demo(profil)
        demo = {"date": date, "reponses": reponses,
                "seuil": calibrer(profil, reponses, date, "P2", etiquette="fictif").seuil}
    return {
        "profil": profil["id"],
        "capital": capital,
        "horizonAns": profil["horizon_ans"],
        "episodes": [{
            **question_baisse(episode, capital),
            "niveau": episode.niveau,
            "anneesRetour": episode.annees_retour,
            "historique": historique_episode(episode.historique, episode.date_sommet, capital),
        } for episode in episodes],
        "crypto": question_crypto(profil["portefeuille"], capital),
        "valeurs": questions_valeurs(profil["pacte"]["regles"]),
        "demo": demo,
        "source": source_des_prix(),
        "limites": LIMITES_CALIBRAGE,
    }



# --- Profil créé par le questionnaire (#86) -------------------------------------------


def groupes_univers() -> dict[str, dict[str, str]]:
    """Le groupe affiché de chaque titre de l'univers (seul champ que ``construire_profil`` lit)."""
    return {ligne["ticker"]: {"groupe": groupe_du_titre(ligne)} for _, ligne in charger_univers().iterrows()}


def semaines_du_profil(profil: dict[str, Any]) -> np.ndarray:
    """Séances hebdomadaires des courbes : le même calendrier que ``calendrier.json`` (séances américaines)."""
    return positions_hebdomadaires(valeurs_actuelles(profil["portefeuille"]).index)


def vues_profil(profil: dict[str, Any]) -> dict[str, Any]:
    """Ce que l'interface lit pour un profil : écran Portefeuille et « Revivez 4 jours »."""
    return {"profil": construire_profil(profil, groupes_univers(), semaines_du_profil(profil)),
            "calibrage": construire_calibrage(profil)}
