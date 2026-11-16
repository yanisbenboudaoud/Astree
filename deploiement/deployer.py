"""Déploie ou met à jour le Tribunal sur AWS (#13). Idempotent : à relancer après chaque fusion.

Étapes, chacune sautée si la ressource est déjà dans l'état voulu :
1. **S3** : bucket ``alphaforge-<compte>`` (créé s'il manque, accès public bloqué) ;
   les CSV de ``alphaforge_starter/`` envoyés dans ``donnees/`` ;
2. **Guardrail Bedrock** ``alphaforge-cadre-simulation`` (#189) : créé s'il manque ; une
   version publiée seulement si sa configuration a changé (empreinte dans la description) ;
   **IAM** : rôle ``alphaforge-lambda`` (créé s'il manque), avec la politique minimale
   ``politique_iam_lambda.json`` appliquée à ce bucket et à ce Guardrail ;
3. **Lambda** ``alphaforge-tribunal`` : créée, ou code et configuration mis à jour
   (python3.14, couche pandas, 300 s, 1024 Mo, variables d'environnement) ;
4. **concurrence réservée** de 2 (coûts Bedrock) ; **invocation asynchrone** (procès lancé
   en arrière-plan, #90) sans relance automatique et abandonnée après 60 s d'attente ;
5. **Function URL** : créée si elle manque, en ``NONE`` (un navigateur ne sait pas signer
   une requête AWS) avec un **CORS limité aux origines de l'interface** (#14) et la
   permission publique que Lambda exige : ``lambda:InvokeFunctionUrl`` et
   ``lambda:InvokeFunction`` seulement par la Function URL. Les origines sont
   ``http://localhost:5173``, le site hébergé (distribution CloudFront ``alphaforge-interface``,
   lue sur le compte à chaque lancement, #136) et les ``--origine``.

Les paramètres sont ceux vérifiés dans #22 (``deploiement/README.md``). Aucune clé :
les identifiants viennent de ``aws login``.

Usage (depuis la racine du dépôt) ::

    .venv\\Scripts\\python -X utf8 deploiement\\deployer.py              # construit le zip puis déploie
    .venv\\Scripts\\python -X utf8 deploiement\\deployer.py --sans-donnees
    .venv\\Scripts\\python -X utf8 deploiement\\deployer.py --url-seulement   # étape 5 seule
    .venv\\Scripts\\python -X utf8 deploiement\\deployer.py --url-seulement --origine http://localhost:5175
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from construire_zip import RACINE, construire  # noqa: E402

REGION = "us-east-1"
FONCTION = "alphaforge-tribunal"
ROLE = "alphaforge-lambda"
COUCHE_PANDAS = "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python314:12"
MODELE = "global.anthropic.claude-sonnet-5-5"
CONCURRENCE_RESERVEE = 2
# Procès lancé en arrière-plan (#90). Aucune relance : un procès raté ne doit pas se rejouer
# seul (nouveaux appels Bedrock). Un procès qui ne peut pas démarrer en 60 s (deux procès en
# cours) est abandonné, plutôt que de tourner quand l'interface a cessé d'attendre.
INVOCATION_ASYNCHRONE = {"MaximumRetryAttempts": 0, "MaximumEventAgeInSeconds": 60}
CONFIGURATION = {
    "Runtime": "python3.14",
    "Handler": "lambda_tribunal.handler",
    "Timeout": 300,
    "MemorySize": 1024,
    "Layers": [COUCHE_PANDAS],
}
# Origines autorisées à appeler la Function URL depuis un navigateur (#14) : l'interface en
# local (npm run dev). Le site hébergé (#135) s'y ajoute, lu sur le compte (origines_cors, #136).
ORIGINES_INTERFACE = ["http://localhost:5173"]
COMMENTAIRE_INTERFACE = "alphaforge-interface"  # repère la distribution CloudFront du site (#135)
STATEMENT_URL = "function-url-publique"
STATEMENT_INVOCATION = "function-url-publique-invocation"
GARDE_FOU = "alphaforge-cadre-simulation"
# Guardrail (#189) : un second regard, en plus du Greffier Python, sur le cadre « simulation
# seulement ». Entrée (demande, question) : attaque de consigne. Sortie (chaque argument
# affiché) : sujet refusé « conseil personnalisé ». Le sujet ne filtre pas l'entrée : une
# demande de conseil reçoit au contre-interrogatoire une réponse qui dit que le Tribunal ne
# conseille pas. Les noms de sujets n'acceptent pas les accents.
CONFIG_GARDE_FOU = {
    "description": "Tribunal AlphaForge : aucun conseil personnalise ni promesse de rendement (#189)",
    "topicPolicyConfig": {"topicsConfig": [{
        "name": "Conseil personnalise",
        "definition": ("Recommandation adressee a l'investisseur d'acheter, vendre ou conserver un placement, "
                       "ou promesse d'un rendement ou d'un prix futur."),
        "examples": ["Vous devriez vendre vos actions Tesla.", "Achetez du Bitcoin maintenant.",
                     "Cette action va doubler l'an prochain.", "Je vous recommande d'alleger votre position."],
        "type": "DENY",
        "inputEnabled": False,
        "outputEnabled": True,
    }]},
    "contentPolicyConfig": {"filtersConfig": [
        {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
    ]},
    "blockedInputMessaging": "Demande refusee par le garde-fou du Tribunal.",
    "blockedOutputsMessaging": "Argument refuse par le garde-fou du Tribunal.",
}
ROUTES = "/tribunal, /progression, /verdict, /question, /verifier, /proces-verbal, /questionnaire, /profil, /table"  # lambda_tribunal.ROUTES
CONFIANCE_LAMBDA = {
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
}


def nom_bucket(compte: str) -> str:
    return f"alphaforge-{compte}"


def politique_pour_bucket(bucket: str, garde_fou_arn: str) -> str:
    """La politique minimale du dépôt, avec le nom réel du bucket et l'ARN du Guardrail."""
    texte = (RACINE / "deploiement" / "politique_iam_lambda.json").read_text(encoding="utf-8")
    return json.dumps(json.loads(texte.replace("NOM_DU_BUCKET", bucket).replace("ARN_DU_GARDE_FOU", garde_fou_arn)))


def variables_environnement(bucket: str, garde_fou: tuple[str, str]) -> dict[str, str]:
    # AWS_REGION n'est pas définie ici : Lambda la fournit elle-même.
    identifiant, version = garde_fou
    return {"SOURCE_DONNEES": "s3", "BUCKET_PROJET": bucket, "BEDROCK_MODEL_ID": MODELE,
            "BEDROCK_GUARDRAIL_ID": identifiant, "BEDROCK_GUARDRAIL_VERSION": version}


# --- 1. S3 -------------------------------------------------------------------------


def preparer_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"S3 : bucket {bucket} déjà présent")
    except ClientError:
        s3.create_bucket(Bucket=bucket)  # us-east-1 : pas de LocationConstraint
        print(f"S3 : bucket {bucket} créé")
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True,
        "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
    })


def envoyer_donnees(s3, bucket: str) -> None:
    fichiers = sorted((RACINE / "alphaforge_starter").glob("*.csv"))
    for fichier in fichiers:
        s3.upload_file(str(fichier), bucket, f"donnees/{fichier.name}")
    print(f"S3 : {len(fichiers)} CSV envoyés dans s3://{bucket}/donnees/")


# --- 2. Guardrail Bedrock et IAM ---------------------------------------------------


def empreinte_garde_fou() -> str:
    """Empreinte de ``CONFIG_GARDE_FOU`` : une nouvelle version n'est publiée que si elle change."""
    return hashlib.sha256(json.dumps(CONFIG_GARDE_FOU, sort_keys=True).encode()).hexdigest()[:12]


def assurer_garde_fou(bedrock) -> tuple[str, str, str]:
    """Crée ou met à jour le Guardrail, puis renvoie (identifiant, version publiée, ARN).

    Idempotent : la version publiée porte l'empreinte de la configuration dans sa description ;
    si la dernière version l'a déjà, rien n'est modifié.
    """
    empreinte = f"config {empreinte_garde_fou()}"
    existant = next((g for g in bedrock.list_guardrails()["guardrails"] if g["name"] == GARDE_FOU), None)
    if existant is None:
        cree = bedrock.create_guardrail(name=GARDE_FOU, **CONFIG_GARDE_FOU)
        identifiant, arn = cree["guardrailId"], cree["guardrailArn"]
        print(f"Bedrock : Guardrail {GARDE_FOU} créé")
    else:
        identifiant, arn = existant["id"], existant["arn"]
    versions = [v for v in bedrock.list_guardrails(guardrailIdentifier=identifiant)["guardrails"]
                if v["version"] != "DRAFT"]
    derniere = max(versions, key=lambda v: int(v["version"]), default=None)
    if derniere is not None and derniere.get("description") == empreinte:
        print(f"Bedrock : Guardrail {GARDE_FOU} déjà à jour (version {derniere['version']})")
        return identifiant, derniere["version"], arn
    if existant is not None:
        bedrock.update_guardrail(guardrailIdentifier=identifiant, name=GARDE_FOU, **CONFIG_GARDE_FOU)
    version = bedrock.create_guardrail_version(guardrailIdentifier=identifiant, description=empreinte)["version"]
    print(f"Bedrock : Guardrail {GARDE_FOU}, version {version} publiée")
    return identifiant, version, arn


def preparer_role(iam, bucket: str, garde_fou_arn: str) -> str:
    try:
        arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
        print(f"IAM : rôle {ROLE} déjà présent")
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(CONFIANCE_LAMBDA),
                              Description="Lambda du Tribunal AlphaForge (#13)")["Role"]["Arn"]
        print(f"IAM : rôle {ROLE} créé")
        time.sleep(10)  # le temps que le nouveau rôle soit visible par Lambda
    iam.put_role_policy(RoleName=ROLE, PolicyName=ROLE, PolicyDocument=politique_pour_bucket(bucket, garde_fou_arn))
    print("IAM : politique minimale appliquée (Bedrock Sonnet 5.5 sur 3 régions, Guardrail du projet, CloudWatch, "
          "bucket, invocation de la fonction elle-même)")
    return arn


# --- 3 à 5. Lambda -----------------------------------------------------------------


def deployer_fonction(lam, code: bytes, role_arn: str, bucket: str, garde_fou: tuple[str, str]) -> None:
    configuration = {**CONFIGURATION, "Environment": {"Variables": variables_environnement(bucket, garde_fou)}}
    try:
        lam.get_function(FunctionName=FONCTION)
    except lam.exceptions.ResourceNotFoundException:
        lam.create_function(FunctionName=FONCTION, Role=role_arn, Code={"ZipFile": code},
                            Architectures=["x86_64"], **configuration)
        lam.get_waiter("function_active_v2").wait(FunctionName=FONCTION)
        print(f"Lambda : {FONCTION} créée")
        return
    lam.update_function_code(FunctionName=FONCTION, ZipFile=code)
    lam.get_waiter("function_updated_v2").wait(FunctionName=FONCTION)
    lam.update_function_configuration(FunctionName=FONCTION, Role=role_arn, **configuration)
    lam.get_waiter("function_updated_v2").wait(FunctionName=FONCTION)
    print(f"Lambda : {FONCTION} mise à jour (code et configuration)")


def regler_concurrence(lam) -> None:
    lam.put_function_concurrency(FunctionName=FONCTION, ReservedConcurrentExecutions=CONCURRENCE_RESERVEE)
    print(f"Lambda : concurrence réservée de {CONCURRENCE_RESERVEE}")


def regler_invocation_asynchrone(lam) -> None:
    """Procès en arrière-plan (#90) : aucune relance automatique, abandon après 60 s d'attente."""
    lam.put_function_event_invoke_config(FunctionName=FONCTION, **INVOCATION_ASYNCHRONE)
    print("Lambda : invocation asynchrone sans relance, abandonnée après "
          f"{INVOCATION_ASYNCHRONE['MaximumEventAgeInSeconds']} s d'attente")


def trouver_distribution_interface(cf) -> dict | None:
    """La distribution CloudFront du site hébergé, repérée par son commentaire, ou None."""
    for page in cf.get_paginator("list_distributions").paginate():
        for distribution in page["DistributionList"].get("Items", []):
            if distribution["Comment"] == COMMENTAIRE_INTERFACE:
                return distribution
    return None


def origines_cors(cf, supplementaires: list[str]) -> list[str]:
    """Origines du CORS : l'interface locale, le site hébergé **lu sur le compte**, puis les ``--origine``.

    Lues à chaque déploiement (#136) : un redéploiement de la Lambda lancé sans ``--origine``,
    par n'importe quel membre, garde toujours le site hébergé.
    """
    origines = list(ORIGINES_INTERFACE)
    distribution = trouver_distribution_interface(cf)
    if distribution is not None:
        origines.append(f"https://{distribution['DomainName']}")
    origines += [origine.rstrip("/") for origine in supplementaires]
    return list(dict.fromkeys(origines))  # sans doublon, dans l'ordre


def cors_interface(origines: list[str]) -> dict:
    """CORS de la Function URL : POST seulement, depuis l'interface, en-tête du procès visible.

    Sans ``ExposeHeaders``, le navigateur cache ``X-Proces-Id``, nécessaire pour ``POST /verdict``.
    """
    return {
        "AllowOrigins": origines,
        "AllowMethods": ["POST"],
        "AllowHeaders": ["content-type"],
        "ExposeHeaders": ["x-proces-id"],
        "MaxAge": 300,
    }


def autoriser_appels_publics(lam) -> None:
    """Permissions d'une Function URL en ``NONE`` : les deux sont exigées par Lambda.

    La seconde ne vaut que pour les appels qui passent par la Function URL
    (``InvokedViaFunctionUrl``) : personne ne peut appeler la fonction directement.
    """
    permissions = [
        {"StatementId": STATEMENT_URL, "Action": "lambda:InvokeFunctionUrl", "FunctionUrlAuthType": "NONE"},
        {"StatementId": STATEMENT_INVOCATION, "Action": "lambda:InvokeFunction", "InvokedViaFunctionUrl": True},
    ]
    for permission in permissions:
        try:
            lam.add_permission(FunctionName=FONCTION, Principal="*", **permission)
        except lam.exceptions.ResourceConflictException:
            pass  # déjà accordée
    print("Function URL : appels publics autorisés (InvokeFunctionUrl et InvokeFunction par l'URL seulement)")


def assurer_function_url(lam, origines: list[str]) -> str:
    """Function URL en ``NONE`` avec le CORS de l'interface (créée ou mise à jour)."""
    reglages = {"AuthType": "NONE", "Cors": cors_interface(origines)}
    try:
        lam.get_function_url_config(FunctionName=FONCTION)
        config = lam.update_function_url_config(FunctionName=FONCTION, **reglages)
        print(f"Function URL : mise à jour (NONE, CORS pour {', '.join(origines)})")
    except lam.exceptions.ResourceNotFoundException:
        config = lam.create_function_url_config(FunctionName=FONCTION, **reglages)
        print(f"Function URL : créée (NONE, CORS pour {', '.join(origines)})")
    autoriser_appels_publics(lam)
    return config["FunctionUrl"]


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--zip", type=Path, help="zip déjà construit (sinon, construit maintenant)")
    lecteur.add_argument("--sans-donnees", action="store_true", help="ne pas renvoyer les CSV dans S3")
    lecteur.add_argument("--url-seulement", action="store_true",
                         help="régler seulement la Function URL (NONE, CORS), sans toucher au code")
    lecteur.add_argument("--origine", action="append", default=[],
                         help="origine de l'interface à ajouter au CORS (répétable)")
    options = lecteur.parse_args(arguments)

    session = boto3.Session(region_name=REGION)
    lam = session.client("lambda")
    origines = origines_cors(session.client("cloudfront"), options.origine)
    if options.url_seulement:
        print(f"Prêt : {assurer_function_url(lam, origines)} (routes POST : {ROUTES})")
        return 0
    bucket = nom_bucket(session.client("sts").get_caller_identity()["Account"])
    s3, iam = session.client("s3"), session.client("iam")

    preparer_bucket(s3, bucket)
    if not options.sans_donnees:
        envoyer_donnees(s3, bucket)
    garde_fou_id, garde_fou_version, garde_fou_arn = assurer_garde_fou(session.client("bedrock"))
    role_arn = preparer_role(iam, bucket, garde_fou_arn)
    zip_lambda = options.zip or construire()
    deployer_fonction(lam, zip_lambda.read_bytes(), role_arn, bucket, (garde_fou_id, garde_fou_version))
    regler_concurrence(lam)
    regler_invocation_asynchrone(lam)
    print(f"Prêt : {assurer_function_url(lam, origines)} (routes POST : {ROUTES})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
