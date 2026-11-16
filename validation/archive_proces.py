"""Archive des procès tenus sur AWS, pour qu'ils survivent au compte de l'événement (#191).

Le jury ne pourra pas tester : le compte AWS sera supprimé. Or la mesure de l'orchestrateur
(#167) relit les contrats archivés par la Lambda dans S3. Ce module copie, en **lecture seule**,
les préfixes du bucket du projet dans une seule archive versionnée :

- ``traces/<date>/<id>.json`` : le contrat de chaque procès (pièces, débat, contrôles, trace) ;
- ``verdicts/<profil>/<id>.json`` : le verdict rendu par l'utilisateur (jurisprudence, #56) ;
- ``profils/<id>.json`` : les profils construits par le questionnaire (#87).

L'archive ``validation/proces_tenus.tar.gz`` contient aussi ``MANIFESTE.json`` : bucket, date de
lecture, et pour chaque fichier sa date S3, sa taille et son empreinte SHA-256. Elle est écrite
de façon reproductible (fichiers triés, dates des objets S3, en-tête gzip sans date) : la même
lecture donne le même fichier.

Usage : ``python -m validation.archive_proces`` (identifiants de ``aws login``, aucun appel à
Bedrock). Ensuite, ``python -m validation.evaluation orchestrateur --archive`` relit l'archive
sans AWS.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_ARCHIVE = RACINE / "validation" / "proces_tenus.tar.gz"
PREFIXES = ("traces/", "verdicts/", "profils/")
MANIFESTE = "MANIFESTE.json"


def lister_objets(s3, bucket: str, prefixes: tuple[str, ...] = PREFIXES) -> list[dict[str, Any]]:
    """Objets JSON des préfixes, triés par clé : ``Key``, ``LastModified``, ``Size``."""
    objets = []
    for prefixe in prefixes:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe):
            objets += [o for o in page.get("Contents", []) if o["Key"].endswith(".json")]
    return sorted(objets, key=lambda o: o["Key"])


def ecrire_archive(fichiers: list[tuple[str, bytes, datetime]], manifeste: dict[str, Any],
                   chemin: Path = CHEMIN_ARCHIVE) -> None:
    """Écrit l'archive de façon reproductible : même contenu, même fichier."""
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w", format=tarfile.PAX_FORMAT) as tar:
        entrees = [(MANIFESTE, json.dumps(manifeste, ensure_ascii=False, indent=1).encode("utf-8"), None)]
        for nom, contenu, date_objet in entrees + sorted(fichiers, key=lambda f: f[0]):
            info = tarfile.TarInfo(nom)
            info.size = len(contenu)
            info.mtime = int(date_objet.timestamp()) if date_objet else 0
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(contenu))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "wb") as sortie, gzip.GzipFile(fileobj=sortie, mode="wb", mtime=0, filename="") as gz:
        gz.write(tampon.getvalue())


def sauvegarder(bucket: str, s3=None, chemin: Path = CHEMIN_ARCHIVE,
                maintenant: datetime | None = None) -> dict[str, Any]:
    """Copie les préfixes du bucket dans l'archive ; rend le manifeste écrit."""
    if s3 is None:
        import boto3
        s3 = boto3.client("s3")
    fichiers, entrees = [], []
    for objet in lister_objets(s3, bucket):
        contenu = s3.get_object(Bucket=bucket, Key=objet["Key"])["Body"].read()
        json.loads(contenu)  # un fichier illisible est signalé ici, pas à la relecture
        fichiers.append((objet["Key"], contenu, objet["LastModified"]))
        entrees.append({"fichier": objet["Key"], "date_s3": objet["LastModified"].isoformat(),
                        "octets": len(contenu), "sha256": hashlib.sha256(contenu).hexdigest()})
    lu_le = (maintenant or datetime.now(timezone.utc)).replace(microsecond=0)
    manifeste = {
        "description": "Copie, en lecture seule, des procès archivés par la Lambda du Tribunal dans S3 (#191).",
        "bucket": bucket,
        "lu_le": lu_le.isoformat(),
        "nombre_par_prefixe": {p: sum(e["fichier"].startswith(p) for e in entrees) for p in PREFIXES},
        "fichiers": entrees,
    }
    ecrire_archive(fichiers, manifeste, chemin)
    return manifeste


def lire_archive(chemin: Path = CHEMIN_ARCHIVE) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Le manifeste et le contenu de chaque fichier, par clé S3 ; vérifie chaque empreinte."""
    with tarfile.open(chemin, mode="r:gz") as tar:
        contenus = {membre.name: tar.extractfile(membre).read() for membre in tar.getmembers() if membre.isfile()}
    manifeste = json.loads(contenus.pop(MANIFESTE))
    for entree in manifeste["fichiers"]:
        if hashlib.sha256(contenus[entree["fichier"]]).hexdigest() != entree["sha256"]:
            raise ValueError(f"Empreinte différente pour {entree['fichier']} : archive altérée")
    return manifeste, contenus


def traces_archivees(chemin: Path = CHEMIN_ARCHIVE) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Contrats de ``traces/`` par identifiant (comme ``lire_traces_s3``), et le manifeste."""
    manifeste, contenus = lire_archive(chemin)
    contrats = {cle.rsplit("/", 1)[-1][:-5]: json.loads(contenu)
                for cle, contenu in sorted(contenus.items()) if cle.startswith("traces/")}
    return contrats, manifeste


def main(arguments: list[str]) -> int:
    if arguments:
        print("Usage : python -m validation.archive_proces   (identifiants de aws login)")
        return 2
    from validation.evaluation_orchestrateur import nom_bucket_projet
    bucket = nom_bucket_projet()
    manifeste = sauvegarder(bucket)
    taille = CHEMIN_ARCHIVE.stat().st_size / 1024
    print(f"{len(manifeste['fichiers'])} fichiers de s3://{bucket} → {CHEMIN_ARCHIVE.relative_to(RACINE)} "
          f"({taille:.0f} Ko) : {manifeste['nombre_par_prefixe']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
