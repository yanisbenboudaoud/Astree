"""Preuves AWS (#191) : lecture seule, refus notés sans arrêter la collecte, secrets masqués."""

from datetime import datetime, timezone

from deploiement.preuves_aws import collecter, ecrire

MAINTENANT = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)


class Refuse:
    """Client dont chaque appel est refusé, comme un rôle d'atelier sans droit de lecture."""

    def __getattr__(self, nom):
        def appel(*args, **kwargs):
            raise PermissionError("AccessDenied")
        return appel


class FauxSTS(Refuse):
    def get_caller_identity(self):
        return {"Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/atelier/marc",
                "ResponseMetadata": {}}


class FauxLambda(Refuse):
    def get_function_configuration(self, FunctionName):
        return {"FunctionName": FunctionName, "Runtime": "python3.14", "MemorySize": 1024, "Timeout": 300,
                "LastModified": "2026-11-15T20:58:00Z",
                "Environment": {"Variables": {"BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-5-5",
                                              "API_KEY_EXTERNE": "ne-doit-pas-sortir"}},
                "ResponseMetadata": {}}


class FausseSession:
    def __init__(self, clients):
        self.clients = clients

    def client(self, service, region_name=None):
        return self.clients.get(service, Refuse())


def test_tout_refuse_n_arrete_rien(tmp_path):
    p = collecter(FausseSession({}), MAINTENANT)
    assert p.fichiers.get("cloudwatch_bedrock") == {}
    assert any("identite" in r for r in p.refus)
    texte = ecrire(p, MAINTENANT, tmp_path).read_text(encoding="utf-8")
    assert "Refusés par le rôle de l'atelier ou introuvables : à capturer dans la console" in texte
    assert "2026-11-16T10:00:00+00:00" in texte


def test_lambda_lue_et_secret_masque(tmp_path):
    p = collecter(FausseSession({"sts": FauxSTS(), "lambda": FauxLambda()}), MAINTENANT)
    variables = p.fichiers["lambda_configuration"]["Environment"]["Variables"]
    assert variables["API_KEY_EXTERNE"] == "*** masqué ***"
    assert variables["BEDROCK_MODEL_ID"] == "global.anthropic.claude-sonnet-5-5"
    assert "ResponseMetadata" not in p.fichiers["identite"]
    ecrire(p, MAINTENANT, tmp_path)
    assert "ne-doit-pas-sortir" not in (tmp_path / "lambda_configuration.json").read_text(encoding="utf-8")
    assert "python3.14, 1024 Mo" in (tmp_path / "README.md").read_text(encoding="utf-8").replace("`", "")
