"""Tests de deploiement/deployer.py pour la Function URL publique (#14), sans appel à AWS."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("deployer", RACINE / "deploiement" / "deployer.py")
deployer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deployer)


class ConflitDePermission(Exception):
    """Imite ResourceConflictException : la permission existe déjà."""


class FauxLambda:
    """Client Lambda minimal : enregistre les appels, refuse une permission déjà accordée."""

    def __init__(self, url_existe: bool = True):
        self.url_existe = url_existe
        self.permissions: list[dict] = []
        self.reglages: dict | None = None
        self.exceptions = type("Exceptions", (), {
            "ResourceConflictException": ConflitDePermission,
            "ResourceNotFoundException": LookupError,
        })

    def get_function_url_config(self, FunctionName):
        if not self.url_existe:
            raise LookupError(FunctionName)
        return {"FunctionUrl": "https://exemple.lambda-url.us-east-1.on.aws/", "AuthType": "AWS_IAM"}

    def update_function_url_config(self, FunctionName, **reglages):
        self.reglages = reglages
        return {"FunctionUrl": "https://exemple.lambda-url.us-east-1.on.aws/"}

    create_function_url_config = update_function_url_config

    def add_permission(self, FunctionName, **permission):
        if any(p["StatementId"] == permission["StatementId"] for p in self.permissions):
            raise ConflitDePermission(permission["StatementId"])
        self.permissions.append(permission)


def test_cors_limite_a_l_interface_et_expose_l_identifiant_du_proces():
    cors = deployer.cors_interface(["http://localhost:5173"])
    assert cors["AllowOrigins"] == ["http://localhost:5173"]
    assert cors["AllowMethods"] == ["POST"]
    assert cors["AllowHeaders"] == ["content-type"]
    assert cors["ExposeHeaders"] == ["x-proces-id"]


def test_function_url_passe_en_none_avec_les_deux_permissions():
    lam = FauxLambda()
    url = deployer.assurer_function_url(lam, deployer.ORIGINES_INTERFACE)
    assert url.startswith("https://")
    assert lam.reglages["AuthType"] == "NONE"
    assert lam.reglages["Cors"]["AllowOrigins"] == ["http://localhost:5173"]
    actions = {p["Action"]: p for p in lam.permissions}
    assert actions["lambda:InvokeFunctionUrl"]["FunctionUrlAuthType"] == "NONE"
    assert actions["lambda:InvokeFunction"]["InvokedViaFunctionUrl"] is True
    assert all(p["Principal"] == "*" for p in lam.permissions)


def test_politique_autorise_seulement_l_invocation_de_la_fonction_elle_meme():
    """#90 : la Lambda s'invoque en asynchrone pour le procès ; rien d'autre côté Lambda."""
    politique = json.loads(deployer.politique_pour_bucket("alphaforge-123", "arn:aws:bedrock:us-east-1:123:guardrail/gr1"))
    invocations = [s for s in politique["Statement"] if "lambda:InvokeFunction" in str(s["Action"])]
    assert invocations == [{"Sid": "SInvoquerEnAsynchronePourLaProgression", "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": f"arn:aws:lambda:us-east-1:*:function:{deployer.FONCTION}"}]


def test_invocation_asynchrone_sans_relance():
    """Un procès raté ne se rejoue jamais tout seul (nouveaux appels Bedrock)."""
    appels = []

    class Lambda:
        def put_function_event_invoke_config(self, **reglages):
            appels.append(reglages)

    deployer.regler_invocation_asynchrone(Lambda())
    assert appels == [{"FunctionName": deployer.FONCTION, "MaximumRetryAttempts": 0, "MaximumEventAgeInSeconds": 60}]


class FauxCloudFront:
    """list_distributions : une distribution d'un autre projet, plus celle du site si elle existe."""

    def __init__(self, site: str | None):
        self.items = [{"Id": "EAUTRE", "Comment": "", "DomainName": "d999.cloudfront.net"}]
        if site:
            self.items.append({"Id": "E123", "Comment": "alphaforge-interface", "DomainName": site})

    def get_paginator(self, nom):
        assert nom == "list_distributions"
        items = self.items

        class Paginateur:
            def paginate(self):
                return iter([{"DistributionList": {"Items": items}}])
        return Paginateur()


def test_cors_garde_le_site_heberge_lu_sur_le_compte_sans_origine():
    """#136 : un redéploiement lancé sans --origine garde toujours le site."""
    origines = deployer.origines_cors(FauxCloudFront("d111.cloudfront.net"), [])
    assert origines == ["http://localhost:5173", "https://d111.cloudfront.net"]


def test_cors_sans_distribution_garde_l_interface_locale():
    assert deployer.origines_cors(FauxCloudFront(None), []) == ["http://localhost:5173"]


def test_cors_ajoute_les_origines_demandees_sans_doublon():
    origines = deployer.origines_cors(FauxCloudFront("d111.cloudfront.net"),
                                      ["http://localhost:5175/", "https://d111.cloudfront.net"])
    assert origines == ["http://localhost:5173", "https://d111.cloudfront.net", "http://localhost:5175"]


def test_relancer_ne_double_pas_les_permissions():
    lam = FauxLambda(url_existe=False)
    deployer.assurer_function_url(lam, ["http://localhost:5173"])
    deployer.assurer_function_url(lam, ["http://localhost:5173"])
    assert len(lam.permissions) == 2


# --- Guardrail Bedrock (#189) ---------------------------------------------------------


class FauxBedrock:
    """Client Bedrock (plan de contrôle) minimal : un Guardrail et ses versions numérotées."""

    def __init__(self, existe: bool = False, description_version: str | None = None):
        self.appels: list[str] = []
        self.versions = [] if description_version is None else [{"version": "1", "description": description_version}]
        self.existe = existe

    def list_guardrails(self, guardrailIdentifier=None):
        if guardrailIdentifier is None:
            return {"guardrails": [{"id": "gr1", "arn": "arn:aws:bedrock:us-east-1:123:guardrail/gr1", "name": deployer.GARDE_FOU, "version": "DRAFT"}]
                    if self.existe else []}
        return {"guardrails": [{"version": "DRAFT"}, *self.versions]}

    def create_guardrail(self, name, **config):
        self.appels.append("create_guardrail")
        self.existe = True
        return {"guardrailId": "gr1", "guardrailArn": "arn:aws:bedrock:us-east-1:123:guardrail/gr1", "version": "DRAFT"}

    def update_guardrail(self, guardrailIdentifier, name, **config):
        self.appels.append("update_guardrail")

    def create_guardrail_version(self, guardrailIdentifier, description):
        self.appels.append("create_guardrail_version")
        version = str(len(self.versions) + 1)
        self.versions.append({"version": version, "description": description})
        return {"guardrailId": guardrailIdentifier, "version": version}


def test_garde_fou_cree_puis_publie_une_version():
    bedrock = FauxBedrock()
    assert deployer.assurer_garde_fou(bedrock) == ("gr1", "1", "arn:aws:bedrock:us-east-1:123:guardrail/gr1")
    assert bedrock.appels == ["create_guardrail", "create_guardrail_version"]


def test_relancer_ne_publie_pas_de_nouvelle_version():
    bedrock = FauxBedrock(existe=True, description_version=f"config {deployer.empreinte_garde_fou()}")
    assert deployer.assurer_garde_fou(bedrock) == ("gr1", "1", "arn:aws:bedrock:us-east-1:123:guardrail/gr1")
    assert bedrock.appels == []


def test_configuration_changee_mise_a_jour_et_nouvelle_version():
    bedrock = FauxBedrock(existe=True, description_version="config ancienne")
    assert deployer.assurer_garde_fou(bedrock)[1] == "2"
    assert bedrock.appels == ["update_guardrail", "create_guardrail_version"]


def test_garde_fou_filtre_l_entree_et_la_sortie_et_droit_minimal():
    [sujet] = deployer.CONFIG_GARDE_FOU["topicPolicyConfig"]["topicsConfig"]
    assert (sujet["inputEnabled"], sujet["outputEnabled"]) == (False, True)  # une demande de conseil n'est pas bloquée
    [attaque] = deployer.CONFIG_GARDE_FOU["contentPolicyConfig"]["filtersConfig"]
    assert attaque == {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"}
    politique = json.loads(deployer.politique_pour_bucket("alphaforge-123", "arn:aws:bedrock:us-east-1:123:guardrail/gr1"))
    assert {"Sid": "GuardrailDuProjet", "Effect": "Allow", "Action": "bedrock:ApplyGuardrail",
            "Resource": "arn:aws:bedrock:us-east-1:123:guardrail/gr1"} in politique["Statement"]
    variables = deployer.variables_environnement("alphaforge-123", ("gr1", "3"))
    assert (variables["BEDROCK_GUARDRAIL_ID"], variables["BEDROCK_GUARDRAIL_VERSION"]) == ("gr1", "3")
