"""Héberge l'interface (``frontend/``) sur S3 privé + CloudFront, en HTTPS (#135). Idempotent.

Étapes, chacune sautée si elle est déjà en place :
1. **S3** : bucket dédié ``alphaforge-site-<compte>``, accès public bloqué. Ce n'est pas le
   bucket des données, qui contient les traces, les verdicts et les profils ;
2. **CloudFront** : contrôle d'accès à l'origine (OAC) ``alphaforge-interface``, puis la
   distribution repérée par son commentaire ``alphaforge-interface`` (jamais une deuxième) :
   origine S3 par l'OAC, ``index.html`` à la racine, HTTP → HTTPS, compression,
   ``PriceClass_100``, et les erreurs 403 et 404 renvoyées vers ``/index.html`` avec le
   statut 200 (l'interface utilise ``BrowserRouter`` : recharger ``/robert/tribunal`` doit
   marcher) ;
3. **politique du bucket** : lecture (``s3:GetObject``) par cette distribution seulement ;
4. **construction** : ``npm run build``, avec l'adresse de la Function URL lue sur le compte
   (``VITE_API_URL``, jamais écrite dans le dépôt) et le mode direct par défaut (#137) ;
5. **envoi** de ``frontend/dist/`` : seuls les fichiers modifiés partent (ETag = MD5),
   ``Content-Type`` selon l'extension, ``assets/*`` (noms hachés par Vite) en cache d'un an,
   tout le reste en ``no-cache`` ; les fichiers qui ne sont plus dans ``dist/`` sont supprimés ;
6. **invalidation** de ``/``, ``/index.html`` et ``/proces-verbaux/*`` si un fichier hors
   ``assets/`` a changé, puis l'adresse du site.

Aucune clé : les identifiants viennent de ``aws login``. Réglages et raisons :
``deploiement/README.md``, section « Interface hébergée ».

Usage (depuis la racine du dépôt) ::

    .venv\\Scripts\\python -X utf8 deploiement\\deployer_interface.py              # mode direct
    .venv\\Scripts\\python -X utf8 deploiement\\deployer_interface.py --mode demo  # procès enregistrés
    .venv\\Scripts\\python -X utf8 deploiement\\deployer_interface.py --sans-construction --forcer
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deployer import (  # noqa: E402
    COMMENTAIRE_INTERFACE,
    FONCTION,
    REGION,
    preparer_bucket,
    trouver_distribution_interface,
)
from construire_zip import RACINE  # noqa: E402

FRONTEND = RACINE / "frontend"
DIST = FRONTEND / "dist"
# Repère la distribution : une seule, jamais recréée. deployer.py le lit aussi pour le CORS (#136).
COMMENTAIRE = COMMENTAIRE_INTERFACE
NOM_OAC = "alphaforge-interface"
ID_ORIGINE = "site-s3"
# Politiques gérées par AWS (identifiants publics et fixes, vérifiés sur le compte le 2026-11-15).
CACHE_OPTIMISE = "658327ea-f89d-4fab-a63d-7e88639e58f6"  # Managed-CachingOptimized
EN_TETES_SECURITE = "67f7725c-6f97-4210-82d7-5512b31e9d03"  # Managed-SecurityHeadersPolicy
CACHE_IMMUABLE = "public, max-age=31536000, immutable"
SANS_CACHE = "no-cache"
CHEMINS_A_INVALIDER = ["/", "/index.html", "/proces-verbaux/*"]
# Types explicites : sous Windows, mimetypes lit le registre, qui peut donner « text/plain » pour .js.
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
}


def nom_bucket_site(compte: str) -> str:
    return f"alphaforge-site-{compte}"


# --- 2. CloudFront ---------------------------------------------------------------------


def assurer_oac(cf) -> str:
    """Contrôle d'accès à l'origine : CloudFront signe ses lectures S3 (SigV4)."""
    for oac in cf.list_origin_access_controls()["OriginAccessControlList"].get("Items", []):
        if oac["Name"] == NOM_OAC:
            print(f"CloudFront : OAC {NOM_OAC} déjà présent")
            return oac["Id"]
    oac = cf.create_origin_access_control(OriginAccessControlConfig={
        "Name": NOM_OAC,
        "Description": "Lecture du bucket de l'interface par CloudFront seulement (#135)",
        "SigningProtocol": "sigv4",
        "SigningBehavior": "always",
        "OriginAccessControlOriginType": "s3",
    })["OriginAccessControl"]
    print(f"CloudFront : OAC {NOM_OAC} créé")
    return oac["Id"]


def config_distribution(bucket: str, oac_id: str, reference: str) -> dict:
    """Configuration voulue de la distribution (``reference`` : CallerReference, à la création)."""
    return {
        "CallerReference": reference,
        "Comment": COMMENTAIRE,
        "Enabled": True,
        "DefaultRootObject": "index.html",
        "PriceClass": "PriceClass_100",  # Amérique du Nord et Europe : le jury est à Montréal
        "HttpVersion": "http2and3",
        "IsIPV6Enabled": True,
        "Origins": {"Quantity": 1, "Items": [{
            "Id": ID_ORIGINE,
            "DomainName": f"{bucket}.s3.{REGION}.amazonaws.com",
            "OriginAccessControlId": oac_id,
            "S3OriginConfig": {"OriginAccessIdentity": ""},  # vide : l'OAC remplace l'ancien OAI
        }]},
        "DefaultCacheBehavior": {
            "TargetOriginId": ID_ORIGINE,
            "ViewerProtocolPolicy": "redirect-to-https",
            "Compress": True,
            "CachePolicyId": CACHE_OPTIMISE,
            "ResponseHeadersPolicyId": EN_TETES_SECURITE,
            "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"],
                               "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
        },
        # BrowserRouter : une page profonde n'existe pas dans le bucket. Sans ListBucket, S3
        # répond 403 (pas 404) pour un objet absent : les deux renvoient l'interface, statut 200.
        # Rien n'est mis en cache (TTL 0) : après un déploiement, la page profonde suit index.html.
        "CustomErrorResponses": {"Quantity": 2, "Items": [
            {"ErrorCode": code, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0}
            for code in (403, 404)
        ]},
    }


CLES_GEREES = ("Comment", "Enabled", "DefaultRootObject", "PriceClass", "HttpVersion", "IsIPV6Enabled",
               "Origins", "DefaultCacheBehavior", "CustomErrorResponses")


def resume_reglages(config: dict) -> dict:
    """Les réglages que ce script gère, sous une forme comparable entre la configuration voulue
    et celle que renvoie AWS (qui ajoute ses valeurs par défaut partout)."""
    origine = config["Origins"]["Items"][0]
    comportement = config["DefaultCacheBehavior"]
    erreurs = config.get("CustomErrorResponses", {}).get("Items", [])
    return {
        "origine": (origine["DomainName"], origine.get("OriginAccessControlId")),
        "racine": config.get("DefaultRootObject"),
        "https": comportement.get("ViewerProtocolPolicy"),
        "compression": comportement.get("Compress"),
        "cache": comportement.get("CachePolicyId"),
        "en_tetes": comportement.get("ResponseHeadersPolicyId"),
        "erreurs": sorted((e["ErrorCode"], e.get("ResponsePagePath"), str(e.get("ResponseCode")),
                           e.get("ErrorCachingMinTTL")) for e in erreurs),
        "prix": config.get("PriceClass"),
        "http": config.get("HttpVersion"),
        "active": config.get("Enabled"),
    }


def assurer_distribution(cf, bucket: str, oac_id: str) -> dict:
    """Crée la distribution si elle manque, ou remet ses réglages si quelqu'un les a changés.

    Renvoie ``{"Id", "ARN", "DomainName", "Status"}``.
    """
    existante = trouver_distribution_interface(cf)
    if existante is None:
        config = config_distribution(bucket, oac_id, reference=f"{COMMENTAIRE}-{int(time.time())}")
        creee = cf.create_distribution(DistributionConfig=config)["Distribution"]
        print(f"CloudFront : distribution {creee['Id']} créée (déploiement : de 5 à 15 min)")
        return {cle: creee[cle] for cle in ("Id", "ARN", "DomainName", "Status")}

    reponse = cf.get_distribution_config(Id=existante["Id"])
    actuelle = reponse["DistributionConfig"]
    voulue = config_distribution(bucket, oac_id, reference=actuelle["CallerReference"])
    if resume_reglages(actuelle) == resume_reglages(voulue):
        print(f"CloudFront : distribution {existante['Id']} déjà en place")
    else:
        corrigee = {**actuelle, **{cle: voulue[cle] for cle in CLES_GEREES}}
        cf.update_distribution(Id=existante["Id"], IfMatch=reponse["ETag"], DistributionConfig=corrigee)
        print(f"CloudFront : distribution {existante['Id']} remise aux réglages du dépôt")
    return {cle: existante[cle] for cle in ("Id", "ARN", "DomainName", "Status")}


# --- 3. Politique du bucket ------------------------------------------------------------


def politique_bucket(bucket: str, arn_distribution: str) -> dict:
    """Lecture seule, par cette distribution seulement (condition ``AWS:SourceArn``)."""
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "LectureParLaDistributionDeLInterface",
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{bucket}/*",
            "Condition": {"StringEquals": {"AWS:SourceArn": arn_distribution}},
        }],
    }


def appliquer_politique_bucket(s3, bucket: str, arn_distribution: str) -> None:
    voulue = politique_bucket(bucket, arn_distribution)
    try:
        if json.loads(s3.get_bucket_policy(Bucket=bucket)["Policy"]) == voulue:
            print("S3 : politique du bucket déjà en place (lecture par la distribution seulement)")
            return
    except ClientError as erreur:
        if erreur.response["Error"]["Code"] != "NoSuchBucketPolicy":
            raise
    s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(voulue))
    print("S3 : politique du bucket appliquée (lecture par la distribution seulement)")


# --- 4. Construction -------------------------------------------------------------------


def adresse_function_url(lam) -> str | None:
    """Adresse de la Function URL, lue sur le compte (comme ``tester_function_url.py``)."""
    try:
        return lam.get_function_url_config(FunctionName=FONCTION)["FunctionUrl"].rstrip("/")
    except lam.exceptions.ResourceNotFoundException:
        return None


def variables_construction(url_api: str | None, mode: str) -> dict[str, str]:
    """Variables Vite du site : mode direct (Lambda) ou démonstration (procès enregistrés).

    En démonstration, l'adresse reste utile : « Trompez le Greffier » appelle ``/verifier``.
    """
    if mode == "direct" and not url_api:
        raise SystemExit(f"Mode direct impossible : la Function URL de {FONCTION} est introuvable. "
                         "Déployez d'abord la Lambda (deployer.py), ou construisez avec --mode demo.")
    variables = {"VITE_USE_MOCKS": "false" if mode == "direct" else "true"}
    if url_api:
        variables["VITE_API_URL"] = url_api
    return variables


def construire_interface(variables: dict[str, str]) -> None:
    """``npm ci`` si besoin, puis ``npm run build``. Les variables du processus passent avant
    ``frontend/.env.local`` (règle de Vite) : la configuration locale de chacun n'entre pas."""
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm est introuvable : installez Node.js.")
    environnement = {**os.environ, **variables}
    if not (FRONTEND / "node_modules").exists():
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True, env=environnement)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True, env=environnement)
    resume = ", ".join(f"{cle}={'<Function URL>' if cle == 'VITE_API_URL' else valeur}"
                       for cle, valeur in variables.items())
    print(f"Interface construite ({resume})")


# --- 5. Envoi --------------------------------------------------------------------------


def en_tetes(cle: str) -> dict[str, str]:
    """``Content-Type`` selon l'extension ; cache d'un an pour les fichiers hachés par Vite."""
    extension = Path(cle).suffix.lower()
    type_contenu = TYPES.get(extension) or mimetypes.guess_type(cle)[0] or "application/octet-stream"
    cache = CACHE_IMMUABLE if cle.startswith("assets/") else SANS_CACHE
    return {"ContentType": type_contenu, "CacheControl": cache}


def fichiers_locaux(dossier: Path) -> dict[str, Path]:
    """Clé S3 (chemin relatif, avec des /) → fichier de ``dist/``."""
    return {f.relative_to(dossier).as_posix(): f for f in sorted(dossier.rglob("*")) if f.is_file()}


def etags_distants(s3, bucket: str) -> dict[str, str]:
    etags = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for objet in page.get("Contents", []):
            etags[objet["Key"]] = objet["ETag"].strip('"')
    return etags


def envoyer_site(s3, bucket: str, dossier: Path, forcer: bool = False) -> dict[str, list[str]]:
    """Synchronise ``dossier`` avec le bucket. Renvoie les clés envoyées, inchangées, supprimées.

    ``index.html`` part en dernier : il ne désigne jamais un fichier pas encore envoyé.
    """
    locaux = fichiers_locaux(dossier)
    if "index.html" not in locaux:
        raise SystemExit(f"{dossier} ne contient pas index.html : lancez la construction.")
    distants = etags_distants(s3, bucket)
    bilan: dict[str, list[str]] = {"envoyes": [], "inchanges": [], "supprimes": []}
    for cle in sorted(locaux, key=lambda c: c == "index.html"):
        contenu = locaux[cle].read_bytes()
        if not forcer and distants.get(cle) == hashlib.md5(contenu).hexdigest():
            bilan["inchanges"].append(cle)
            continue
        s3.put_object(Bucket=bucket, Key=cle, Body=contenu, **en_tetes(cle))
        bilan["envoyes"].append(cle)
    obsoletes = sorted(set(distants) - set(locaux))
    for debut in range(0, len(obsoletes), 1000):  # delete_objects : 1000 clés au plus par appel
        lot = obsoletes[debut:debut + 1000]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": cle} for cle in lot], "Quiet": True})
    bilan["supprimes"] = obsoletes
    print(f"S3 : {len(bilan['envoyes'])} fichiers envoyés, {len(bilan['inchanges'])} inchangés, "
          f"{len(obsoletes)} supprimés")
    return bilan


# --- 6. Invalidation -------------------------------------------------------------------


def chemins_a_invalider(bilan: dict[str, list[str]]) -> list[str]:
    """Les fichiers hachés (``assets/``) changent de nom à chaque modification : seul un
    changement ailleurs (``index.html``, procès-verbaux…) demande une invalidation."""
    modifies = bilan["envoyes"] + bilan["supprimes"]
    return CHEMINS_A_INVALIDER if any(not cle.startswith("assets/") for cle in modifies) else []


def invalider(cf, distribution_id: str, chemins: list[str]) -> None:
    if not chemins:
        print("CloudFront : rien à invalider (index.html et procès-verbaux inchangés)")
        return
    cf.create_invalidation(DistributionId=distribution_id, InvalidationBatch={
        "Paths": {"Quantity": len(chemins), "Items": chemins},
        "CallerReference": f"{COMMENTAIRE}-{time.time_ns()}",
    })
    print(f"CloudFront : invalidation de {', '.join(chemins)}")


def origine_autorisee(lam, origine: str) -> bool:
    """La Function URL accepte-t-elle les appels du navigateur depuis le site (CORS) ?"""
    try:
        cors = lam.get_function_url_config(FunctionName=FONCTION).get("Cors", {})
    except lam.exceptions.ResourceNotFoundException:
        return False
    return origine in cors.get("AllowOrigins", [])


def lire_options(arguments: list[str] | None = None) -> argparse.Namespace:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--mode", choices=["direct", "demo"], default="direct",
                         help="mode de l'interface construite : direct (Lambda, par défaut) ou demo "
                              "(procès enregistrés)")
    lecteur.add_argument("--sans-construction", action="store_true",
                         help="envoyer frontend/dist/ tel quel, sans npm run build")
    lecteur.add_argument("--forcer", action="store_true",
                         help="renvoyer tous les fichiers, même inchangés (après un changement des en-têtes)")
    lecteur.add_argument("--attendre", action="store_true",
                         help="attendre que la distribution soit déployée")
    return lecteur.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = lire_options(arguments)
    session = boto3.Session(region_name=REGION)
    s3, cf, lam = session.client("s3"), session.client("cloudfront"), session.client("lambda")
    bucket = nom_bucket_site(session.client("sts").get_caller_identity()["Account"])

    preparer_bucket(s3, bucket)
    distribution = assurer_distribution(cf, bucket, assurer_oac(cf))
    appliquer_politique_bucket(s3, bucket, distribution["ARN"])
    url_api = adresse_function_url(lam)
    if not options.sans_construction:
        construire_interface(variables_construction(url_api, options.mode))
    invalider(cf, distribution["Id"], chemins_a_invalider(envoyer_site(s3, bucket, DIST, options.forcer)))

    site = f"https://{distribution['DomainName']}"
    if url_api and not origine_autorisee(lam, site):
        print(f"Attention : le CORS de la Function URL n'autorise pas {site} : le site ne peut pas "
              "appeler la Lambda (procès en direct, « Trompez le Greffier »). Pour l'ajouter (le domaine "
              "est lu sur le compte, #136) :\n"
              "  .venv\\Scripts\\python -X utf8 deploiement\\deployer.py --url-seulement")
    if options.attendre:
        print("CloudFront : attente du déploiement de la distribution…")
        cf.get_waiter("distribution_deployed").wait(Id=distribution["Id"])
        distribution["Status"] = "Deployed"
    etat = "" if distribution["Status"] == "Deployed" else " (distribution en cours de déploiement)"
    print(f"Site : {site}{etat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
