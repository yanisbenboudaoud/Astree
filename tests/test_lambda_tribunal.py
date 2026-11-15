"""Tests du point d'entrée de la Lambda (deploiement/lambda_tribunal.py) et de la lecture S3 (#13).

Ni AWS ni Bedrock : le procès est remplacé par un faux, S3 par un dictionnaire
(ou par botocore Stubber pour la lecture des CSV).
"""

import base64
import io
import json

import boto3
import pandas as pd
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from deploiement import lambda_tribunal
from pipeline import donnees
from pipeline.agent_profil import ProfilInconnu


class FauxS3:
    """S3 réduit à put_object et get_object, sur un dictionnaire."""

    def __init__(self):
        self.objets = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objets[Key] = json.loads(Body)

    def get_object(self, Bucket, Key):
        if Key not in self.objets:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        class Corps:
            def __init__(self, contenu):
                self.contenu = contenu

            def read(self):
                return json.dumps(self.contenu).encode("utf-8")

        return {"Body": Corps(self.objets[Key])}


@pytest.fixture
def s3(monkeypatch):
    faux = FauxS3()
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    monkeypatch.setattr(lambda_tribunal, "_client_s3", lambda: faux)
    return faux


CONTRAT = {"persona": "robert", "decision": {"libelle": "30 % en TSLA"}, "verdict": None}


@pytest.fixture
def faux_proces(monkeypatch):
    appels = []

    def juger(profil, demande):
        appels.append((profil, demande))
        if profil == "inconnu":
            raise ProfilInconnu("Aucun profil « inconnu » dans personas/")
        return dict(CONTRAT)
    monkeypatch.setattr(lambda_tribunal, "juger_decision", juger)
    return appels


def evenement(chemin, corps, methode="POST", base64_=False):
    brut = json.dumps(corps)
    return {"rawPath": chemin, "requestContext": {"http": {"method": methode}},
            "body": base64.b64encode(brut.encode()).decode() if base64_ else brut,
            "isBase64Encoded": base64_}


def reponse(resultat):
    return resultat["statusCode"], json.loads(resultat["body"])


# --- Routes ------------------------------------------------------------------------


def test_route_inconnue_404():
    assert lambda_tribunal.handler(evenement("/autre", {}))["statusCode"] == 404


def test_methode_autre_que_post_405():
    assert lambda_tribunal.handler(evenement("/tribunal", {}, methode="GET"))["statusCode"] == 405


@pytest.mark.parametrize("corps, message", [
    ({"demande": "30 % en Tesla"}, "profil"),
    ({"profil": "robert"}, "demande"),
    ({"profil": "robert", "demande": "x" * 2001}, "trop longue"),
])
def test_tribunal_corps_invalide_400(corps, message, faux_proces):
    statut, contenu = reponse(lambda_tribunal.handler(evenement("/tribunal", corps)))
    assert statut == 400 and message in contenu["erreur"]
    assert faux_proces == []  # aucun procès (ni appel Bedrock) lancé


def test_corps_json_illisible_400():
    evt = evenement("/tribunal", {})
    evt["body"] = "{pas du json"
    assert lambda_tribunal.handler(evt)["statusCode"] == 400


# --- /tribunal ---------------------------------------------------------------------


def test_tribunal_renvoie_le_contrat_et_l_archive(s3, faux_proces):
    resultat = lambda_tribunal.handler(evenement("/tribunal", {"profil": "robert", "demande": "30 % en Tesla"},
                                                 base64_=True))
    statut, contenu = reponse(resultat)
    assert statut == 200 and contenu == CONTRAT  # le format du contrat ne change pas
    identifiant = resultat["headers"]["X-Proces-Id"]
    assert lambda_tribunal.FORMAT_ID.fullmatch(identifiant)
    assert s3.objets[f"traces/{identifiant[:10]}/{identifiant}.json"] == CONTRAT


def test_tribunal_profil_inconnu_404(s3, faux_proces):
    statut, contenu = reponse(lambda_tribunal.handler(evenement("/tribunal", {"profil": "inconnu", "demande": "x"})))
    assert statut == 404 and "inconnu" in contenu["erreur"]


def test_tribunal_renvoye_meme_si_l_archive_echoue(monkeypatch, faux_proces):
    monkeypatch.delenv("BUCKET_PROJET", raising=False)  # archive impossible
    resultat = lambda_tribunal.handler(evenement("/tribunal", {"profil": "robert", "demande": "x"}))
    assert resultat["statusCode"] == 200  # le procès a coûté des appels Bedrock : on le renvoie
    assert "X-Proces-Id" not in resultat["headers"]


# --- /verdict ----------------------------------------------------------------------


def test_verdict_archive_le_proces_avec_le_choix(s3, faux_proces):
    resultat = lambda_tribunal.handler(evenement("/tribunal", {"profil": "robert", "demande": "x"}))
    identifiant = resultat["headers"]["X-Proces-Id"]

    statut, contenu = reponse(lambda_tribunal.handler(
        evenement("/verdict", {"id": identifiant, "verdict": "modifie"})))

    # Rangé par profil : l'outil de jurisprudence (#56) relit les verdicts d'un profil.
    assert statut == 200 and contenu["archive"] == f"verdicts/robert/{identifiant}.json"
    assert s3.objets[f"verdicts/robert/{identifiant}.json"] == {**CONTRAT, "verdict": "modifie"}


def test_verdict_pour_un_proces_inconnu_404(s3):
    statut, _ = reponse(lambda_tribunal.handler(
        evenement("/verdict", {"id": "2026-11-14-000000000000", "verdict": "maintenu"})))
    assert statut == 404


@pytest.mark.parametrize("corps", [
    {"id": "../traces/autre", "verdict": "maintenu"},     # identifiant hors format (chemin S3)
    {"id": "2026-11-14-000000000000", "verdict": "oui"},  # verdict hors contrat
])
def test_verdict_invalide_400(corps, s3):
    assert lambda_tribunal.handler(evenement("/verdict", corps))["statusCode"] == 400


# --- /question (contre-interrogatoire, #55) -------------------------------------------

ECHANGE = {"question": "Et à 15 % ?", "pieces_ajoutees": ["P7"], "requisitoire": [], "plaidoirie": [],
           "arguments_rejetes": [], "controle_chiffres": {"statut": "a_verifier", "regle": "verifier_chiffres",
                                                          "message": "x"}, "trace": []}


@pytest.fixture
def faux_interroger(monkeypatch):
    appels = []

    def interroger(contrat, question):
        appels.append((contrat, question))
        if question == "vide":
            raise lambda_tribunal.QuestionInvalide("Question vide : posez une question sur le procès")
        return {**contrat, "pieces": [{"id": "P7", "titre": "Simulation à 15 %"}],
                "contre_interrogatoire": [ECHANGE]}
    monkeypatch.setattr(lambda_tribunal, "interroger", interroger)
    return appels


def test_question_repond_et_rearchive_le_proces(s3, faux_proces, faux_interroger):
    identifiant = lambda_tribunal.handler(
        evenement("/tribunal", {"profil": "robert", "demande": "x"}))["headers"]["X-Proces-Id"]

    statut, contenu = reponse(lambda_tribunal.handler(
        evenement("/question", {"id": identifiant, "question": "Et à 15 % ?"})))

    assert statut == 200
    assert contenu["echange"] == ECHANGE
    assert contenu["pieces"] == [{"id": "P7", "titre": "Simulation à 15 %"}]
    assert faux_interroger[0] == (CONTRAT, "Et à 15 % ?")  # le procès archivé, relu dans S3
    archive = s3.objets[f"traces/{identifiant[:10]}/{identifiant}.json"]
    assert archive["contre_interrogatoire"] == [ECHANGE]  # réarchivé au même endroit


def test_question_pour_un_proces_inconnu_404(s3, faux_interroger):
    statut, _ = reponse(lambda_tribunal.handler(
        evenement("/question", {"id": "2026-11-14-000000000000", "question": "Et à 15 % ?"})))
    assert statut == 404 and faux_interroger == []


@pytest.mark.parametrize("corps", [
    {"id": "../traces/autre", "question": "Et à 15 % ?"},   # identifiant hors format
    {"id": "2026-11-14-000000000000", "question": "   "},  # question vide
    {"id": "2026-11-14-000000000000"},                     # question absente
])
def test_question_invalide_400_sans_appel(corps, s3, faux_interroger):
    assert lambda_tribunal.handler(evenement("/question", corps))["statusCode"] == 400
    assert faux_interroger == []


def test_question_refusee_par_le_pipeline_400(s3, faux_proces, faux_interroger):
    identifiant = lambda_tribunal.handler(
        evenement("/tribunal", {"profil": "robert", "demande": "x"}))["headers"]["X-Proces-Id"]
    statut, contenu = reponse(lambda_tribunal.handler(
        evenement("/question", {"id": identifiant, "question": "vide"})))
    assert statut == 400 and "Question vide" in contenu["erreur"]


# --- Lecture des CSV dans S3 (pipeline/donnees.py) ------------------------------------


def test_l_univers_passe_par_la_lecture_des_donnees(monkeypatch):
    """Régression : pipeline/univers.py lisait le CSV sur le disque, absent du zip de la Lambda."""
    from pipeline import univers
    monkeypatch.setattr(univers.donnees, "charger_univers",
                        lambda: pd.DataFrame({"ticker": ["XOM"], "name": ["Exxon Mobil"]}))
    assert univers.charger_univers() == [{"ticker": "XOM", "name": "Exxon Mobil"}]


def test_lire_csv_depuis_s3(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    contenu = b"ticker,poids\nXOM,0.1\n"
    with Stubber(client) as stubber:
        stubber.add_response("get_object", {"Body": StreamingBody(io.BytesIO(contenu), len(contenu))},
                             {"Bucket": "bucket-de-test", "Key": "donnees/essai.csv"})
        monkeypatch.setattr(donnees.boto3, "client", lambda service: client)
        tableau = donnees.lire_csv("essai.csv")
    assert tableau.equals(pd.DataFrame({"ticker": ["XOM"], "poids": [0.1]}))


def test_lire_csv_s3_sans_bucket_erreur_lisible(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.delenv("BUCKET_PROJET", raising=False)
    with pytest.raises(donnees.ErreurDonnees, match="BUCKET_PROJET"):
        donnees.lire_csv("essai.csv")


def test_lire_csv_s3_objet_absent_erreur_lisible(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    with Stubber(client) as stubber:
        stubber.add_client_error("get_object", service_error_code="NoSuchKey")
        monkeypatch.setattr(donnees.boto3, "client", lambda service: client)
        with pytest.raises(donnees.ErreurDonnees, match="NoSuchKey"):
            donnees.lire_csv("absent.csv")


# --- /verifier : « Trompez le Greffier » (#69) -------------------------------------------

ID_PROCES = "2026-11-15-0123456789ab"
CONTRAT_ARCHIVE = {
    "persona": "robert",
    "decision": {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"},
    "pieces": [
        {"id": "P2", "type": "calculee", "valeurs": {"pire_baisse": -0.289679, "pire_baisse_actuelle": -0.077574}},
        {"id": "P3", "type": "calculee", "valeurs": {"rendement_2022_apres": -0.237129}},
    ],
}


@pytest.fixture
def proces_archive(s3, monkeypatch):
    s3.objets[lambda_tribunal.cle_trace(ID_PROCES)] = CONTRAT_ARCHIVE
    monkeypatch.setattr(lambda_tribunal, "_appels_verifier", {})
    monkeypatch.setattr(lambda_tribunal, "juger_decision", lambda *a: pytest.fail("aucun procès attendu"))
    monkeypatch.setattr(lambda_tribunal, "interroger", lambda *a: pytest.fail("aucun appel Bedrock attendu"))
    return s3


def verifier(texte, pieces, identifiant=ID_PROCES):
    corps = {"id": identifiant, "texte": texte, "pieces": pieces}
    return reponse(lambda_tribunal.handler(evenement("/verifier", corps)))


def test_verifier_accepte_un_vrai_chiffre_de_la_piece_citee(proces_archive):
    statut, contenu = verifier("Avec 30 % en TSLA, la pire baisse passe à −29,0 %.", ["P2"])
    assert statut == 200 and contenu["valide"] and contenu["compte"] == "2/2"
    assert contenu["nombres"][1] == {"texte": "−29,0 %", "trouve": True, "sources": ["P2"], "motif": None}


def test_verifier_rejette_un_chiffre_invente_avec_son_motif(proces_archive):
    statut, contenu = verifier("TSLA ferait chuter le portefeuille à −40 %.", ["P2"])
    assert statut == 200 and not contenu["valide"]
    assert contenu["motif"] == "« −40 % » introuvable dans P2"


def test_verifier_signale_la_piece_qui_contient_le_chiffre(proces_archive):
    _, contenu = verifier("En 2022, le portefeuille aurait fait −23,7 %.", ["P2"])
    assert "présent dans P3, pièce non citée" in contenu["motif"]


def test_verifier_proces_inconnu_404(proces_archive):
    statut, contenu = verifier("−29,0 %", ["P2"], identifiant="2026-11-15-ffffffffffff")
    assert statut == 404 and "Aucun procès archivé" in contenu["erreur"]


@pytest.mark.parametrize("corps, message", [
    ({"id": ID_PROCES, "texte": "x" * 601, "pieces": ["P2"]}, "trop long"),
    ({"id": ID_PROCES, "texte": " ", "pieces": ["P2"]}, "texte"),
    ({"id": "pas-un-id", "texte": "−29,0 %", "pieces": ["P2"]}, "id"),
    ({"id": ID_PROCES, "texte": "−29,0 %", "pieces": ["P2; DROP"]}, "pieces"),
    ({"id": ID_PROCES, "texte": "−29,0 %", "pieces": [f"P{i}" for i in range(11)]}, "pieces"),
])
def test_verifier_requete_invalide_400(corps, message, proces_archive):
    statut, contenu = reponse(lambda_tribunal.handler(evenement("/verifier", corps)))
    assert statut == 400 and message in contenu["erreur"]


def test_verifier_debit_limite_par_adresse(proces_archive):
    for _ in range(lambda_tribunal.DEBIT_MAX_VERIFIER):
        assert verifier("−29,0 %", ["P2"])[0] == 200
    statut, contenu = verifier("−29,0 %", ["P2"])
    assert statut == 429 and "Trop de vérifications" in contenu["erreur"]


def test_fenetre_de_debit_glissante(monkeypatch):
    monkeypatch.setattr(lambda_tribunal, "_appels_verifier", {})
    for i in range(lambda_tribunal.DEBIT_MAX_VERIFIER):
        assert not lambda_tribunal.trop_de_verifications("1.2.3.4", maintenant=float(i))
    assert lambda_tribunal.trop_de_verifications("1.2.3.4", maintenant=59.0)
    assert not lambda_tribunal.trop_de_verifications("5.6.7.8", maintenant=59.0)
    assert not lambda_tribunal.trop_de_verifications("1.2.3.4", maintenant=61.0)
