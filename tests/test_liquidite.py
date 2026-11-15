"""Outil 8 : mesurer_liquidite — jours de bourse pour revendre une ligne (#117)."""

import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd
import pytest

from pipeline import liquidite
from pipeline.chiffres import verifier_argument
from pipeline.donnees import ErreurDonnees, lire_csv
from pipeline.liquidite import jours_pour_vendre, piece_liquidite, valeur_echangee_moyenne
from pipeline.orchestrateur import outils_du_profil
from pipeline.pacte import charger_pacte
from pipeline.sources import SOURCES, sources_du_proces

RACINE = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def robert():
    return charger_pacte(RACINE / "personas" / "robert.json")


@pytest.fixture(scope="module")
def piece_robert(robert):
    return piece_liquidite("P4", robert["portefeuille"], robert["decision_demo"], robert["capital_fictif_cad"])


def valider_piece(piece):
    jsonschema.Draft202012Validator({"$ref": "#/$defs/piece", "$defs": SCHEMA["$defs"]}).validate(piece)


# --- Calcul à la main sur un petit jeu de données --------------------------------


def test_valeur_echangee_calculee_a_la_main():
    # 1 000 × 10 $ + 2 000 × 11 $ + (volume absent : ignoré) + 0 × 13 $ = 32 000 $ sur 3 séances.
    volumes = pd.Series([1000, 2000, np.nan, 0])
    cloture = pd.Series([10.0, 11.0, 12.0, 13.0])
    assert valeur_echangee_moyenne(volumes, cloture) == pytest.approx(32000 / 3)
    # Une position de 5 000 $, à 10 % des échanges par jour : 5 000 ÷ (0,10 × 10 666,67) = 4,6875 jours.
    assert jours_pour_vendre(5000, 32000 / 3) == pytest.approx(4.6875)


def test_conversion_en_cad_au_taux_de_chaque_seance():
    # 100 × 50 $ US × 1,25 = 6 250 $ ; 200 × 50 $ US × 1,40 = 14 000 $ → 10 125 $ en moyenne.
    moyenne = valeur_echangee_moyenne(pd.Series([100, 200]), pd.Series([50.0, 50.0]), pd.Series([1.25, 1.40]))
    assert moyenne == pytest.approx(10125)


def test_volume_crypto_deja_en_dollars():
    # Yahoo donne le volume crypto en dollars US échangés : il n'est pas multiplié par le prix.
    moyenne = valeur_echangee_moyenne(pd.Series([1e6, 3e6]), pd.Series([60000.0, 61000.0]), pd.Series([1.3, 1.3]),
                                      volume_en_devise=True)
    assert moyenne == pytest.approx(2.6e6)


def test_titre_sans_volume_absent_jamais_zero():
    cloture = pd.Series([10.0, 11.0])
    assert valeur_echangee_moyenne(pd.Series([np.nan, np.nan]), cloture) is None
    # Rien d'échangé sur toute la période : le temps pour vendre serait infini, pas zéro.
    assert valeur_echangee_moyenne(pd.Series([0, 0]), cloture) is None
    with pytest.raises(ValueError):
        jours_pour_vendre(5000, 0)


# --- La pièce sur les vraies données ------------------------------------------------


def test_robert_trente_pour_cent_de_tsla(piece_robert):
    valider_piece(piece_robert)
    v = piece_robert["valeurs"]
    assert piece_robert["outil"] == "mesurer_liquidite" and piece_robert["etiquette"] == "fictif"
    # Lignes après la décision : TSLA à 30 %, les autres réduites au prorata (ZST.TO 30 % → 21 %).
    assert v["titres"][0] == "TSLA" and len(v["titres"]) == 7
    assert (v["valeur_position_cad_TSLA"], v["valeur_position_cad_ZST.TO"]) == (195000.0, 136500.0)
    # Le petit FNB obligataire est la ligne la plus longue à revendre, pas TSLA.
    assert v["titre_le_moins_liquide"] == "ZST.TO"
    assert v["jours_pour_vendre_ZST.TO"] == v["jours_pour_vendre_max"]
    assert v["jours_pour_vendre_TSLA"] < 0.001
    assert v["part_max_volume"] == 0.10 and v["capital"] == 650000


def test_zst_refait_depuis_le_csv(piece_robert):
    """ZST.TO (CAD) : moyenne de volume × close sur ses propres séances, volume nul du 2022-07-06 compris."""
    brut = lire_csv("prices_daily.csv")
    zst = brut[brut["ticker"] == "ZST.TO"]
    assert (zst["volume"] == 0).sum() == 1
    attendue = float((zst["volume"] * zst["close"]).mean())
    v = piece_robert["valeurs"]
    assert v["valeur_echangee_moyenne_cad_ZST.TO"] == pytest.approx(attendue, abs=0.01)
    assert v["valeur_echangee_moyenne_millions_cad_ZST.TO"] == pytest.approx(attendue / 1e6, abs=1e-6)
    assert v["part_volume_quotidien_ZST.TO"] == pytest.approx(136500 / attendue, rel=1e-5)
    assert v["jours_pour_vendre_ZST.TO"] == pytest.approx(136500 / (0.10 * attendue), rel=1e-5)


def test_bitcoin_volume_en_dollars_converti_en_cad():
    profil = charger_pacte(RACINE / "personas" / "amira.json")
    piece = piece_liquidite("P4", profil["portefeuille"], profil["decision_demo"], profil["capital_fictif_cad"],
                            ["BTC-USD"])
    brut = lire_csv("prices_daily.csv")
    btc = brut[brut["ticker"] == "BTC-USD"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")
    taux = lire_csv("fx_usdcad_daily.csv").assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["usdcad"]
    taux = taux.reindex(taux.index.union(btc.index)).ffill().reindex(btc.index)
    assert piece["valeurs"]["valeur_echangee_moyenne_cad_BTC-USD"] == pytest.approx(float((btc["volume"] * taux).mean()), rel=1e-9)
    # Une petite valeur garde ses chiffres significatifs au lieu de s'arrondir à 0.
    assert 0 < piece["valeurs"]["part_volume_quotidien_BTC-USD"] < 1e-6


def test_volume_absent_signale_sans_valeur(robert, monkeypatch):
    vraies = liquidite.charger_volumes

    def sans_volume_pour_zst(tickers):
        lignes = vraies(tickers)
        lignes.loc[lignes["ticker"] == "ZST.TO", "volume"] = np.nan
        return lignes

    monkeypatch.setattr(liquidite, "charger_volumes", sans_volume_pour_zst)
    piece = piece_liquidite("P4", robert["portefeuille"], robert["decision_demo"], robert["capital_fictif_cad"])
    v = piece["valeurs"]
    assert v["titres_sans_volume"] == ["ZST.TO"]
    assert not [cle for cle in v if cle.endswith("_ZST.TO")]
    assert v["titre_le_moins_liquide"] == "XBB.TO"
    assert "volume absent : ZST.TO" in piece["valeur_affichee"]
    with pytest.raises(ErreurDonnees, match="Aucun volume utilisable"):
        piece_liquidite("P4", robert["portefeuille"], robert["decision_demo"], robert["capital_fictif_cad"], ["ZST.TO"])


def test_demandes_impossibles(robert):
    with pytest.raises(ErreurDonnees, match="Absent.*NVDA"):
        piece_liquidite("P4", robert["portefeuille"], robert["decision_demo"], 650000, ["NVDA"])
    with pytest.raises(ErreurDonnees, match="Capital fictif inconnu"):
        piece_liquidite("P4", robert["portefeuille"], robert["decision_demo"], None)


def test_sans_decision_le_portefeuille_actuel(robert):
    piece = piece_liquidite("P4", robert["portefeuille"], None, 650000)
    assert piece["valeurs"]["valeur_position_cad_ZST.TO"] == 195000.0
    assert "TSLA" not in piece["valeurs"]["titres"]


# --- Orchestrateur, Greffier et sources ----------------------------------------------


def test_outil_de_l_orchestrateur(robert):
    [outil] = [o for o in outils_du_profil(robert, robert["decision_demo"]) if o.nom == "mesurer_liquidite"]
    schema = outil.description_bedrock["toolSpec"]["inputSchema"]["json"]
    assert schema["properties"]["titres"]["items"]["enum"] == sorted(
        ["TSLA", "ZST.TO", "XBB.TO", "XIU.TO", "JNJ", "RY.TO", "FTS.TO"])
    piece = outil.executer({"titres": ["ZST.TO", "TSLA"]}, "P5")
    assert piece["id"] == "P5" and piece["valeurs"]["titres"] == ["ZST.TO", "TSLA"]


def test_un_argument_de_liquidite_passe_le_greffier(piece_robert, robert):
    dossier = {"decision": robert["decision_demo"], "pieces": [piece_robert], "periode": ["2021-11-12", "2026-11-12"]}
    texte = ("Votre ligne ZST.TO de 136 500 $ représente +8,3 % de ce qui s'en échange en moyenne chaque jour, "
             "soit 1,6 million $. En ne pesant pas plus de 10 % des échanges, il faudrait 0,8 jour de bourse pour la revendre.")
    assert verifier_argument({"texte": texte, "pieces": ["P4"]}, dossier).introuvables == []
    # 136 500 ÷ 1,6 million calculé par l'agent (8,5 %) : nombre dérivé, rejeté.
    faux = "Votre ligne ZST.TO représente +8,5 % de ce qui s'en échange chaque jour."
    assert verifier_argument({"texte": faux, "pieces": ["P4"]}, dossier).introuvables


def test_source_des_volumes(piece_robert):
    contrat = {"persona": "robert", "pieces": [piece_robert], "controles": [], "pacte": {"regles": []},
               "trace": [{"etape": "orchestrateur", "outil": "mesurer_liquidite", "sortie": "P4",
                          "raison": "Une ligne obligataire peu échangée pourrait être lente à revendre"}]}
    sources = {s["nom"]: s for s in sources_du_proces(contrat)}
    volumes = sources[SOURCES["volumes"].nom]
    assert volumes["fichier"] == "prices_daily.csv" and volumes["date_extraction"] == "2026-11-13"
    assert volumes["pieces"] == [{"id": "P4", "raison": "Une ligne obligataire peu échangée pourrait être lente à revendre"}]
    assert SOURCES["change"].nom in sources and SOURCES["univers"].nom in sources
