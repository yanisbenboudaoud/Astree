"""Lance un procès sur la Lambda déployée, par sa Function URL (#22).

Ce script signe la requête (SigV4) avec les identifiants de ``aws login``, puis affiche
le statut HTTP, la durée et un résumé du contrat. La signature était obligatoire quand
la Function URL était en ``AWS_IAM`` ; depuis #14 elle est en ``NONE`` (appelée par
l'interface) et une requête signée reste acceptée.

L'adresse n'est pas écrite dans le dépôt : elle est lue sur le compte
(``get_function_url_config``).

Usage (depuis la racine du dépôt) ::

    .venv\\Scripts\\python -X utf8 deploiement\\tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla"
    .venv\\Scripts\\python -X utf8 deploiement\\tester_function_url.py amira "…" --sortie contrat.json
    .venv\\Scripts\\python -X utf8 deploiement\\tester_function_url.py robert "…" --calibrage-demo   # Pacte vécu (#68)
    .venv\\Scripts\\python -X utf8 deploiement\\tester_function_url.py --creer-profil docs\\exemples\\reponses_questionnaire.json "Je veux mettre 30 % en Tesla"   # #87

``--creer-profil`` envoie d'abord le fichier de réponses à ``/profil`` (sans Bedrock),
puis fait le procès du profil créé, rangé dans ``profils/<id>.json`` du bucket.

Chaque appel fait un vrai procès : quelques appels Bedrock payants.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from pipeline.agent_profil import chemin_profil  # noqa: E402
from pipeline.calibrage import reponses_demo  # noqa: E402
from pipeline.pacte import charger_pacte  # noqa: E402

REGION = "us-east-1"
FONCTION = "alphaforge-tribunal"
DELAI_CLIENT_S = 900  # la Lambda coupe elle-même à 300 s


def adresse_function_url(fonction: str) -> str:
    """Adresse de la Function URL, lue sur le compte AWS."""
    config = boto3.client("lambda", region_name=REGION).get_function_url_config(FunctionName=fonction)
    return config["FunctionUrl"].rstrip("/")


def envoyer(url: str, corps: dict) -> tuple[int, float, bytes, str | None]:
    """POST signé ; renvoie (statut HTTP, durée en s, corps de la réponse, identifiant du procès)."""
    donnees = json.dumps(corps).encode("utf-8")
    requete = AWSRequest(method="POST", url=url, data=donnees,
                         headers={"Content-Type": "application/json"})
    identifiants = boto3.Session().get_credentials().get_frozen_credentials()
    SigV4Auth(identifiants, "lambda", REGION).add_auth(requete)

    http = urllib.request.Request(url, data=donnees, headers=dict(requete.headers), method="POST")
    debut = time.perf_counter()
    try:
        with urllib.request.urlopen(http, timeout=DELAI_CLIENT_S) as reponse:
            statut, contenu, en_tetes = reponse.status, reponse.read(), reponse.headers
    except urllib.error.HTTPError as erreur:
        statut, contenu, en_tetes = erreur.code, erreur.read(), erreur.headers
    # Les en-têtes de la réponse sont lus sans tenir compte de la casse.
    return statut, time.perf_counter() - debut, contenu, en_tetes.get("X-Proces-Id")


def resumer(contenu: bytes) -> str:
    """Pièces, outils choisis par l'orchestrateur et arguments rejetés, ou le message d'erreur."""
    try:
        contrat = json.loads(contenu)
    except json.JSONDecodeError:
        return f"réponse illisible : {contenu[:300]!r}"
    if "erreur" in contrat:
        return f"erreur : {contrat['erreur']}"
    outils = [etape["outil"] for etape in contrat["trace"] if etape["etape"] == "orchestrateur"]
    return (
        f"décision : {contrat['decision']['libelle'] if contrat.get('decision') else 'aucune'}\n"
        f"pièces : {len(contrat['pieces'])} · outils de l'orchestrateur : {', '.join(outils)}\n"
        f"arguments : {len(contrat['requisitoire'])} contre, {len(contrat['plaidoirie'])} pour, "
        f"{len(contrat['arguments_rejetes'])} rejetés"
    )


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("profil", nargs="?", help="identifiant du profil, ex. : robert (sauf avec --creer-profil)")
    lecteur.add_argument("demande", help="la décision à juger, en une phrase")
    lecteur.add_argument("--creer-profil", type=Path, metavar="REPONSES",
                         help="crée d'abord le profil par /profil (fichier de réponses du questionnaire, #87)")
    lecteur.add_argument("--fonction", default=FONCTION, help=f"nom de la Lambda ({FONCTION})")
    lecteur.add_argument("--sortie", type=Path, help="fichier où écrire la réponse JSON")
    lecteur.add_argument("--calibrage-demo", action="store_true",
                         help="envoie les réponses préenregistrées du Pacte vécu du profil (#68)")
    lecteur.add_argument("--verdict", choices=["maintenu", "modifie", "pacte_ajuste"],
                         help="envoie aussi ce verdict à /verdict pour le procès archivé (#13)")
    options = lecteur.parse_args(arguments)

    if (options.profil is None) == (options.creer_profil is None):
        lecteur.error("indiquez un identifiant de profil, ou --creer-profil REPONSES, pas les deux")

    adresse = adresse_function_url(options.fonction)
    if options.creer_profil:
        saisie = json.loads(options.creer_profil.read_text(encoding="utf-8"))
        demande_profil = {"reponses": saisie["reponses"], "capital": saisie["capital_cad"],
                          "portefeuille": saisie["portefeuille"], "nom": saisie.get("nom", "Investisseur")}
        statut, duree, contenu, _ = envoyer(f"{adresse}/profil", demande_profil)
        reponse = json.loads(contenu)
        print(f"/profil : HTTP {statut} en {duree:.1f} s · {reponse.get('archive') or reponse}")
        if statut != 201:
            return 1
        options.profil = reponse["id"]
    corps = {"profil": options.profil, "demande": options.demande}
    if options.calibrage_demo:
        corps["calibrage"] = {"reponses": reponses_demo(charger_pacte(chemin_profil(options.profil)))[0]}
    statut, duree, contenu, identifiant = envoyer(f"{adresse}/tribunal", corps)
    print(f"HTTP {statut} en {duree:.1f} s · procès archivé : {identifiant or 'non'}")
    print(resumer(contenu))
    if options.sortie:
        options.sortie.write_bytes(contenu)
        print(f"Réponse écrite dans {options.sortie}")
    if statut != 200:
        return 1
    if options.verdict and identifiant:
        statut, duree, contenu, _ = envoyer(f"{adresse}/verdict", {"id": identifiant, "verdict": options.verdict})
        print(f"/verdict : HTTP {statut} en {duree:.1f} s · {contenu.decode('utf-8')}")
        return 0 if statut == 200 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
