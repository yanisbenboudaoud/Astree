"""Chargement et validation des Pactes (CLAUDE.md, section 3).

Un fichier ``personas/<id>.json`` décrit un profil et son Pacte. Le reste du code
ne lit jamais un nom de persona : il lit les règles renvoyées par ``charger_pacte``.

Deux niveaux de validation, comme pour le contrat de sortie :
1. le schéma JSON (``personas/schema_pacte.json``) : champs, types, paramètres
   de chaque type de règle ;
2. la cohérence, que le schéma ne peut pas exprimer : id de règles uniques,
   catégories connues, poids qui totalisent 1, tickers sans doublon, etc.

Un Pacte invalide lève ``PacteInvalide`` avec la liste de toutes ses erreurs.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from contrat.valider import CONTROLES_SYSTEME
from pipeline.categories import noms_categories
from pipeline.poches import a_des_poches, ecarts_portefeuille_global, regles_de_la_poche

DOSSIER_PERSONAS = Path(__file__).resolve().parent.parent / "personas"
CHEMIN_SCHEMA = DOSSIER_PERSONAS / "schema_pacte.json"
TOLERANCE_SOMME_POIDS = 1e-6

# Clés de la pièce « Pacte » qui ne sont pas des règles : un id de règle ne peut
# pas les reprendre, pas plus que les contrôles du système (controles[].regle).
CLES_PIECE_PACTE = {"date_signature", "horizon_ans", "part_poche"}
IDS_REGLES_RESERVES = CLES_PIECE_PACTE | CONTROLES_SYSTEME

# Paramètre chiffré de chaque type de règle, repris dans la pièce « Pacte ».
PARAMETRE_CHIFFRE = {"pire_baisse_max": "seuil", "plafond": "max"}

MOIS_ABREGES = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]
VOYELLES = set("aeiouyàâäéèêëîïôöùûü")


class PacteInvalide(Exception):
    """Fichier profil refusé. ``erreurs`` contient un message par problème trouvé."""

    def __init__(self, chemin: Path, erreurs: list[str]):
        self.chemin = chemin
        self.erreurs = erreurs
        lignes = "\n".join(f"- {erreur}" for erreur in erreurs)
        super().__init__(f"Pacte invalide ({chemin}) :\n{lignes}")


# --- Chargement --------------------------------------------------------------

def charger_pacte(chemin: str | Path) -> dict:
    """Lit et valide un fichier profil ; renvoie le profil complet (avec son Pacte).

    Lève ``PacteInvalide`` si le fichier ne respecte pas le format commun.
    """
    chemin = Path(chemin)
    with open(chemin, encoding="utf-8") as fichier:
        try:
            profil = json.load(fichier)
        except json.JSONDecodeError as erreur:
            raise PacteInvalide(chemin, [f"JSON illisible : {erreur}"]) from erreur

    erreurs = erreurs_profil(profil, nom_fichier=chemin.stem)
    if erreurs:
        raise PacteInvalide(chemin, erreurs)
    return profil


def erreurs_profil(profil: dict, nom_fichier: str | None = None) -> list[str]:
    """Toutes les erreurs du profil (liste vide s'il est valide).

    La cohérence n'est vérifiée que si le schéma passe, car elle suppose que
    les champs existent et ont le bon type.
    """
    erreurs = erreurs_schema(profil)
    if erreurs:
        return erreurs
    return erreurs_coherence(profil, nom_fichier)


# --- Niveau 1 : schéma JSON --------------------------------------------------

@lru_cache(maxsize=1)
def _validateur() -> Draft202012Validator:
    with open(CHEMIN_SCHEMA, encoding="utf-8") as fichier:
        return Draft202012Validator(json.load(fichier))


def erreurs_schema(profil: dict) -> list[str]:
    """Erreurs du schéma JSON, sous la forme « emplacement : message »."""
    erreurs = sorted(_validateur().iter_errors(profil), key=lambda e: list(e.absolute_path))
    return [f"{_emplacement(profil, list(e.absolute_path))} : {_message_schema(e)}" for e in erreurs]


def _emplacement(profil: dict, chemin: list) -> str:
    """Chemin de l'erreur, complété par l'id de la règle quand il est connu."""
    texte = "/".join(str(partie) for partie in chemin) or "(racine)"
    regle = None
    if len(chemin) >= 3 and chemin[:2] == ["pacte", "regles"]:
        regle = profil["pacte"]["regles"][chemin[2]]
    elif len(chemin) >= 4 and chemin[0] == "poches" and chemin[2] == "regles":  # règle d'une poche (#115)
        regle = profil["poches"][chemin[1]]["regles"][chemin[3]]
    if isinstance(regle, dict) and isinstance(regle.get("id"), str):
        texte += f" (règle « {regle['id']} »)"
    return texte


def _message_schema(erreur) -> str:
    """Message en français pour les erreurs les plus courantes, sinon celui de jsonschema."""
    valeur = erreur.validator_value
    if erreur.validator == "required":
        champ = re.match(r"'(.+)' is a required property", erreur.message)
        return f"champ obligatoire manquant : {champ.group(1) if champ else valeur}"
    if erreur.validator == "enum":
        permis = ", ".join(str(v) for v in valeur)
        return f"valeur « {erreur.instance} » inconnue ; valeurs permises : {permis}"
    if erreur.validator == "const":
        return f"doit valoir « {valeur} », pas « {erreur.instance} »"
    if erreur.validator == "additionalProperties" and isinstance(erreur.instance, dict):
        inconnus = sorted(set(erreur.instance) - set(erreur.schema.get("properties", {})))
        return f"champ non permis ici : {', '.join(inconnus)}"
    if erreur.validator == "minimum":
        return f"{erreur.instance} est inférieur au minimum {valeur}"
    if erreur.validator == "maximum":
        return f"{erreur.instance} est supérieur au maximum {valeur}"
    return erreur.message


# --- Niveau 2 : cohérence ----------------------------------------------------

def erreurs_coherence(profil: dict, nom_fichier: str | None = None) -> list[str]:
    """Erreurs que le schéma ne peut pas exprimer. Suppose que le schéma passe."""
    erreurs = []
    if nom_fichier is not None and profil["id"] != nom_fichier:
        erreurs.append(f"id : « {profil['id']} » diffère du nom du fichier « {nom_fichier}.json »")

    try:
        date.fromisoformat(profil["pacte"]["date_signature"])
    except ValueError:
        erreurs.append(f"pacte/date_signature : « {profil['pacte']['date_signature']} » n'est pas une date réelle")

    minimum, maximum = profil["horizon_ans"]
    if maximum is not None and minimum > maximum:
        erreurs.append(f"horizon_ans : le minimum {minimum} dépasse le maximum {maximum}")

    erreurs += _erreurs_lignes(profil["portefeuille"], "portefeuille")
    if "decision_demo" in profil:  # facultative : absente d'un profil créé par le questionnaire (#84)
        erreurs += _erreurs_decision(profil["decision_demo"], _portefeuille_de_la_decision(profil))
    erreurs += _erreurs_regles(profil["pacte"]["regles"])
    erreurs += _erreurs_poches(profil)
    return erreurs


def _portefeuille_de_la_decision(profil: dict) -> list[dict]:
    """Portefeuille où la décision de démonstration est financée : celui de sa poche, s'il y en a une."""
    id_poche = profil["decision_demo"].get("poche")
    poche = next((p for p in profil.get("poches", []) if p["id"] == id_poche), None)
    return poche["portefeuille"] if poche else profil["portefeuille"]


def _erreurs_poches(profil: dict) -> list[str]:
    """Poches (#115) : id uniques, parts qui totalisent 1, portefeuilles et règles valides, portefeuille global cohérent.

    Sans poches : au moins une règle dans le Pacte, et une décision de démonstration sans poche.
    """
    poche_demo = profil.get("decision_demo", {}).get("poche")
    if not a_des_poches(profil):
        erreurs = [] if profil["pacte"]["regles"] else ["pacte/regles : au moins une règle est nécessaire"]
        if poche_demo is not None:
            erreurs.append(f"decision_demo/poche : « {poche_demo} » alors que le profil n'a pas de poches")
        return erreurs

    erreurs = []
    poches = profil["poches"]
    ids = [poche["id"] for poche in poches]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        erreurs.append(f"poches : id de poche en double : {', '.join(doublons)}")
    somme = sum(poche["part"] for poche in poches)
    if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
        erreurs.append(f"poches : les parts totalisent {somme:.4f}, pas 1")
    for i, poche in enumerate(poches):
        lieu = f"poches/{i} (poche « {poche['id']} »)"
        minimum, maximum = poche["horizon_ans"]
        if maximum is not None and minimum > maximum:
            erreurs.append(f"{lieu}/horizon_ans : le minimum {minimum} dépasse le maximum {maximum}")
        erreurs += _erreurs_lignes(poche["portefeuille"], f"{lieu}/portefeuille")
        erreurs += _erreurs_regles(poche["regles"], f"{lieu}/regles")
        if not regles_de_la_poche(profil, poche):
            erreurs.append(f"{lieu} : aucune règle, ni commune (pacte/regles) ni propre à la poche")
    ecarts = ecarts_portefeuille_global(profil)
    if ecarts:
        erreurs.append("portefeuille : il doit être la somme des portefeuilles des poches pondérés par leur part ("
                       + " ; ".join(ecarts) + ")")
    if poche_demo is not None and poche_demo not in ids:
        erreurs.append(f"decision_demo/poche : « {poche_demo} » n'est pas une poche du profil ({', '.join(ids)})")
    return erreurs


def _erreurs_lignes(lignes: list[dict], champ: str) -> list[str]:
    """Poids qui totalisent 1 et tickers sans doublon."""
    erreurs = []
    somme = sum(ligne["poids"] for ligne in lignes)
    if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
        erreurs.append(f"{champ} : les poids totalisent {somme:.4f}, pas 1")
    tickers = [ligne["ticker"] for ligne in lignes]
    doublons = sorted({t for t in tickers if tickers.count(t) > 1})
    if doublons:
        erreurs.append(f"{champ} : ticker en double : {', '.join(doublons)}")
    return erreurs


def _erreurs_decision(decision: dict, portefeuille: list[dict]) -> list[str]:
    if decision["type"] == "reallocation":
        return _erreurs_lignes(decision["panier"], "decision_demo/panier")

    financement = decision["financement"]
    if financement.startswith("depuis_"):
        source = financement.removeprefix("depuis_")
        if source not in {ligne["ticker"] for ligne in portefeuille}:
            return [f"decision_demo/financement : « {source} » n'est pas dans le portefeuille"]
    return []


def _erreurs_regles(regles: list[dict], champ: str = "pacte/regles") -> list[str]:
    """Id uniques et non réservés, catégories existantes."""
    erreurs = []
    ids = [regle["id"] for regle in regles]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        erreurs.append(f"{champ} : id de règle en double : {', '.join(doublons)}")

    connues = noms_categories()
    for i, regle in enumerate(regles):
        lieu = f"{champ}/{i} (règle « {regle['id']} »)"
        if regle["id"] in IDS_REGLES_RESERVES:
            erreurs.append(f"{lieu} : id réservé par le système, choisir un autre id")
        inconnues = [c for c in regle.get("categories", []) if c not in connues]
        if inconnues:
            erreurs.append(
                f"{lieu} : catégorie inconnue : {', '.join(inconnues)} ; "
                f"catégories définies dans config/categories.json : {', '.join(sorted(connues))}"
            )
    return erreurs


# --- Sorties pour le contrat -------------------------------------------------

def pacte_pour_contrat(profil: dict) -> dict:
    """Champ « pacte » du contrat de sortie : les règles sans leur justification.

    Profil projeté sur une poche (#115, ``pipeline.poches.profil_de_la_poche``) : horizon
    et règles de la poche, et le champ ``poche`` (id, objectif, horizon, part).
    """
    pacte = {
        "id": profil["id"],
        "profil_risque": profil["profil_risque"],
        "horizon_ans": profil["horizon_ans"],
        "date_signature": profil["pacte"]["date_signature"],
        "regles": [
            {cle: valeur for cle, valeur in regle.items() if cle != "justification"}
            for regle in profil["pacte"]["regles"]
        ],
    }
    if "poche" in profil:
        pacte["poche"] = dict(profil["poche"])
    return pacte


def piece_pacte(profil: dict, id_piece: str) -> dict:
    """Pièce « Pacte » : les paramètres chiffrés des règles, citables par les agents.

    Le numéro de la pièce est donné par le pipeline, qui numérote toutes les pièces.
    """
    valeurs = {"date_signature": profil["pacte"]["date_signature"]}
    for regle in profil["pacte"]["regles"]:
        parametre = PARAMETRE_CHIFFRE.get(regle["type"])
        if parametre is not None:
            valeurs[regle["id"]] = regle[parametre]
    valeurs["horizon_ans"] = profil["horizon_ans"]
    titre = f"Pacte {_de(profil['nom'])}"
    traitement = "Règles typées lues par l'agent Profil (format générique du Pacte)"
    poche = profil.get("poche")
    if poche is not None:  # profil projeté sur une poche (#115)
        valeurs["part_poche"] = poche["part"]
        titre += f" : poche « {poche['objectif']} »"
        traitement += (f" ; poche « {poche['id']} » : son horizon, ses règles propres et les règles communes "
                       "du Pacte qu'elle ne remplace pas")

    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": titre,
        "outil": "charger_pacte",
        "valeurs": valeurs,
        "valeur_affichee": f"Signé le {_date_francaise(profil['pacte']['date_signature'])}",
        "source": f"personas/{profil['id']}.json (persona fictif)",
        "traitement": traitement,
        "limites": _limites_seuils(profil),
    }


def _limites_seuils(profil: dict) -> str:
    """Les seuils sont des hypothèses, sauf ceux mesurés par le Pacte vécu (#68), qui citent leur pièce."""
    mesures = [r for r in profil["pacte"]["regles"] if r.get("piece")]
    if not mesures:
        return "Les seuils sont des hypothèses de l'équipe"
    pieces = ", ".join(sorted({r["piece"] for r in mesures}))
    return f"Seuil de pire baisse mesuré sur les réponses de l'utilisateur ({pieces}) ; les autres seuils sont des hypothèses de l'équipe"


def _de(nom: str) -> str:
    """« de Robert », « d'Amira »."""
    return f"d'{nom}" if nom[:1].lower() in VOYELLES else f"de {nom}"


def _date_francaise(date_iso: str) -> str:
    """« 2026-11-14 » → « 14 nov. 2026 »."""
    annee, mois, jour = date_iso.split("-")
    return f"{int(jour)} {MOIS_ABREGES[int(mois) - 1]} {annee}"
