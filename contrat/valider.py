"""Validation du contrat de sortie du Tribunal (CLAUDE.md, section 5).

Deux niveaux :
1. le schéma JSON (contrat/schema_sortie.json) : champs obligatoires, types, valeurs permises ;
2. les renvois entre champs, que le schéma ne peut pas exprimer : pièces citées
   qui existent, contrôles qui portent sur une règle connue, etc.

Usage : python -m contrat.valider docs/exemples/contrat_robert.json [...]
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

CHEMIN_SCHEMA = Path(__file__).with_name("schema_sortie.json")
CONTROLES_SYSTEME = {"verifier_chiffres", "performance_passee", "biais_survivant"}
TOLERANCE_SOMME_POIDS = 1e-6


def charger_schema():
    with open(CHEMIN_SCHEMA, encoding="utf-8") as fichier:
        return json.load(fichier)


def erreurs_schema(contrat):
    """Erreurs du schéma JSON, sous la forme « chemin : message »."""
    validateur = Draft202012Validator(charger_schema())
    erreurs = sorted(validateur.iter_errors(contrat), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(racine)'} : {e.message}" for e in erreurs]


def erreurs_renvois(contrat):
    """Erreurs de cohérence entre les champs du contrat."""
    erreurs = []
    ids_pieces = [piece["id"] for piece in contrat["pieces"]]
    pieces_connues = set(ids_pieces)
    if len(ids_pieces) != len(pieces_connues):
        erreurs.append("pieces : identifiants en double")

    for champ in ("requisitoire", "plaidoirie", "arguments_rejetes", "controles"):
        for i, element in enumerate(contrat[champ]):
            for id_piece in element.get("pieces", []):
                if id_piece not in pieces_connues:
                    erreurs.append(f"{champ}/{i} : pièce {id_piece} inexistante")

    ids_regles = {regle["id"] for regle in contrat["pacte"]["regles"]}
    regles_controlees = set()
    for i, controle in enumerate(contrat["controles"]):
        regles_controlees.add(controle["regle"])
        if controle["regle"] not in ids_regles | CONTROLES_SYSTEME:
            erreurs.append(f"controles/{i} : règle « {controle['regle']} » inconnue du Pacte")
    for id_regle in sorted(ids_regles - regles_controlees):
        erreurs.append(f"controles : la règle « {id_regle} » du Pacte n'a aucun contrôle")
    if "verifier_chiffres" not in regles_controlees:
        erreurs.append("controles : le contrôle verifier_chiffres est absent")

    appels_orchestrateur = [e for e in contrat["trace"] if e["etape"] == "orchestrateur"]
    if not any(e["outil"] == "simuler_portefeuille" for e in appels_orchestrateur):
        erreurs.append("trace : la pièce obligatoire simuler_portefeuille est absente")
    for i, etape in enumerate(contrat["trace"]):
        sortie = etape["sortie"]
        if etape["etape"] == "orchestrateur" and sortie not in pieces_connues:
            erreurs.append(f"trace/{i} : la sortie « {sortie} » n'est pas une pièce")

    decision = contrat["decision"]
    if decision["type"] == "reallocation":
        somme = sum(ligne["poids"] for ligne in decision["panier"])
        if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
            erreurs.append(f"decision/panier : les poids totalisent {somme}, pas 1")

    return erreurs


def valider_contrat(contrat):
    """Liste des erreurs du contrat (vide s'il est valide).

    Les renvois ne sont vérifiés que si le schéma passe, car ils supposent
    que les champs existent et ont le bon type.
    """
    erreurs = erreurs_schema(contrat)
    if erreurs:
        return erreurs
    return erreurs_renvois(contrat)


def main(chemins):
    code_sortie = 0
    for chemin in chemins:
        with open(chemin, encoding="utf-8") as fichier:
            erreurs = valider_contrat(json.load(fichier))
        if erreurs:
            code_sortie = 1
            print(f"✗ {chemin}")
            for erreur in erreurs:
                print(f"  - {erreur}")
        else:
            print(f"✓ {chemin}")
    return code_sortie


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
