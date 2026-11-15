"""Frais de gestion des FNB : relevé, coût annuel du portefeuille et pièce de simulation (#114)."""

import json
from pathlib import Path

import pytest

from pipeline import frais
from pipeline.chiffres import verifier_argument
from pipeline.donnees import ErreurDonnees, charger_univers
from pipeline.simulation import formater_pourcentage, piece_simulation

RACINE = Path(__file__).resolve().parent.parent
ROBERT = json.loads((RACINE / "personas" / "robert.json").read_text(encoding="utf-8"))
DECISION = ROBERT["decision_demo"]  # 30 % en TSLA, financement proportionnel

# Petit relevé fictif, pour des calculs faits à la main indépendants du vrai relevé.
RELEVE_TEST = {
    "date_releve": "2026-11-15",
    "sans_frais_de_gestion": {"classes": ["equity", "crypto"]},
    "fnb": [
        {"ticker": "XIU.TO", "ratio_frais": 0.0020, "url": "https://exemple", "date_donnee": "2026-10-31"},
        {"ticker": "XBB.TO", "ratio_frais": 0.0010, "url": "https://exemple", "date_donnee": "2026-10-31"},
    ],
}


@pytest.fixture
def releve_test(monkeypatch):
    monkeypatch.setattr(frais, "charger_frais", lambda: RELEVE_TEST)


# --- Coût annuel : calculs faits à la main ------------------------------------------------

def test_cout_annuel_pondere_calcule_a_la_main(releve_test):
    # 50 % × 0,20 % + 30 % × 0,10 % + 20 % × 0 (action détenue en direct) = 0,13 %
    cout = frais.cout_frais({"XIU.TO": 0.5, "XBB.TO": 0.3, "RY.TO": 0.2})
    assert cout.ratio == pytest.approx(0.0013)
    assert cout.inconnus == ()


def test_action_et_cryptoactif_sans_frais_de_gestion(releve_test):
    assert frais.ratio_frais("TSLA") == 0.0
    assert frais.ratio_frais("BTC-USD") == 0.0


def test_un_titre_sans_frais_connus_n_est_jamais_devine(releve_test):
    # TLT est un FNB de l'univers absent du relevé de test ; ZZZ n'est pas dans l'univers.
    assert frais.ratio_frais("TLT") is None
    assert frais.ratio_frais("ZZZ") is None
    cout = frais.cout_frais({"XIU.TO": 0.6, "TLT": 0.4})
    assert cout == frais.CoutFrais(None, ("TLT",))


def test_contexte_avant_apres_en_dollars(releve_test):
    valeurs, traitement = frais.contexte_frais({"XIU.TO": 0.5, "XBB.TO": 0.5}, {"XIU.TO": 0.35, "XBB.TO": 0.35, "TSLA": 0.3},
                                               capital=100_000)
    # Avant : 0,5 × 0,20 % + 0,5 × 0,10 % = 0,15 % → 150 $ ; après : 0,7 × 0,15 % = 0,105 % → 105 $.
    assert valeurs == {
        "frais_annuels": pytest.approx(0.00105),
        "frais_annuels_cad": 105,
        "frais_annuels_actuels": pytest.approx(0.0015),
        "frais_annuels_cad_actuels": 150,
        "ecart_frais_annuels_cad": 45,
    }
    assert "déjà prélevés dans les cours" in traitement


def test_contexte_signale_le_titre_inconnu_sans_valeur(releve_test):
    valeurs, traitement = frais.contexte_frais({"XIU.TO": 1.0}, {"XIU.TO": 0.7, "TLT": 0.3}, capital=100_000)
    # Avant : connu ; après : TLT inconnu, donc aucune valeur après ni écart.
    assert valeurs == {"frais_annuels_actuels": pytest.approx(0.002), "frais_annuels_cad_actuels": 200,
                       "frais_inconnus": ["TLT"]}
    assert "frais inconnus pour TLT" in traitement


def test_sans_capital_aucun_montant(releve_test):
    valeurs, _ = frais.contexte_frais({"XIU.TO": 1.0}, {"XIU.TO": 1.0})
    assert set(valeurs) == {"frais_annuels", "frais_annuels_actuels"}


# --- Le relevé réel ---------------------------------------------------------------------

def test_le_releve_couvre_chaque_fnb_de_l_univers_avec_sa_source():
    releve = frais.charger_frais()
    univers = charger_univers()
    fnb_univers = set(univers.loc[univers["asset_class"].str.startswith("etf"), "ticker"])
    assert {f["ticker"] for f in releve["fnb"]} == fnb_univers
    for fnb in releve["fnb"]:
        assert fnb["url"].startswith("https://") and fnb["date_donnee"] and fnb["document"]
    assert releve["conditions_utilisation"] and releve["frais_dans_les_cours"]["preuves"]


def test_tout_titre_de_l_univers_a_un_ratio():
    assert all(frais.ratio_frais(ticker) is not None for ticker in charger_univers()["ticker"])


@pytest.mark.parametrize("modification, message", [
    (lambda r: r["fnb"].append(dict(r["fnb"][0])), "apparaît deux fois"),
    (lambda r: r["fnb"][0].update(ratio_frais=0.17), "ratio de"),
    (lambda r: r["fnb"][0].pop("url"), "source ou date manquante"),
])
def test_un_releve_invalide_est_refuse(tmp_path, modification, message):
    releve = json.loads(frais.CHEMIN_FRAIS.read_text(encoding="utf-8"))
    modification(releve)
    chemin = tmp_path / "frais.json"
    chemin.write_text(json.dumps(releve), encoding="utf-8")
    with pytest.raises(ErreurDonnees, match=message):
        frais.charger_frais(chemin)


def test_releve_absent(tmp_path):
    with pytest.raises(ErreurDonnees, match="absent"):
        frais.charger_frais(tmp_path / "absent.json")


# --- Pièce de simulation -----------------------------------------------------------------

def test_robert_frais_dans_la_piece_de_simulation():
    piece = piece_simulation("P2", ROBERT["portefeuille"], DECISION, capital=ROBERT["capital_fictif_cad"])
    v = piece["valeurs"]
    # 30 % ZST.TO × 0,17 % + 20 % XBB.TO × 0,10 % + 20 % XIU.TO × 0,17 % ; actions : aucun frais.
    assert v["frais_annuels_actuels"] == pytest.approx(0.00105)
    assert v["frais_annuels"] == pytest.approx(0.00105 * 0.7)  # TSLA prend 30 %, au prorata
    assert v["frais_annuels_cad_actuels"] == round(650_000 * v["frais_annuels_actuels"])
    assert v["frais_annuels_cad"] == round(650_000 * v["frais_annuels"])
    assert "relevés le 2026-11-15" in piece["source"]
    assert frais.LIMITES_FRAIS in piece["limites"]


def test_le_rejeu_2022_n_a_pas_de_frais():
    piece = piece_simulation("P3", ROBERT["portefeuille"], DECISION, periode="2022")
    assert not any(cle.startswith("frais") for cle in piece["valeurs"])


def test_sans_releve_la_piece_reste_produite(monkeypatch, capsys):
    def absent():
        raise ErreurDonnees("donnees_externes/frais_fnb.json absent")
    monkeypatch.setattr(frais, "charger_frais", absent)
    piece = piece_simulation("P2", ROBERT["portefeuille"], DECISION, capital=650_000)
    assert "frais_annuels" not in piece["valeurs"]
    assert "Frais non ajoutés à P2" in capsys.readouterr().out


def test_un_cout_des_frais_cite_passe_le_greffier():
    piece = piece_simulation("P2", ROBERT["portefeuille"], DECISION, capital=650_000)
    v = piece["valeurs"]
    dossier = {"decision": DECISION, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    texte = (
        f"Les frais de gestion des FNB coûteraient {v['frais_annuels_cad']} $ par an avec la décision, "
        f"contre {v['frais_annuels_cad_actuels']} $ aujourd'hui, soit "
        f"{formater_pourcentage(v['frais_annuels'], 2)} du portefeuille."
    )
    assert verifier_argument({"texte": texte, "pieces": ["P2"]}, dossier).introuvables == []
    # Un rendement « après frais » calculé par l'agent (déduction en double) est rejeté.
    net = formater_pourcentage(v["rendement_annuel"] - v["frais_annuels"], 2)
    faux = f"Après frais, le portefeuille rapporterait {net} par an."
    assert verifier_argument({"texte": faux, "pieces": ["P2"]}, dossier).introuvables
