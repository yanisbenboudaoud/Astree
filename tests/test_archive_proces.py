"""Archive des procès tenus sur AWS (#191) : sauvegarde reproductible, relecture vérifiée, sans réseau."""

import io
import json
import tarfile
from datetime import datetime, timezone

import pytest

from validation import evaluation_orchestrateur
from validation.archive_proces import MANIFESTE, lire_archive, sauvegarder, traces_archivees

LU_LE = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)


class FauxS3:
    """Objets JSON par clé, avec leur date S3 ; lecture seule."""

    def __init__(self, objets):
        self.objets = objets

    def get_paginator(self, nom):
        assert nom == "list_objects_v2"
        objets = self.objets

        class Paginateur:
            def paginate(self, Bucket, Prefix):
                return [{"Contents": [{"Key": k, "LastModified": datetime(2026, 11, 15, 12, i, tzinfo=timezone.utc),
                                       "Size": 1}
                                      for i, k in enumerate(sorted(objets)) if k.startswith(Prefix)]}]
        return Paginateur()

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(json.dumps(self.objets[Key]).encode())}


OBJETS = {
    "traces/2026-11-15/2026-11-15-bbb.json": {"persona": "amira"},
    "traces/2026-11-14/2026-11-14-aaa.json": {"persona": "robert"},
    "verdicts/robert/2026-11-14-aaa.json": {"verdict": "maintenu"},
    "profils/investisseur_x.json": {"id": "investisseur_x"},
    "progression/2026-11-15-bbb.json": {"statut": "termine"},  # pas un préfixe archivé
}


def test_sauvegarde_les_trois_prefixes_et_rien_d_autre(tmp_path):
    chemin = tmp_path / "proces.tar.gz"
    manifeste = sauvegarder("bucket-test", FauxS3(OBJETS), chemin, maintenant=LU_LE)
    assert manifeste["nombre_par_prefixe"] == {"traces/": 2, "verdicts/": 1, "profils/": 1}
    assert manifeste["bucket"] == "bucket-test" and manifeste["lu_le"] == "2026-11-16T10:00:00+00:00"
    lu, contenus = lire_archive(chemin)
    assert lu == manifeste
    assert sorted(contenus) == sorted(k for k in OBJETS if not k.startswith("progression/"))


def test_archive_reproductible(tmp_path):
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    sauvegarder("bucket-test", FauxS3(OBJETS), a, maintenant=LU_LE)
    sauvegarder("bucket-test", FauxS3(OBJETS), b, maintenant=LU_LE)
    assert a.read_bytes() == b.read_bytes()


def test_archive_garde_la_date_s3_de_chaque_fichier(tmp_path):
    chemin = tmp_path / "proces.tar.gz"
    sauvegarder("bucket-test", FauxS3(OBJETS), chemin, maintenant=LU_LE)
    with tarfile.open(chemin, "r:gz") as tar:
        dates = {m.name: m.mtime for m in tar.getmembers()}
    assert dates[MANIFESTE] == 0
    assert all(d > 0 for nom, d in dates.items() if nom != MANIFESTE)


def test_fichier_altere_detecte(tmp_path):
    chemin = tmp_path / "proces.tar.gz"
    manifeste = sauvegarder("bucket-test", FauxS3(OBJETS), chemin, maintenant=LU_LE)
    manifeste["fichiers"][0]["sha256"] = "0" * 64
    from validation.archive_proces import ecrire_archive
    _, contenus = lire_archive(chemin)
    ecrire_archive([(k, v, LU_LE) for k, v in contenus.items()], manifeste, chemin)
    with pytest.raises(ValueError, match="archive altérée"):
        lire_archive(chemin)


def test_traces_archivees_comme_lire_traces_s3(tmp_path):
    chemin = tmp_path / "proces.tar.gz"
    sauvegarder("bucket-test", FauxS3(OBJETS), chemin, maintenant=LU_LE)
    traces, _ = traces_archivees(chemin)
    assert traces == {"2026-11-14-aaa": {"persona": "robert"}, "2026-11-15-bbb": {"persona": "amira"}}


def test_mesure_de_l_orchestrateur_relue_depuis_l_archive(tmp_path, monkeypatch):
    chemin = tmp_path / "proces.tar.gz"
    sauvegarder("bucket-test", FauxS3(OBJETS), chemin, maintenant=LU_LE)
    import validation.archive_proces as archive
    monkeypatch.setattr(archive, "CHEMIN_ARCHIVE", chemin)
    monkeypatch.setattr(archive.traces_archivees, "__defaults__", (chemin,))
    lecture = evaluation_orchestrateur.lire(archive=True)
    assert lecture.archive and lecture.bucket == "bucket-test"
    assert lecture.date_lecture == "2026-11-16"  # date de la copie : rapport reproductible
    assert {"2026-11-14-aaa", "2026-11-15-bbb"} <= set(lecture.contrats)
    assert lecture.origines["2026-11-14-aaa"][0] == "S3"


# --- L'archive du dépôt : la mesure de #167 reste vérifiable sans AWS ---------------------

def test_rapport_orchestrateur_se_regenere_depuis_l_archive_du_depot():
    import json

    from validation.bulletin import CHEMIN_BULLETIN, mesure_orchestrateur
    from validation.evaluation import RACINE
    from validation.plan_proces import charger_plan, charger_resultats

    lecture = evaluation_orchestrateur.lire(archive=True)
    mesures = evaluation_orchestrateur.mesurer(lecture.contrats.values())
    texte = evaluation_orchestrateur.rapport(lecture, mesures, charger_plan(), charger_resultats())
    assert (RACINE / "docs" / "validation" / "evaluation_orchestrateur.md").read_text(encoding="utf-8") == texte, (
        "docs/validation/evaluation_orchestrateur.md n'est plus à jour : relancer "
        "python -m validation.evaluation orchestrateur --archive")
    _, mesure = mesure_orchestrateur(mesures, lecture.date_lecture)
    entree = json.loads(CHEMIN_BULLETIN.read_text(encoding="utf-8"))["mesures"]["orchestrateur"]
    assert {k: v for k, v in entree.items() if k != "date"} == mesure
