"""Tests de deploiement/deployer_interface.py (#135), sans appel à AWS ni à npm."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

RACINE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("deployer_interface", RACINE / "deploiement" / "deployer_interface.py")
interface = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(interface)

ARN = "arn:aws:cloudfront::123456789012:distribution/E123"


# --- Faux clients ----------------------------------------------------------------------


class Paginateur:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **_):
        return iter(self.pages)


class FauxCloudFront:
    """Garde l'état entre deux exécutions : OAC, distributions et appels faits."""

    def __init__(self):
        self.oacs: list[dict] = []
        self.distributions: dict[str, dict] = {}
        self.appels: list[str] = []
        self.invalidations: list[dict] = []

    def list_origin_access_controls(self):
        return {"OriginAccessControlList": {"Items": self.oacs} if self.oacs else {}}

    def create_origin_access_control(self, OriginAccessControlConfig):
        self.appels.append("create_origin_access_control")
        oac = {"Id": f"OAC{len(self.oacs) + 1}", "Name": OriginAccessControlConfig["Name"]}
        self.oacs.append(oac)
        return {"OriginAccessControl": oac}

    def get_paginator(self, nom):
        assert nom == "list_distributions"
        items = [{"Id": i, "ARN": ARN, "DomainName": "d111.cloudfront.net", "Status": "Deployed",
                  "Comment": d["Comment"]} for i, d in self.distributions.items()]
        # Une distribution d'un autre projet, sans commentaire : jamais touchée.
        items.insert(0, {"Id": "EAUTRE", "ARN": "arn:autre", "DomainName": "d999.cloudfront.net",
                         "Status": "Deployed", "Comment": ""})
        return Paginateur([{"DistributionList": {"Items": items}}])

    def create_distribution(self, DistributionConfig):
        self.appels.append("create_distribution")
        self.distributions["E123"] = avec_valeurs_par_defaut_aws(DistributionConfig)
        return {"Distribution": {"Id": "E123", "ARN": ARN, "DomainName": "d111.cloudfront.net",
                                 "Status": "InProgress"}}

    def get_distribution_config(self, Id):
        return {"DistributionConfig": copy.deepcopy(self.distributions[Id]), "ETag": "ETAG1"}

    def update_distribution(self, Id, IfMatch, DistributionConfig):
        assert IfMatch == "ETAG1"
        self.appels.append("update_distribution")
        self.distributions[Id] = DistributionConfig

    def create_invalidation(self, DistributionId, InvalidationBatch):
        self.invalidations.append(InvalidationBatch["Paths"]["Items"])


def avec_valeurs_par_defaut_aws(config: dict) -> dict:
    """Ce que renvoie get_distribution_config : la configuration, plus les valeurs par défaut d'AWS."""
    renvoyee = copy.deepcopy(config)
    renvoyee["Origins"]["Items"][0].update({"OriginPath": "", "ConnectionAttempts": 3, "ConnectionTimeout": 10,
                                            "CustomHeaders": {"Quantity": 0}})
    renvoyee["DefaultCacheBehavior"].update({"SmoothStreaming": False, "FieldLevelEncryptionId": "",
                                             "LambdaFunctionAssociations": {"Quantity": 0},
                                             "FunctionAssociations": {"Quantity": 0}})
    renvoyee.update({"Aliases": {"Quantity": 0}, "CacheBehaviors": {"Quantity": 0}, "Logging": {
        "Enabled": False, "IncludeCookies": False, "Bucket": "", "Prefix": ""}, "WebACLId": ""})
    return renvoyee


class FauxS3:
    def __init__(self, objets: dict[str, bytes] | None = None, politique: str | None = None):
        self.objets = dict(objets or {})
        self.en_tetes: dict[str, dict] = {}
        self.politique = politique
        self.ordre_envoi: list[str] = []
        self.politiques_posees = 0

    def get_paginator(self, nom):
        assert nom == "list_objects_v2"
        contenu = [{"Key": cle, "ETag": f'"{hashlib.md5(corps).hexdigest()}"'} for cle, corps in self.objets.items()]
        return Paginateur([{"Contents": contenu}] if contenu else [{}])

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        self.objets[Key] = Body
        self.en_tetes[Key] = {"ContentType": ContentType, "CacheControl": CacheControl}
        self.ordre_envoi.append(Key)

    def delete_objects(self, Bucket, Delete):
        for objet in Delete["Objects"]:
            del self.objets[objet["Key"]]

    def get_bucket_policy(self, Bucket):
        if self.politique is None:
            raise ClientError({"Error": {"Code": "NoSuchBucketPolicy"}}, "GetBucketPolicy")
        return {"Policy": self.politique}

    def put_bucket_policy(self, Bucket, Policy):
        self.politique = Policy
        self.politiques_posees += 1


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "proces-verbaux").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "proces-verbaux" / "2026-11-15-abc.html").write_text("<p>PV</p>", encoding="utf-8")
    (tmp_path / "marque.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


# --- Distribution ----------------------------------------------------------------------


def test_distribution_https_compression_et_pages_profondes():
    config = interface.config_distribution("alphaforge-site-123", "OAC1", "ref")
    assert config["Comment"] == "alphaforge-interface"
    assert config["DefaultRootObject"] == "index.html"
    assert config["PriceClass"] == "PriceClass_100"
    comportement = config["DefaultCacheBehavior"]
    assert comportement["ViewerProtocolPolicy"] == "redirect-to-https"
    assert comportement["Compress"] is True
    origine = config["Origins"]["Items"][0]
    assert origine["DomainName"] == "alphaforge-site-123.s3.us-east-1.amazonaws.com"
    assert origine["OriginAccessControlId"] == "OAC1"
    # BrowserRouter : recharger /robert/tribunal renvoie l'interface, avec le statut 200.
    assert config["CustomErrorResponses"]["Items"] == [
        {"ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0},
        {"ErrorCode": 404, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0},
    ]


def test_relancer_ne_recree_rien():
    cf = FauxCloudFront()
    premiere = interface.assurer_distribution(cf, "alphaforge-site-123", interface.assurer_oac(cf))
    seconde = interface.assurer_distribution(cf, "alphaforge-site-123", interface.assurer_oac(cf))
    assert cf.appels == ["create_origin_access_control", "create_distribution"]
    assert premiere["Id"] == seconde["Id"] == "E123"
    assert "EAUTRE" not in cf.distributions  # la distribution sans commentaire n'est pas touchée


def test_reglage_change_a_la_main_est_remis_sans_toucher_au_reste():
    cf = FauxCloudFront()
    interface.assurer_distribution(cf, "alphaforge-site-123", "OAC1")
    stockee = cf.distributions["E123"]
    stockee["CustomErrorResponses"] = {"Quantity": 0}
    stockee["Logging"]["Enabled"] = True  # réglage que le script ne gère pas
    reference = stockee["CallerReference"]

    interface.assurer_distribution(cf, "alphaforge-site-123", "OAC1")
    corrigee = cf.distributions["E123"]
    assert cf.appels.count("update_distribution") == 1
    assert corrigee["CustomErrorResponses"]["Quantity"] == 2
    assert corrigee["CallerReference"] == reference
    assert corrigee["Logging"]["Enabled"] is True


# --- Bucket ----------------------------------------------------------------------------


def test_politique_du_bucket_limitee_a_la_distribution():
    politique = interface.politique_bucket("alphaforge-site-123", ARN)
    [declaration] = politique["Statement"]
    assert declaration["Principal"] == {"Service": "cloudfront.amazonaws.com"}
    assert declaration["Action"] == "s3:GetObject"
    assert declaration["Resource"] == "arn:aws:s3:::alphaforge-site-123/*"
    assert declaration["Condition"] == {"StringEquals": {"AWS:SourceArn": ARN}}


def test_politique_du_bucket_posee_une_seule_fois():
    s3 = FauxS3()
    interface.appliquer_politique_bucket(s3, "alphaforge-site-123", ARN)
    interface.appliquer_politique_bucket(s3, "alphaforge-site-123", ARN)
    assert s3.politiques_posees == 1
    assert json.loads(s3.politique) == interface.politique_bucket("alphaforge-site-123", ARN)


# --- Envoi et invalidation -------------------------------------------------------------


def test_en_tetes_selon_le_fichier():
    assert interface.en_tetes("assets/index-abc123.js") == {
        "ContentType": "text/javascript; charset=utf-8", "CacheControl": "public, max-age=31536000, immutable"}
    assert interface.en_tetes("assets/index-abc123.css")["ContentType"] == "text/css; charset=utf-8"
    assert interface.en_tetes("index.html") == {"ContentType": "text/html; charset=utf-8", "CacheControl": "no-cache"}
    assert interface.en_tetes("proces-verbaux/2026-11-15-abc.html") == {
        "ContentType": "text/html; charset=utf-8", "CacheControl": "no-cache"}
    assert interface.en_tetes("marque.svg") == {"ContentType": "image/svg+xml", "CacheControl": "no-cache"}


def test_envoi_saute_l_inchange_supprime_l_obsolete_et_envoie_index_en_dernier(dist):
    s3 = FauxS3({"assets/index-abc123.js": b"console.log(1)", "assets/index-ancien.js": b"x"})
    bilan = interface.envoyer_site(s3, "alphaforge-site-123", dist)
    assert bilan["inchanges"] == ["assets/index-abc123.js"]
    assert bilan["supprimes"] == ["assets/index-ancien.js"]
    assert s3.ordre_envoi[-1] == "index.html"
    assert set(s3.objets) == {"index.html", "assets/index-abc123.js", "proces-verbaux/2026-11-15-abc.html", "marque.svg"}
    assert s3.en_tetes["proces-verbaux/2026-11-15-abc.html"]["CacheControl"] == "no-cache"


def test_second_envoi_sans_changement_n_envoie_ni_n_invalide_rien(dist):
    s3, cf = FauxS3(), FauxCloudFront()
    interface.invalider(cf, "E123", interface.chemins_a_invalider(interface.envoyer_site(s3, "b", dist)))
    bilan = interface.envoyer_site(s3, "b", dist)
    interface.invalider(cf, "E123", interface.chemins_a_invalider(bilan))
    assert bilan["envoyes"] == [] and bilan["supprimes"] == []
    assert cf.invalidations == [["/", "/index.html", "/proces-verbaux/*"]]


def test_forcer_renvoie_tout(dist):
    s3 = FauxS3()
    interface.envoyer_site(s3, "b", dist)
    assert len(interface.envoyer_site(s3, "b", dist, forcer=True)["envoyes"]) == 4


def test_seul_un_changement_hors_assets_demande_une_invalidation():
    assert interface.chemins_a_invalider({"envoyes": ["assets/index-neuf.js"], "supprimes": ["assets/index-vieux.js"]}) == []
    assert interface.chemins_a_invalider({"envoyes": ["index.html"], "supprimes": []}) == ["/", "/index.html", "/proces-verbaux/*"]
    assert interface.chemins_a_invalider({"envoyes": [], "supprimes": ["proces-verbaux/vieux.html"]}) != []


def test_envoi_refuse_un_dossier_sans_index(tmp_path):
    with pytest.raises(SystemExit):
        interface.envoyer_site(FauxS3(), "b", tmp_path)


# --- Construction ----------------------------------------------------------------------


def test_mode_direct_par_defaut_avec_l_adresse_lue_sur_le_compte():
    url = "https://exemple.lambda-url.us-east-1.on.aws"
    assert interface.variables_construction(url, "direct") == {"VITE_USE_MOCKS": "false", "VITE_API_URL": url}
    assert interface.variables_construction(url, "demo") == {"VITE_USE_MOCKS": "true", "VITE_API_URL": url}
    assert interface.variables_construction(None, "demo") == {"VITE_USE_MOCKS": "true"}
    with pytest.raises(SystemExit):
        interface.variables_construction(None, "direct")


def test_mode_par_defaut_de_la_ligne_de_commande_est_direct():
    assert interface.lire_options([]).mode == "direct"
    assert interface.lire_options(["--mode", "demo"]).mode == "demo"
