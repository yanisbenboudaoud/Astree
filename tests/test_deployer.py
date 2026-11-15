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
    politique = json.loads(deployer.politique_pour_bucket("alphaforge-123"))
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


def test_relancer_ne_double_pas_les_permissions():
    lam = FauxLambda(url_existe=False)
    deployer.assurer_function_url(lam, ["http://localhost:5173"])
    deployer.assurer_function_url(lam, ["http://localhost:5173"])
    assert len(lam.permissions) == 2
