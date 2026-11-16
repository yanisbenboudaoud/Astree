"""L'orchestrateur et le débat mesurés (#167) : lecture des traces, mesures et rapport, sans AWS."""

import io
import json

from pipeline.orchestrateur import RAISON_D_OFFICE
from validation.evaluation_orchestrateur import (
    groupe_decision,
    groupe_profil,
    lire_proces_locaux,
    lire_traces_s3,
    mesurer,
    motif_general,
    genre_motif,
    nom_bucket_projet,
    outils_reserves,
    rapport,
    rassembler,
)

POSITION = {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel",
            "libelle": "30 % en TSLA"}


def appel(outil, entree=None, sortie="P2", raison="Une raison courte"):
    return {"etape": "orchestrateur", "outil": outil, "raison": raison, "entree": entree or {}, "sortie": sortie}


def contrat(persona="robert", decision=POSITION, orchestrateur=(), debat=(), rejetes=(), requisitoire=1,
            plaidoirie=1, questions=()):
    trace = [{"etape": "agent_profil", "outil": "bedrock", "entree": "", "sortie": {}}, *orchestrateur,
             {"etape": "procureur", "outil": "bedrock", "entree": [], "sortie": [{}] * (requisitoire + len(
                 [r for r in rejetes if r == "requisitoire"]))},
             {"etape": "avocat", "outil": "bedrock", "entree": [], "sortie": [{}] * (plaidoirie + len(
                 [r for r in rejetes if r == "plaidoirie"]))},
             *debat]
    return {"persona": persona, "decision": decision, "trace": trace,
            "requisitoire": [{}] * requisitoire, "plaidoirie": [{}] * plaidoirie,
            "arguments_rejetes": [{"cote": c} for c in rejetes],
            **({"contre_interrogatoire": list(questions)} if questions else {})}


SIMULATION_COMPLETE = appel("simuler_portefeuille", {"ticker": "TSLA", "taille": 0.3, "periode": "complete"})


def relance(etape, motif):
    return {"etape": etape, "outil": "bedrock_correction", "entree": {"argument": "…", "motif": motif}, "sortie": {}}


# --- Lecture d'une trace --------------------------------------------------------------

def test_simulation_d_office_et_pieces_d_office_hors_budget():
    m = mesurer([contrat(orchestrateur=[
        appel("indicateurs_actif"),
        appel("simuler_portefeuille", {"periode": "complete"}, raison=RAISON_D_OFFICE),
        appel("points_de_bascule", raison=f"{RAISON_D_OFFICE} : une règle calculable du Pacte est en violation"),
    ])])
    assert m.appels_par_proces == [1]
    assert m.simulation_spontanee == 0 and m.simulation_d_office == 1
    assert m.d_office == {"simuler_portefeuille": 1, "points_de_bascule": 1}


def test_simulation_demandee_par_le_modele():
    m = mesurer([contrat(orchestrateur=[SIMULATION_COMPLETE])])
    assert m.simulation_spontanee == 1 and m.simulation_d_office == 0


def test_budget_refus_compris():
    neuf = [SIMULATION_COMPLETE] * 8 + [appel("indicateurs_actif", sortie="Erreur : Budget d'appels atteint")]
    m = mesurer([contrat(orchestrateur=neuf), contrat(orchestrateur=[SIMULATION_COMPLETE] * 8)])
    assert m.appels_par_proces == [9, 8]
    assert m.depassements_budget == 1
    assert m.proces_dans_budget == 1


def test_refus_regroupes_par_motif_sans_le_titre():
    sortie = "Erreur : Aucun document sur NVDA pour le critère « controverse_esg_importante » : source manquante"
    m = mesurer([contrat(orchestrateur=[SIMULATION_COMPLETE, appel("rechercher_documents", sortie=sortie)])])
    assert m.refus == {"Aucun document sur <titre> pour le critère « controverse_esg_importante » : source manquante": 1}
    assert m.appels_executes == 1
    # un appel refusé ne compte pas comme un outil obtenu
    assert m.outils_par_profil["robert"][1]["rechercher_documents"] == 0


def test_motif_general_masque_l_outil():
    assert motif_general("Erreur : Outil « verifier_pacte » non autorisé") == "Outil « <outil> » non autorisé"


def test_debat_renvoyes_corriges_et_rejetes():
    m = mesurer([contrat(
        debat=[relance("procureur", "« −31 % » introuvable dans P1"),
               relance("procureur", "Conseil personnalisé : « vous devriez »"),
               relance("avocat", "« 4 » introuvable dans P2 ; Promesse ou prévision sur l'avenir : « va monter »")],
        rejetes=["requisitoire"], requisitoire=3, plaidoirie=2)])
    procureur, avocat = m.cotes["requisitoire"], m.cotes["plaidoirie"]
    assert (procureur.proposes, procureur.renvoyes, procureur.corriges, procureur.rejetes) == (4, 2, 1, 1)
    assert procureur.motifs == {"chiffres": 1, "cadre": 1}
    assert (avocat.proposes, avocat.renvoyes, avocat.corriges) == (2, 1, 1)
    assert avocat.motifs == {"chiffres et cadre": 1}


def test_contre_interrogatoire_budget_de_quatre():
    question = {"trace": [appel("indicateurs_actif")] * 5}
    m = mesurer([contrat(questions=[question, {"trace": []}])])
    assert (m.questions, m.questions_dans_budget) == (2, 1)


def test_appels_bedrock_comptes_dans_la_trace():
    m = mesurer([contrat(debat=[relance("procureur", "« 3 » introuvable dans P1")])])
    assert m.appels_bedrock == [4]  # Agent Profil, Procureur, Avocat, une relance


def test_groupes():
    assert groupe_profil("investisseur_22c8053eb316") == "questionnaire"
    assert groupe_profil("mateo") == "mateo"
    assert groupe_decision(POSITION) == "position TSLA"
    panier = {"type": "reallocation", "panier": [{"ticker": "QQQ", "poids": 0.5}, {"ticker": "ETH-USD", "poids": 0.5}]}
    assert groupe_decision(panier) == "réallocation ETH-USD, QQQ"


def test_outil_reserve_a_un_profil():
    m = mesurer([contrat("mateo", orchestrateur=[SIMULATION_COMPLETE, appel("rechercher_documents")]),
                 contrat("robert", orchestrateur=[SIMULATION_COMPLETE])])
    assert outils_reserves(m) == {"rechercher_documents": ["mateo"]}


def test_genre_motif_autre():
    assert genre_motif("motif inattendu") == "autre"


# --- Lecture des sources --------------------------------------------------------------

class FauxS3:
    def __init__(self, objets):
        self.objets = objets
        self.lus = []

    def get_paginator(self, nom):
        assert nom == "list_objects_v2"
        objets = self.objets

        class Paginateur:
            def paginate(self, Bucket, Prefix):
                return [{"Contents": [{"Key": k} for k in objets if k.startswith(Prefix)]}]
        return Paginateur()

    def get_object(self, Bucket, Key):
        self.lus.append(Key)
        return {"Body": io.BytesIO(json.dumps(self.objets[Key]).encode())}


def test_lire_traces_s3_sans_bedrock():
    s3 = FauxS3({"traces/2026-11-15/2026-11-15-aaa.json": {"persona": "robert"},
                 "progression/2026-11-15-aaa.json": {"statut": "termine"}})
    assert lire_traces_s3("bucket", s3) == {"2026-11-15-aaa": {"persona": "robert"}}
    assert s3.lus == ["traces/2026-11-15/2026-11-15-aaa.json"]


def test_nom_du_bucket(monkeypatch):
    monkeypatch.delenv("BUCKET_PROJET", raising=False)

    class FauxSTS:
        def get_caller_identity(self):
            return {"Account": "123456789012"}
    assert nom_bucket_projet(FauxSTS()) == "alphaforge-123456789012"
    monkeypatch.setenv("BUCKET_PROJET", "mon-bucket")
    assert nom_bucket_projet() == "mon-bucket"


def test_union_des_sources_sans_doublon():
    lecture = rassembler({"2026-11-15-a": {"x": 1}}, {"2026-11-15-a": {"x": 2}, "2026-11-14-b": {"x": 3}},
                         "2026-11-15", "bucket")
    assert list(lecture.contrats) == ["2026-11-14-b", "2026-11-15-a"]
    assert lecture.contrats["2026-11-15-a"] == {"x": 1}  # la trace S3 prime
    assert lecture.origines["2026-11-15-a"] == ["S3", "interface"]


def test_rapport_sur_les_proces_de_l_interface():
    locaux = lire_proces_locaux()
    assert len(locaux) == 15
    lecture = rassembler({}, locaux, "2026-11-15", None)
    texte = rapport(lecture, mesurer(lecture.contrats.values()))
    assert "**Lu le 2026-11-15** : 15 procès distincts" in texte
    assert "--local" in texte and "S3 non lu" in texte
    assert "ne sont pas un échantillon planifié" in texte
    for identifiant in locaux:
        assert f"`{identifiant}`" in texte


# --- Plan de procès -------------------------------------------------------------------

from validation import plan_proces  # noqa: E402
from validation.evaluation_orchestrateur import outils_obtenus, section_plan  # noqa: E402

PLAN = {"description": "Plan.", "cout_estime": "0 $.", "repetitions": 2, "profils": ["robert", "amira"],
        "decisions": [{"id": "tsla", "demande": "30 % en TSLA"}]}


def test_tenir_plan_reprend_sans_rejouer_ce_qui_est_fait(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_proces, "CHEMIN_PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(plan_proces, "CHEMIN_RESULTATS", tmp_path / "resultats.json")
    (tmp_path / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    (tmp_path / "resultats.json").write_text(json.dumps([
        {"decision": "tsla", "demande": "30 % en TSLA", "profil": "robert", "repetition": 1,
         "proces_id": "p1", "statut": 200, "duree_s": 20.0},
        {"decision": "tsla", "demande": "30 % en TSLA", "profil": "amira", "repetition": 1,
         "proces_id": None, "statut": 429, "duree_s": 0.4},
    ]), encoding="utf-8")
    envois = []

    def envoyer(corps):
        envois.append(corps["profil"])
        return 200, 25.04, f"p{len(envois) + 1}"

    resultats = plan_proces.tenir_plan(envoyer, plan_proces._ecrire)
    assert envois == ["amira", "robert", "amira"]  # la case en échec est rejouée, la case réussie non
    assert len(resultats) == 5  # l'échec reste noté
    assert json.loads((tmp_path / "resultats.json").read_text(encoding="utf-8"))[-1]["duree_s"] == 25.0


def test_section_plan_stabilite_et_duree():
    tsla = contrat(orchestrateur=[SIMULATION_COMPLETE, appel("taille_max_compatible")])
    autre = contrat(orchestrateur=[SIMULATION_COMPLETE, appel("calculer_correlations")])
    lecture = rassembler({"a": tsla, "b": tsla, "c": tsla, "d": autre}, {}, "2026-11-15", "bucket")
    resultats = [
        {"decision": "tsla", "profil": "robert", "repetition": 1, "proces_id": "a", "statut": 200, "duree_s": 20.0},
        {"decision": "tsla", "profil": "robert", "repetition": 2, "proces_id": "b", "statut": 200, "duree_s": 30.0},
        {"decision": "tsla", "profil": "amira", "repetition": 1, "proces_id": "c", "statut": 200, "duree_s": 25.0},
        {"decision": "tsla", "profil": "amira", "repetition": 2, "proces_id": "d", "statut": 200, "duree_s": 40.0},
        {"decision": "tsla", "profil": "amira", "repetition": 2, "proces_id": None, "statut": 429, "duree_s": 0.5},
    ]
    texte = "\n".join(section_plan(lecture, PLAN, resultats))
    assert "4 procès sur 4 lus ; envois en échec : 1 (429)" in texte
    assert "Mêmes outils d'une répétition à l'autre : 1/2" in texte
    assert "min. 20,0, médiane 27,5, max. 40,0 s" in texte
    assert "| 30 % en TSLA | robert | `simuler_portefeuille`, `taille_max_compatible` |" in texte


def test_section_plan_sans_proces_lus():
    lecture = rassembler({}, {}, "2026-11-15", None)
    texte = "\n".join(section_plan(lecture, PLAN, []))
    assert "Aucun procès du plan n'a pu être lu" in texte


def test_outils_obtenus_dans_l_ordre_et_sans_refus():
    c = contrat(orchestrateur=[appel("taille_max_compatible"), SIMULATION_COMPLETE,
                               appel("rechercher_documents", sortie="Erreur : source manquante")])
    assert outils_obtenus(c) == ["simuler_portefeuille", "taille_max_compatible"]
