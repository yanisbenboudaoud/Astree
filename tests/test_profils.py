"""Tests des profils créés par les utilisateurs (#87) : rangement, relecture et signature.

Ni AWS ni Bedrock : le dossier local est un dossier temporaire, S3 un faux client.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from pipeline import profils
from pipeline.agent_profil import FORMAT_IDENTIFIANT, ProfilInconnu, charger_profil
from pipeline.pacte import PacteInvalide, erreurs_profil
from pipeline.profils import (
    ProfilDejaExistant,
    appliquer_modifications,
    enregistrer_profil,
    lire_profil_cree,
    nouvel_identifiant_profil,
)
from pipeline.questionnaire import ReponsesInvalides, profil_depuis_reponses

RACINE = Path(__file__).resolve().parents[1]
SAISIE = json.loads((RACINE / "docs" / "exemples" / "reponses_questionnaire.json").read_text(encoding="utf-8"))
DATE = "2026-11-15"


def profil_exemple(identifiant: str | None = None) -> dict:
    return profil_depuis_reponses(SAISIE["reponses"], SAISIE["capital_cad"], SAISIE["portefeuille"], DATE,
                                  identifiant=identifiant or nouvel_identifiant_profil(), nom="Investisseur")


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_DONNEES", "local")
    monkeypatch.setattr(profils, "DOSSIER_PROFILS_LOCAL", tmp_path / "profils")
    return tmp_path / "profils"


# --- Identifiant ----------------------------------------------------------------------


def test_identifiant_neuf_au_format_d_un_profil_et_unique():
    identifiants = {nouvel_identifiant_profil() for _ in range(50)}
    assert len(identifiants) == 50
    assert all(FORMAT_IDENTIFIANT.fullmatch(i) and i.startswith("investisseur_") for i in identifiants)


# --- Rangement local ------------------------------------------------------------------


def test_un_profil_range_est_relu_et_valide(local):
    profil = profil_exemple()
    emplacement = enregistrer_profil(profil)
    assert Path(emplacement) == local / f"{profil['id']}.json"
    assert lire_profil_cree(profil["id"]) == profil
    assert charger_profil(profil["id"]) == profil


def test_un_profil_de_demonstration_reste_lu_dans_personas(local):
    assert charger_profil("robert")["id"] == "robert"


def test_profil_absent(local):
    assert lire_profil_cree("investisseur_absent") is None
    with pytest.raises(ProfilInconnu, match="ni parmi les profils créés"):
        charger_profil("investisseur_absent")


def test_identifiant_invalide_jamais_cherche_hors_du_dossier(local):
    with pytest.raises(ProfilInconnu, match="invalide"):
        charger_profil("../personas/robert")


def test_un_profil_ne_s_ecrase_jamais(local):
    profil = profil_exemple()
    enregistrer_profil(profil)
    with pytest.raises(ProfilDejaExistant):
        enregistrer_profil(profil)


def test_un_profil_cree_n_ecrase_jamais_un_profil_de_demonstration(local):
    with pytest.raises(ProfilDejaExistant, match="démonstration"):
        enregistrer_profil(profil_exemple("robert"))
    assert not (local / "robert.json").exists()


def test_un_profil_invalide_n_est_pas_range(local):
    profil = profil_exemple()
    profil["portefeuille"] = []
    with pytest.raises(ReponsesInvalides):
        enregistrer_profil(profil)
    assert not local.exists() or not any(local.iterdir())


def test_un_profil_range_puis_abime_est_refuse_a_la_lecture(local):
    profil = profil_exemple()
    enregistrer_profil(profil)
    chemin = local / f"{profil['id']}.json"
    abime = {**profil, "horizon_ans": "longtemps"}
    chemin.write_text(json.dumps(abime), encoding="utf-8")
    with pytest.raises(PacteInvalide):
        charger_profil(profil["id"])


# --- Rangement S3 -----------------------------------------------------------------------


class FauxS3:
    def __init__(self):
        self.objets = {}

    def put_object(self, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert IfNoneMatch == "*"  # écriture conditionnelle : jamais d'écrasement
        if Key in self.objets:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objets[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objets:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        class Corps:
            def __init__(self, contenu):
                self.contenu = contenu

            def read(self):
                return self.contenu

        return {"Body": Corps(self.objets[Key])}


@pytest.fixture
def s3(monkeypatch):
    faux = FauxS3()
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.setenv("BUCKET_PROJET", "bucket-de-test")
    monkeypatch.setattr(profils.boto3, "client", lambda service: faux)
    return faux


def test_s3_range_sous_profils_et_relit(s3):
    profil = profil_exemple()
    assert enregistrer_profil(profil) == f"s3://bucket-de-test/profils/{profil['id']}.json"
    assert f"profils/{profil['id']}.json" in s3.objets
    assert charger_profil(profil["id"]) == profil


def test_s3_ne_reecrit_jamais_un_profil(s3):
    profil = profil_exemple()
    enregistrer_profil(profil)
    with pytest.raises(ProfilDejaExistant):
        enregistrer_profil(profil)


def test_s3_profil_absent(s3):
    assert lire_profil_cree("investisseur_absent") is None


def test_s3_sans_bucket(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.delenv("BUCKET_PROJET", raising=False)
    with pytest.raises(Exception, match="BUCKET_PROJET"):
        lire_profil_cree("investisseur_absent")


# --- Seuils choisis par l'utilisateur -------------------------------------------------------


def regle(profil: dict, id_regle: str) -> dict:
    return next(r for r in profil["pacte"]["regles"] if r["id"] == id_regle)


def test_seuil_de_pire_baisse_choisi_par_l_utilisateur():
    profil = profil_exemple()
    propose = regle(profil, "pire_baisse_max")["seuil"]
    modifie = appliquer_modifications(profil, {"pire_baisse_max": -0.15}, DATE)
    nouvelle = regle(modifie, "pire_baisse_max")
    assert nouvelle["seuil"] == -0.15
    assert nouvelle["libelle"] == "Pire baisse tolérée : −15,0 %"
    assert nouvelle["justification"].startswith(f"Choisi par vous le {DATE} : −15,0 % au lieu de −20,0 % ")
    assert regle(profil, "pire_baisse_max")["seuil"] == propose  # l'original n'est pas touché
    assert erreurs_profil(modifie, nom_fichier=modifie["id"]) == []


def test_plafond_choisi_par_l_utilisateur():
    modifie = appliquer_modifications(profil_exemple(), {"plafond_tech": 0.25}, DATE)
    nouvelle = regle(modifie, "plafond_tech")
    assert nouvelle["max"] == 0.25
    assert nouvelle["libelle"] == "Technologie : 25 % du portefeuille au maximum"
    assert "Choisi par vous" in nouvelle["justification"]


def test_meme_valeur_que_le_bareme_rien_ne_change():
    profil = profil_exemple()
    seuil = regle(profil, "pire_baisse_max")["seuil"]
    assert appliquer_modifications(profil, {"pire_baisse_max": seuil}, DATE) == profil


@pytest.mark.parametrize("modifications, motif", [
    ({"inconnue": -0.1}, "Règle inconnue"),
    ({"regle_personnelle": 0.1}, "pas de seuil"),
    ({"pire_baisse_max": "−20 %"}, "nombre"),
    ({"pire_baisse_max": 0.2}, "entre −1 et 0"),
    ({"plafond_tech": 1.5}, "entre 0 et 1"),
])
def test_modifications_refusees(modifications, motif):
    with pytest.raises(ReponsesInvalides, match=motif):
        appliquer_modifications(profil_exemple(), modifications, DATE)
