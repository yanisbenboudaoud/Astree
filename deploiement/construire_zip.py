"""Construit le zip de la Lambda du Tribunal (#13), depuis n'importe quel poste.

Contenu :
- les dépendances de ``requirements.txt`` (boto3, jsonschema), en **version Linux**
  pour Python 3.14 : pandas, numpy et pyarrow viennent de la couche Lambda ;
- le code et ses fichiers : ``pipeline/``, ``contrat/``, ``personas/``, ``config/``,
  ``donnees_externes/`` ;
- ``lambda_tribunal.py`` à la **racine** du zip (handler ``lambda_tribunal.handler``).

Les CSV ne sont pas dans le zip : dans Lambda, ``SOURCE_DONNEES=s3`` les lit dans le
bucket du projet (``deploiement/deployer.py`` les y envoie).

Usage (depuis la racine du dépôt) ::

    .venv\\Scripts\\python deploiement\\construire_zip.py            # → build\\lambda_tribunal.zip
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_BUILD = RACINE / "build"
DOSSIER_PAQUET = DOSSIER_BUILD / "paquet"
ZIP = DOSSIER_BUILD / "lambda_tribunal.zip"
DOSSIERS_DU_CODE = ("pipeline", "contrat", "personas", "config", "donnees_externes")
VERSION_PYTHON_LAMBDA = "3.14"


def installer_dependances(destination: Path) -> None:
    """Dépendances du zip, en roues Linux x86_64 pour le runtime python3.14."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(RACINE / "requirements.txt"),
         "--platform", "manylinux2014_x86_64", "--implementation", "cp",
         "--python-version", VERSION_PYTHON_LAMBDA, "--only-binary=:all:", "--target", str(destination)],
        check=True,
    )


def copier_code(destination: Path) -> None:
    ignorer = shutil.ignore_patterns("__pycache__", "*.pyc")
    for dossier in DOSSIERS_DU_CODE:
        shutil.copytree(RACINE / dossier, destination / dossier, ignore=ignorer)
    shutil.copy2(RACINE / "deploiement" / "lambda_tribunal.py", destination / "lambda_tribunal.py")


def zipper(source: Path, zip_sortie: Path) -> None:
    with zipfile.ZipFile(zip_sortie, "w", zipfile.ZIP_DEFLATED) as archive:
        for chemin in sorted(source.rglob("*")):
            if chemin.is_file() and "__pycache__" not in chemin.parts:
                archive.write(chemin, chemin.relative_to(source).as_posix())


def construire() -> Path:
    if DOSSIER_BUILD.exists():
        shutil.rmtree(DOSSIER_BUILD)
    DOSSIER_PAQUET.mkdir(parents=True)
    installer_dependances(DOSSIER_PAQUET)
    copier_code(DOSSIER_PAQUET)
    zipper(DOSSIER_PAQUET, ZIP)
    taille = sum(f.stat().st_size for f in DOSSIER_PAQUET.rglob("*") if f.is_file())
    print(f"{ZIP} : {ZIP.stat().st_size / 1e6:.1f} Mo compressé, {taille / 1e6:.0f} Mo décompressé "
          "(plus 190 Mo pour la couche pandas, sur 250 Mo permis)")
    return ZIP


if __name__ == "__main__":
    construire()
