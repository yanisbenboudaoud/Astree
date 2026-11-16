"""Preuves de l'intégration AWS, exportées avant la suppression du compte de l'événement (#191).

Le jury ne pourra pas tester : il verra ce que le dépôt garde. Ce script lit le compte en
**lecture seule** (aucune création, aucune modification, aucun appel à Bedrock) et écrit dans
``docs/preuves/aws/`` :

- un fichier JSON par service, tel que l'API le renvoie (dates comprises) ;
- ``README.md`` : le résumé lisible de chaque preuve.

Preuves : identité du compte ; Lambda (configuration, Function URL, concurrence réservée,
invocation asynchrone) ; métriques CloudWatch de la Lambda et de Bedrock pendant le Datathon
(appels, jetons, par modèle) ; journaux CloudWatch du dernier procès archivé ; contenu des buckets
S3 ; rôle IAM et ses politiques ; distribution CloudFront ; alerte de budget.

Un appel refusé par le rôle de l'atelier n'arrête rien : il est noté « à capturer dans la console ».
Les variables d'environnement dont le nom évoque un secret sont masquées.

Usage : ``python -m deploiement.preuves_aws`` (identifiants de ``aws login``, région us-east-1).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from deploiement.deployer import COMMENTAIRE_INTERFACE, FONCTION, MODELE, REGION, ROLE, nom_bucket
from deploiement.deployer_interface import nom_bucket_site

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "docs" / "preuves" / "aws"
# Le Datathon : du début du 14 novembre à la lecture.
DEBUT_EVENEMENT = datetime(2026, 11, 14, tzinfo=timezone.utc)
SECRET = re.compile(r"key|secret|token|password|mot_de_passe", re.I)
PREFIXES_PROJET = ("traces/", "verdicts/", "profils/", "progression/", "donnees/")


class Preuves:
    """Collecte les preuves ; chaque appel refusé ou en erreur est noté, sans arrêter les autres."""

    def __init__(self, session):
        self.session = session
        self.fichiers: dict[str, Any] = {}
        self.resume: list[str] = []
        self.refus: list[str] = []

    def client(self, service: str):
        return self.session.client(service, region_name=REGION)

    def lire(self, nom: str, appel: Callable[[], Any]) -> Any:
        try:
            resultat = appel()
        except Exception as erreur:  # AccessDenied du rôle de l'atelier, ressource absente…
            self.refus.append(f"`{nom}` : {type(erreur).__name__} : {str(erreur)[:160]}")
            return None
        self.fichiers[nom] = resultat
        return resultat


def _sans_metadonnees(reponse: dict) -> dict:
    return {k: v for k, v in (reponse or {}).items() if k != "ResponseMetadata"}


def _masquer_environnement(configuration: dict) -> dict:
    variables = configuration.get("Environment", {}).get("Variables", {})
    for nom in variables:
        if SECRET.search(nom):
            variables[nom] = "*** masqué ***"
    return configuration


def collecter(session, maintenant: datetime) -> Preuves:
    p = Preuves(session)
    identite = p.lire("identite", lambda: _sans_metadonnees(p.client("sts").get_caller_identity()))
    compte = identite["Account"] if identite else None

    lam = p.client("lambda")
    config = p.lire("lambda_configuration", lambda: _masquer_environnement(
        _sans_metadonnees(lam.get_function_configuration(FunctionName=FONCTION))))
    url = p.lire("lambda_function_url", lambda: _sans_metadonnees(lam.get_function_url_config(FunctionName=FONCTION)))
    concurrence = p.lire("lambda_concurrence", lambda: _sans_metadonnees(lam.get_function_concurrency(FunctionName=FONCTION)))
    asynchrone = p.lire("lambda_invocation_asynchrone",
                        lambda: _sans_metadonnees(lam.get_function_event_invoke_config(FunctionName=FONCTION)))

    cw = p.client("cloudwatch")

    def metriques(espace: str, noms: list[str], dimensions: list[dict], statistique: str = "Sum") -> dict:
        requetes = [{"Id": f"m{i}", "Label": nom, "ReturnData": True,
                     "MetricStat": {"Metric": {"Namespace": espace, "MetricName": nom, "Dimensions": dimensions},
                                    "Period": 3600, "Stat": statistique}}
                    for i, nom in enumerate(noms)]
        reponse = cw.get_metric_data(MetricDataQueries=requetes, StartTime=DEBUT_EVENEMENT, EndTime=maintenant)
        return {r["Label"]: {"total": sum(r["Values"]), "heures": len(r["Values"]),
                             "points": dict(zip((t.isoformat() for t in r["Timestamps"]), r["Values"]))}
                for r in reponse["MetricDataResults"]}

    lambda_cw = p.lire("cloudwatch_lambda", lambda: metriques(
        "AWS/Lambda", ["Invocations", "Errors", "Throttles"], [{"Name": "FunctionName", "Value": FONCTION}]))
    modeles = p.lire("cloudwatch_bedrock_modeles", lambda: sorted({
        d["Value"] for m in cw.list_metrics(Namespace="AWS/Bedrock", MetricName="Invocations")["Metrics"]
        for d in m["Dimensions"] if d["Name"] == "ModelId"}))
    bedrock = {}
    for modele in modeles or []:
        bedrock[modele] = p.lire(f"cloudwatch_bedrock::{modele}", lambda modele=modele: metriques(
            "AWS/Bedrock", ["Invocations", "InputTokenCount", "OutputTokenCount", "InvocationClientErrors"],
            [{"Name": "ModelId", "Value": modele}]))
    p.fichiers["cloudwatch_bedrock"] = bedrock
    for cle in [k for k in p.fichiers if k.startswith("cloudwatch_bedrock::")]:
        del p.fichiers[cle]

    s3 = p.client("s3")

    def inventaire(bucket: str, prefixes: tuple[str, ...] | None) -> dict:
        resultat = {}
        for prefixe in prefixes or ("",):
            objets = [o for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe)
                      for o in page.get("Contents", [])]
            dates = sorted(o["LastModified"] for o in objets)
            resultat[prefixe or "(tout)"] = {
                "objets": len(objets), "octets": sum(o["Size"] for o in objets),
                "premier": dates[0].isoformat() if dates else None, "dernier": dates[-1].isoformat() if dates else None}
        return resultat

    s3_projet = p.lire("s3_projet", lambda: {"bucket": nom_bucket(compte), **inventaire(nom_bucket(compte), PREFIXES_PROJET)}) \
        if compte else None
    s3_site = p.lire("s3_site", lambda: {"bucket": nom_bucket_site(compte), **inventaire(nom_bucket_site(compte), None)}) \
        if compte else None

    journaux = None
    if s3_projet and s3_projet.get("traces/", {}).get("objets"):
        dernier = max((o for page in s3.get_paginator("list_objects_v2").paginate(Bucket=nom_bucket(compte),
                                                                                    Prefix="traces/")
                       for o in page.get("Contents", [])), key=lambda o: o["LastModified"])
        identifiant = dernier["Key"].rsplit("/", 1)[-1][:-5]
        logs = p.client("logs")
        groupe = f"/aws/lambda/{FONCTION}"

        def evenements(liste: list[dict]) -> list[dict]:
            return [{"heure": datetime.fromtimestamp(e["timestamp"] / 1000, timezone.utc).isoformat(),
                     "message": e["message"].rstrip()[:400]} for e in liste][:60]

        def lire_journaux() -> dict | None:
            # D'abord les lignes qui citent le procès ; sinon, les dernières lignes du flux le plus récent
            # (START, REPORT avec durée et mémoire, messages du Tribunal).
            autour = logs.filter_log_events(
                logGroupName=groupe, filterPattern=f'"{identifiant}"',
                startTime=int((dernier["LastModified"] - timedelta(minutes=10)).timestamp() * 1000),
                endTime=int((dernier["LastModified"] + timedelta(minutes=5)).timestamp() * 1000)).get("events", [])
            if autour:
                return {"proces": identifiant, "methode": "lignes qui citent le procès", "evenements": evenements(autour)}
            flux = logs.describe_log_streams(logGroupName=groupe, orderBy="LastEventTime", descending=True,
                                             limit=1).get("logStreams", [])
            if not flux:
                return None
            lignes = logs.get_log_events(logGroupName=groupe, logStreamName=flux[0]["logStreamName"],
                                         limit=60, startFromHead=False).get("events", [])
            return {"flux": flux[0]["logStreamName"], "methode": "dernières lignes du flux le plus récent",
                    "evenements": evenements(lignes)} if lignes else None

        journaux = p.lire("cloudwatch_journaux", lire_journaux)
        if journaux is None and "cloudwatch_journaux" in p.fichiers:
            del p.fichiers["cloudwatch_journaux"]
            p.refus.append(f"`cloudwatch_journaux` : aucune ligne trouvée dans `{groupe}`")

    iam = p.client("iam")
    p.lire("iam_role", lambda: {k: v for k, v in iam.get_role(RoleName=ROLE)["Role"].items()
                                if k in ("RoleName", "Arn", "CreateDate", "AssumeRolePolicyDocument", "Description")})
    p.lire("iam_politiques", lambda: {nom: iam.get_role_policy(RoleName=ROLE, PolicyName=nom)["PolicyDocument"]
                                      for nom in iam.list_role_policies(RoleName=ROLE)["PolicyNames"]})
    p.lire("iam_politiques_gerees", lambda: iam.list_attached_role_policies(RoleName=ROLE)["AttachedPolicies"])

    cf = p.client("cloudfront")

    def distribution() -> dict | None:
        for page in cf.get_paginator("list_distributions").paginate():
            for d in page["DistributionList"].get("Items", []):
                if d["Comment"] == COMMENTAIRE_INTERFACE:
                    return {k: d[k] for k in ("Id", "DomainName", "Status", "Enabled", "LastModifiedTime", "Comment")}
        return None
    site = p.lire("cloudfront", distribution)

    if compte:
        p.lire("budget", lambda: [{k: b.get(k) for k in ("BudgetName", "BudgetLimit", "TimeUnit", "CalculatedSpend")}
                                  for b in p.client("budgets").describe_budgets(AccountId=compte).get("Budgets", [])])

    # --- Résumé lisible ---------------------------------------------------------------
    r = p.resume
    if config:
        r.append(f"- **Lambda `{FONCTION}`** : runtime `{config.get('Runtime')}`, {config.get('MemorySize')} Mo, "
                 f"délai {config.get('Timeout')} s, modèle `{config.get('Environment', {}).get('Variables', {}).get('BEDROCK_MODEL_ID', MODELE)}`, "
                 f"dernière modification {config.get('LastModified')}.")
    if url:
        r.append(f"- **Function URL** : authentification `{url.get('AuthType')}`, invocation `{url.get('InvokeMode')}`, "
                 f"CORS {url.get('Cors', {}).get('AllowOrigins')}.")
    if concurrence:
        r.append(f"- **Concurrence réservée** : {concurrence.get('ReservedConcurrentExecutions')}.")
    if asynchrone:
        r.append(f"- **Invocation asynchrone** : {asynchrone.get('MaximumRetryAttempts')} relance, "
                 f"{asynchrone.get('MaximumEventAgeInSeconds')} s d'attente au plus.")
    if lambda_cw:
        r.append("- **Lambda, depuis le 14 nov.** : " + ", ".join(
            f"{nom} {int(v['total'])}" for nom, v in lambda_cw.items()) + ".")
    for modele, m in bedrock.items():
        if m:
            r.append(f"- **Bedrock `{modele}`, depuis le 14 nov.** : " + ", ".join(
                f"{nom} {int(v['total']):,}".replace(",", " ") for nom, v in m.items()) + ".")
    if s3_projet:
        r.append(f"- **S3 `{s3_projet['bucket']}`** : " + "; ".join(
            f"`{k}` {v['objets']} objets" for k, v in s3_projet.items() if k != "bucket") + ".")
    if s3_site:
        r.append(f"- **S3 `{s3_site['bucket']}`** (site) : {s3_site['(tout)']['objets']} objets.")
    if journaux:
        r.append(f"- **Journaux CloudWatch** ({journaux['methode']}) : {len(journaux['evenements'])} lignes.")
    if site:
        r.append(f"- **CloudFront** : `{site['DomainName']}`, état `{site['Status']}`, activée : {site['Enabled']}.")
    return p


def ecrire(p: Preuves, maintenant: datetime, dossier: Path = DOSSIER) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, contenu in p.fichiers.items():
        (dossier / f"{nom}.json").write_text(json.dumps(contenu, ensure_ascii=False, indent=1, default=str) + "\n",
                                             encoding="utf-8")
    lignes = [
        "# Preuves de l'intégration AWS",
        "",
        f"> Exportées le **{maintenant.isoformat()}** par `python -m deploiement.preuves_aws` (#191), en lecture "
        "seule, avant la suppression du compte de l'événement. Chaque fichier JSON est la réponse de l'API, "
        "sans modification (variables d'environnement au nom de secret masquées).",
        "",
        "## Résumé",
        "",
        *(p.resume or ["Aucune preuve lue."]),
        "",
        "## Fichiers",
        "",
        *[f"- [`{nom}.json`]({nom}.json)" for nom in p.fichiers],
        "",
        "## Refusés par le rôle de l'atelier ou introuvables : à capturer dans la console",
        "",
        *(f"- {refus}" for refus in p.refus),
        *([] if p.refus else ["Aucun."]),
        "",
    ]
    chemin = dossier / "README.md"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin


def main(arguments: list[str]) -> int:
    if arguments:
        print("Usage : python -m deploiement.preuves_aws   (identifiants de aws login)")
        return 2
    import boto3
    maintenant = datetime.now(timezone.utc).replace(microsecond=0)
    p = collecter(boto3.Session(region_name=REGION), maintenant)
    chemin = ecrire(p, maintenant)
    print(f"{len(p.fichiers)} preuves → {chemin.relative_to(RACINE)}")
    for refus in p.refus:
        print(f"REFUSÉ  {refus}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
