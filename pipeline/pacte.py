"""Chargement et validation d'un fichier profil (Pacte), quel qu'il soit.

Le code ne connaît aucun nom de persona : il lit uniquement le fichier et ses
règles typées (CLAUDE.md, section 3). Ajouter un profil = ajouter un fichier
personas/<id>.json qui passe cette validation.

Deux niveaux de validation, comme pour le contrat (contrat/valider.py) :
1. le schéma JSON (personas/schema_pacte.json) : champs, types, paramètres de
   chaque type de règle ;
2. les renvois que le schéma ne peut pas exprimer : id de règles uniques,
   catégories citées qui existent dans config/categories.json, poids qui
   totalisent 1.

Usage : python -m pipeline.pacte personas/robert.json [...]
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from pipeline.categories import CHEMIN_CATEGORIES, charger_categories

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "personas" / "schema_pacte.json"
TOLERANCE_SOMME_POIDS = 1e-6
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

# Valeur chiffrée de chaque type de règle reprise dans la pièce Pacte
# (les règles sans paramètre chiffré n'y figurent pas).
PARAMETRE_CHIFFRE = {"pire_baisse_max": "seuil", "plafond": "max"}


class PacteInvalide(ValueError):
    """Le fichier profil ne respecte pas le format du Pacte.

    L'attribut `erreurs` contient la liste des problèmes trouvés.
    """

    def __init__(self, chemin, erreurs):
        self.erreurs = erreurs
        details = "\n".join(f"  - {erreur}" for erreur in erreurs)
        super().__init__(f"Pacte invalide ({chemin}) :\n{details}")


def charger_schema():
    with open(CHEMIN_SCHEMA, encoding="utf-8") as fichier:
        return json.load(fichier)


def _message_en_francais(erreur):
    """Traduit les erreurs de jsonschema les plus fréquentes en message clair."""
    if erreur.validator == "required":
        manquants = [champ for champ in erreur.validator_value if champ not in erreur.instance]
        return f"champ obligatoire manquant : {', '.join(manquants)}"
    if erreur.validator == "enum":
        permis = ", ".join(str(valeur) for valeur in erreur.validator_value)
        return f"valeur « {erreur.instance} » inconnue (valeurs permises : {permis})"
    if erreur.validator == "const":
        return f"valeur « {erreur.instance} » refusée (attendu : {erreur.validator_value})"
    if erreur.validator == "additionalProperties":
        return f"champ non prévu par le format : {erreur.message}"
    if erreur.validator == "not" and "required" in erreur.validator_value:
        # Bloc « not required » du schéma : paramètre d'un autre type de règle.
        parametre = erreur.validator_value["required"][0]
        return f"paramètre « {parametre} » non permis pour le type « {erreur.instance.get('type')} »"
    return erreur.message


def erreurs_schema(profil):
    """Erreurs du schéma JSON, sous la forme « chemin : message »."""
    validateur = Draft202012Validator(charger_schema())
    erreurs = sorted(validateur.iter_errors(profil), key=lambda e: list(e.absolute_path))
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(racine)'} : {_message_en_francais(e)}"
        for e in erreurs
    ]


def _erreur_somme_poids(lignes, chemin):
    somme = sum(ligne["poids"] for ligne in lignes)
    if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
        return [f"{chemin} : les poids totalisent {somme:.4f}, pas 1"]
    return []


def erreurs_renvois(profil, noms_categories):
    """Erreurs de cohérence que le schéma ne peut pas exprimer."""
    erreurs = []

    ids_regles = [regle["id"] for regle in profil["pacte"]["regles"]]
    for id_regle in sorted({i for i in ids_regles if ids_regles.count(i) > 1}):
        erreurs.append(f"pacte/regles : identifiant de règle « {id_regle} » en double")

    for i, regle in enumerate(profil["pacte"]["regles"]):
        for categorie in regle.get("categories", []):
            if categorie not in noms_categories:
                connues = ", ".join(sorted(noms_categories))
                erreurs.append(
                    f"pacte/regles/{i} ({regle['id']}) : catégorie « {categorie} » inconnue "
                    f"(catégories de config/categories.json : {connues})"
                )

    minimum, maximum = profil["horizon_ans"]
    if maximum is not None and maximum < minimum:
        erreurs.append(f"horizon_ans : le maximum ({maximum}) est plus petit que le minimum ({minimum})")

    tickers = [ligne["ticker"] for ligne in profil["portefeuille"]]
    for ticker in sorted({t for t in tickers if tickers.count(t) > 1}):
        erreurs.append(f"portefeuille : titre « {ticker} » en double")
    erreurs += _erreur_somme_poids(profil["portefeuille"], "portefeuille")

    decision = profil["decision_demo"]
    if decision["type"] == "reallocation":
        erreurs += _erreur_somme_poids(decision["panier"], "decision_demo/panier")

    return erreurs


def valider_profil(profil, noms_categories):
    """Liste des erreurs du profil (vide s'il est valide).

    Les renvois ne sont vérifiés que si le schéma passe, car ils supposent
    que les champs existent et ont le bon type.
    """
    erreurs = erreurs_schema(profil)
    if erreurs:
        return erreurs
    return erreurs_renvois(profil, noms_categories)


def charger_profil(chemin, chemin_categories=CHEMIN_CATEGORIES):
    """Lit et valide un fichier profil. Lève PacteInvalide avec un message clair sinon."""
    with open(chemin, encoding="utf-8") as fichier:
        profil = json.load(fichier)
    erreurs = valider_profil(profil, set(charger_categories(chemin_categories)))
    if erreurs:
        raise PacteInvalide(chemin, erreurs)
    return profil


def date_lisible(date_iso):
    """« 2026-11-14 » → « 14 nov. 2026 »."""
    annee, mois, jour = date_iso.split("-")
    return f"{int(jour)} {MOIS[int(mois) - 1]} {annee}"


def piece_pacte(profil, source, id_piece="P3"):
    """Construit la pièce « Pacte » du contrat (CLAUDE.md, section 5) à partir d'un profil validé.

    Les valeurs chiffrées des règles sont rangées sous l'id de la règle
    (ex. : {"pire_baisse_max": -0.12, "plafond_crypto": 0.0}), pour que
    verifier_chiffres puisse retrouver un seuil cité dans un argument.
    """
    pacte = profil["pacte"]
    valeurs = {"date_signature": pacte["date_signature"]}
    for regle in pacte["regles"]:
        parametre = PARAMETRE_CHIFFRE.get(regle["type"])
        if parametre is not None:
            valeurs[regle["id"]] = regle[parametre]
    valeurs["horizon_ans"] = list(profil["horizon_ans"])

    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": profil["etiquette"],
        "titre": f"Pacte de {profil['nom']}",
        "outil": "charger_pacte",
        "valeurs": valeurs,
        "valeur_affichee": f"Signé le {date_lisible(pacte['date_signature'])}",
        "source": f"{source} (profil {profil['etiquette']})",
        "traitement": "Règles typées lues par l'agent Profil (format générique du Pacte)",
        "limites": "Les seuils sont des hypothèses de l'équipe, pas des recommandations réglementaires",
    }


def pacte_du_contrat(profil):
    """Champ « pacte » du contrat : les règles du fichier, sans leurs justifications."""
    return {
        "id": profil["id"],
        "profil_risque": profil["profil_risque"],
        "horizon_ans": list(profil["horizon_ans"]),
        "date_signature": profil["pacte"]["date_signature"],
        "regles": [
            {cle: valeur for cle, valeur in regle.items() if cle != "justification"}
            for regle in profil["pacte"]["regles"]
        ],
    }


def charger_pacte(chemin, id_piece="P3", chemin_categories=CHEMIN_CATEGORIES):
    """Valide un fichier profil et renvoie sa pièce « Pacte ».

    id_piece : numéro attribué par le pipeline (P3 dans l'exemple du contrat).
    """
    chemin = Path(chemin)
    profil = charger_profil(chemin, chemin_categories)
    return piece_pacte(profil, source=f"personas/{chemin.name}", id_piece=id_piece)


def main(chemins):
    code_sortie = 0
    for chemin in chemins:
        try:
            profil = charger_profil(chemin)
        except PacteInvalide as erreur:
            code_sortie = 1
            print(f"✗ {erreur}")
        else:
            print(f"✓ {chemin} : {len(profil['pacte']['regles'])} règles")
    return code_sortie


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
