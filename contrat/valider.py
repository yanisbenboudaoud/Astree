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
CONTROLES_SYSTEME = {"verifier_chiffres", "cadre_simulation", "performance_passee", "biais_survivant",
                     "interpretation_demande"}
TYPES_CALCULABLES = {"pire_baisse_max", "plafond"}  # règles qui ont un point de bascule (#61)
TOLERANCE_SOMME_POIDS = 1e-6
# Sortie d'un appel d'outil refusé ou en erreur (orchestrateur, #12) : le procès continue sans pièce.
PREFIXE_ERREUR_OUTIL = "Erreur : "


def est_erreur_outil(sortie):
    """« Erreur : <motif> », avec un motif non vide."""
    return (isinstance(sortie, str) and sortie.startswith(PREFIXE_ERREUR_OUTIL)
            and bool(sortie[len(PREFIXE_ERREUR_OUTIL):].strip()))


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

    for champ in ("requisitoire", "plaidoirie", "arguments_rejetes", "controles", "points_de_bascule"):
        for i, element in enumerate(contrat.get(champ, [])):
            for id_piece in element.get("pieces", []):
                if id_piece not in pieces_connues:
                    erreurs.append(f"{champ}/{i} : pièce {id_piece} inexistante")

    for i, regle in enumerate(contrat["pacte"]["regles"]):
        piece = next((p for p in contrat["pieces"] if p["id"] == regle.get("piece")), None)
        if "piece" in regle and (piece is None or piece["type"] != "declaree"):
            erreurs.append(f"pacte/regles/{i} : la pièce {regle['piece']} du seuil mesuré n'est pas une pièce declaree")

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
    if not any(e["outil"] == "simuler_portefeuille" and e["sortie"] in pieces_connues
               for e in appels_orchestrateur):
        erreurs.append("trace : la pièce obligatoire simuler_portefeuille est absente")
    for i, etape in enumerate(contrat["trace"]):
        sortie = etape["sortie"]
        if etape["etape"] == "orchestrateur" and sortie not in pieces_connues and not est_erreur_outil(sortie):
            erreurs.append(f"trace/{i} : la sortie « {sortie} » n'est ni une pièce ni une erreur d'outil")

    if "points_de_bascule" in contrat:
        erreurs += erreurs_points_de_bascule(contrat)

    decision = contrat["decision"]
    if decision["type"] == "reallocation":
        somme = sum(ligne["poids"] for ligne in decision["panier"])
        if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
            erreurs.append(f"decision/panier : les poids totalisent {somme}, pas 1")

    erreurs += erreurs_contre_interrogatoire(contrat, pieces_connues)
    return erreurs


def erreurs_contre_interrogatoire(contrat, pieces_connues):
    """Renvois des échanges du contre-interrogatoire (#55), s'il y en a."""
    erreurs = []
    deja_ajoutees = set()
    for n, echange in enumerate(contrat.get("contre_interrogatoire", [])):
        chemin = f"contre_interrogatoire/{n}"
        for id_piece in echange["pieces_ajoutees"]:
            if id_piece not in pieces_connues:
                erreurs.append(f"{chemin} : pièce ajoutée {id_piece} absente du champ pieces")
            elif id_piece in deja_ajoutees:
                erreurs.append(f"{chemin} : pièce {id_piece} déjà ajoutée par un échange précédent")
            deja_ajoutees.add(id_piece)
        for champ in ("requisitoire", "plaidoirie", "arguments_rejetes"):
            for i, argument in enumerate(echange[champ]):
                for id_piece in argument["pieces"]:
                    if id_piece not in pieces_connues:
                        erreurs.append(f"{chemin}/{champ}/{i} : pièce {id_piece} inexistante")
        if echange["controle_chiffres"]["regle"] != "verifier_chiffres":
            erreurs.append(f"{chemin} : controle_chiffres doit porter sur verifier_chiffres")
        for i, etape in enumerate(echange["trace"]):
            sortie = etape["sortie"]
            if etape["etape"] == "orchestrateur" and sortie not in pieces_connues and not est_erreur_outil(sortie):
                erreurs.append(f"{chemin}/trace/{i} : la sortie « {sortie} » n'est ni une pièce ni une erreur d'outil")
    return erreurs


def erreurs_points_de_bascule(contrat):
    """Un point de bascule par règle calculable en violation, et seulement pour elles (#61)."""
    erreurs = []
    regles = {regle["id"]: regle for regle in contrat["pacte"]["regles"]}
    en_violation = {controle["regle"] for controle in contrat["controles"] if controle["statut"] == "violation"}
    attendues = {id_regle for id_regle in en_violation
                 if id_regle in regles and regles[id_regle]["type"] in TYPES_CALCULABLES}
    vues = set()
    for i, point in enumerate(contrat["points_de_bascule"]):
        regle = regles.get(point["regle"])
        if regle is None or regle["type"] not in TYPES_CALCULABLES:
            erreurs.append(f"points_de_bascule/{i} : « {point['regle']} » n'est pas une règle calculable du Pacte")
        elif regle["type"] != point["type"]:
            erreurs.append(f"points_de_bascule/{i} : type « {point['type']} » au lieu de « {regle['type']} »")
        elif point["regle"] not in en_violation:
            erreurs.append(f"points_de_bascule/{i} : la règle « {point['regle']} » n'est pas en violation")
        if point["regle"] in vues:
            erreurs.append(f"points_de_bascule/{i} : règle « {point['regle']} » en double")
        vues.add(point["regle"])
    for id_regle in sorted(attendues - vues):
        erreurs.append(f"points_de_bascule : la règle « {id_regle} » est en violation sans point de bascule")
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
