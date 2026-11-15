"""Tests de la jurisprudence (pipeline/jurisprudence.py, #56).

Ni AWS ni Bedrock : les archives sont des fichiers dans un dossier temporaire,
ou un faux client S3.
"""

import json
from pathlib import Path

import jsonschema
import pytest
from botocore.exceptions import ClientError

from pipeline import jurisprudence
from pipeline.agent_profil import chemin_profil
from pipeline.chiffres import verifier_argument
from pipeline.donnees import ErreurDonnees
from pipeline.jurisprudence import TOUTES, charger_archives, cle_verdict, piece_jurisprudence
from pipeline.orchestrateur import outils_du_profil
from pipeline.pacte import charger_pacte

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
PRUDENT = charger_pacte(chemin_profil("robert"))
PACTE = {"regles": [{"id": "pire_baisse_max"}, {"id": "plafond_crypto"}]}


def archive(verdict, violations=(), libelle="30 % en TSLA", autres_controles=()):
    """Contrat archivé réduit aux champs lus par la jurisprudence."""
    controles = [{"statut": "violation", "regle": regle} for regle in violations]
    controles += [{"statut": "conforme", "regle": "plafond_crypto"}, *autres_controles]
    return {"persona": "robert", "decision": {"libelle": libelle}, "pacte": PACTE,
            "controles": controles, "verdict": verdict}


# Les plus récentes d'abord, comme les renvoie charger_archives.
ARCHIVES = [
    ("2026-11-14-cccccccccccc", archive("maintenu", ["pire_baisse_max"])),
    ("2026-11-13-bbbbbbbbbbbb", archive("modifie", ["pire_baisse_max", "plafond_crypto"], "5 % en BTC-USD")),
    ("2026-11-12-aaaaaaaaaaaa", archive("maintenu", [], "5 % en XIU.TO")),
]


# --- Calcul de la pièce -----------------------------------------------------------


def test_aucun_antecedent_est_dit_et_jamais_invente():
    piece = piece_jurisprudence([], "pire_baisse_max")
    assert piece["valeurs"]["proces_archives"] == 0
    assert piece["valeurs"]["proces_en_violation"] == 0 and piece["valeurs"]["dates_antecedents"] == []
    assert piece["valeur_affichee"] == "Aucun procès archivé pour ce profil"


def test_compte_les_violations_d_une_regle_et_les_verdicts():
    valeurs = piece_jurisprudence(ARCHIVES, "pire_baisse_max")["valeurs"]
    assert valeurs["proces_archives"] == 3
    assert valeurs["proces_en_violation"] == 2
    assert (valeurs["maintenu"], valeurs["modifie"], valeurs["pacte_ajuste"]) == (1, 1, 0)
    assert valeurs["dates_antecedents"] == ["2026-11-14", "2026-11-13"]
    assert valeurs["decisions_antecedents"] == ["30 % en TSLA", "5 % en BTC-USD"]
    assert valeurs["regles_violees_antecedents"] == ["pire_baisse_max", "pire_baisse_max, plafond_crypto"]
    assert valeurs["verdicts_antecedents"] == ["maintenu", "modifie"]


def test_une_autre_regle_ne_compte_que_ses_violations():
    valeurs = piece_jurisprudence(ARCHIVES, "plafond_crypto")["valeurs"]
    assert valeurs["proces_en_violation"] == 1 and valeurs["modifie"] == 1 and valeurs["maintenu"] == 0


def test_toutes_les_regles():
    piece = piece_jurisprudence(ARCHIVES, TOUTES)
    assert piece["valeurs"]["proces_en_violation"] == 2
    assert piece["valeur_affichee"] == "3 procès archivés · 2 en violation : 1 maintenu, 1 modifié, 0 Pacte ajusté"


def test_proces_sans_verdict_ignore():
    archives = [("2026-11-14-dddddddddddd", archive(None, ["pire_baisse_max"])), *ARCHIVES]
    assert piece_jurisprudence(archives, "pire_baisse_max")["valeurs"]["proces_archives"] == 3


def test_controles_du_systeme_ne_sont_pas_des_regles_du_pacte():
    systeme = [{"statut": "violation", "regle": "verifier_chiffres"}]
    archives = [("2026-11-14-eeeeeeeeeeee", archive("maintenu", [], autres_controles=systeme))]
    assert piece_jurisprudence(archives, TOUTES)["valeurs"]["proces_en_violation"] == 0


def test_antecedents_detailles_bornes():
    archives = [(f"2026-11-{jour:02d}-aaaaaaaaaaaa", archive("maintenu", ["pire_baisse_max"]))
                for jour in range(14, 4, -1)]
    valeurs = piece_jurisprudence(archives, "pire_baisse_max")["valeurs"]
    assert valeurs["proces_en_violation"] == 10
    assert len(valeurs["dates_antecedents"]) == jurisprudence.NB_ANTECEDENTS_MAX


def test_piece_conforme_au_contrat():
    piece = {"id": "P4", **piece_jurisprudence(ARCHIVES, "pire_baisse_max")}
    jsonschema.validate(piece, {"$ref": "#/$defs/piece", "$defs": SCHEMA_CONTRAT["$defs"]})
    assert piece["type"] == "calculee" and piece["etiquette"] == "fait"


def test_le_greffier_verifie_les_chiffres_de_la_jurisprudence():
    """Un argument qui cite la pièce passe ; un compte inventé est rejeté."""
    piece = {"id": "P4", **piece_jurisprudence(ARCHIVES, "pire_baisse_max")}
    dossier = {"decision": {"taille": 0.30}, "periode": ["2021-11-12", "2026-11-12"], "pieces": [piece]}
    juste = {"texte": "Sur 3 procès archivés, 2 violaient déjà la pire baisse ; le 14 novembre, "
                      "la décision a été maintenue.", "pieces": ["P4"]}
    invente = {"texte": "La règle a été violée 4 fois.", "pieces": ["P4"]}
    assert verifier_argument(juste, dossier).valide
    assert not verifier_argument(invente, dossier).valide


# --- Lecture des archives ---------------------------------------------------------


def test_cle_rangee_par_profil():
    assert cle_verdict("robert", "2026-11-14-cccccccccccc") == "verdicts/robert/2026-11-14-cccccccccccc.json"


def ecrire(dossier, persona, identifiant, contenu):
    chemin = dossier / persona / f"{identifiant}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu), encoding="utf-8")


def test_local_lit_seulement_le_profil_juge(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "local")
    monkeypatch.setattr(jurisprudence, "DOSSIER_VERDICTS_LOCAL", tmp_path)
    for identifiant, contenu in ARCHIVES:
        ecrire(tmp_path, "robert", identifiant, contenu)
    ecrire(tmp_path, "amira", "2026-11-14-ffffffffffff", archive("pacte_ajuste", ["pire_baisse_max"]))

    archives = charger_archives("robert")
    assert [identifiant for identifiant, _ in archives] == [identifiant for identifiant, _ in ARCHIVES]
    assert charger_archives("inconnu") == []


class FauxS3:
    def __init__(self, objets, erreur=False):
        self.objets, self.erreur, self.prefixes = objets, erreur, []

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        faux = self

        class Paginateur:
            def paginate(self, Bucket, Prefix):
                faux.prefixes.append(Prefix)
                if faux.erreur:
                    raise ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectsV2")
                return [{"Contents": [{"Key": cle} for cle in faux.objets if cle.startswith(Prefix)]}]

        return Paginateur()

    def get_object(self, Bucket, Key):
        class Corps:
            def read(_):
                return json.dumps(self.objets[Key]).encode("utf-8")

        return {"Body": Corps()}


def test_s3_lit_le_prefixe_du_profil_les_plus_recentes_d_abord(monkeypatch):
    objets = {cle_verdict("robert", identifiant): contenu for identifiant, contenu in reversed(ARCHIVES)}
    objets[cle_verdict("amira", "2026-11-14-ffffffffffff")] = archive("maintenu")
    faux = FauxS3(objets)
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    monkeypatch.setattr(jurisprudence.boto3, "client", lambda service: faux)

    archives = charger_archives("robert")
    assert faux.prefixes == ["verdicts/robert/"]
    assert [identifiant for identifiant, _ in archives] == [identifiant for identifiant, _ in ARCHIVES]


def test_s3_illisible_devient_erreur_de_donnees(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    monkeypatch.setattr(jurisprudence.boto3, "client", lambda service: FauxS3({}, erreur=True))
    with pytest.raises(ErreurDonnees, match="illisibles"):
        charger_archives("robert")


# --- Branchement dans l'orchestrateur ---------------------------------------------


def test_outil_dans_la_liste_blanche_avec_les_regles_du_pacte():
    outils = {outil.nom: outil for outil in outils_du_profil(PRUDENT)}
    schema = outils["consulter_jurisprudence"].description_bedrock["toolSpec"]["inputSchema"]["json"]
    ids = [regle["id"] for regle in PRUDENT["pacte"]["regles"]]
    assert schema["properties"]["regle"]["enum"] == [*ids, TOUTES]


def test_deuxieme_proces_recoit_la_jurisprudence_du_premier(tmp_path, monkeypatch):
    """Un premier procès maintenu malgré une violation devient une pièce du suivant."""
    monkeypatch.setenv("SOURCE_DONNEES", "local")
    monkeypatch.setattr(jurisprudence, "DOSSIER_VERDICTS_LOCAL", tmp_path)
    ecrire(tmp_path, PRUDENT["id"], "2026-11-14-cccccccccccc", archive("maintenu", ["pire_baisse_max"]))

    outils = {outil.nom: outil for outil in outils_du_profil(PRUDENT)}
    piece = outils["consulter_jurisprudence"].executer({"regle": "pire_baisse_max"}, "P5")
    assert piece["id"] == "P5"
    assert piece["valeurs"]["proces_en_violation"] == 1 and piece["valeurs"]["maintenu"] == 1
