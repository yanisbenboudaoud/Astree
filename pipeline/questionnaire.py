"""Questionnaire investisseur (#84) : les réponses deviennent un fichier profil valide.

Un Pacte n'existait que si quelqu'un écrivait ``personas/<id>.json`` à la main.
Le questionnaire laisse un vrai utilisateur créer le sien : une quinzaine de
questions (``config/questionnaire.json``), et Python transforme les réponses en
un profil au format de ``personas/``, avec une justification par règle qui cite
la réponse d'origine. **Aucun LLM**, aucun nom de profil dans le code.

Barème (paramètres dans la config, étiquette « hypothese ») :
1. **Plafond de capacité** : la baisse que la situation permet (horizon, retraits,
   coussin, part du patrimoine, revenu) ; le facteur le plus contraignant l'emporte.
2. **Resserrement** : le seuil est resserré d'un cran si la personne vend quand ça
   baisse ; le vécu de 2022 l'emporte sur la réaction imaginée quand la personne
   investissait déjà. ``pire_baisse_max.seuil`` en découle, arrondi vers le prudent.
3. La baisse **vraiment acceptée** n'est pas demandée ici : le Pacte vécu (#68) la
   mesure ensuite devant de vrais jours de marché, et le seuil mesuré l'emporte.
4. Les préférences (crypto, concentration, hors du Canada, exclusions, objectif,
   règle personnelle) deviennent directement des règles ``plafond``,
   ``critere_documentaire`` ou ``qualitative``.

Une réponse manquante ne devine rien : la règle correspondante n'est pas créée
et un contrôle « à vérifier » le dit (``detail_bareme``). Seule exception, la
question facultative « hors du Canada » (#112) : passée, elle ne crée ni règle
ni contrôle.

Usage ::

    python -m pipeline.questionnaire --questions                 # questions prêtes à afficher
    python -m pipeline.questionnaire reponses.json               # écrit personas/<id>.json
    python -m pipeline.questionnaire reponses.json --sortie profil.json
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date as Date
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.pacte import CHEMIN_SCHEMA, DOSSIER_PERSONAS, erreurs_profil
from pipeline.simulation import formater_pourcentage
from pipeline.univers import charger_univers

CHEMIN_CONFIG = Path(__file__).resolve().parent.parent / "config" / "questionnaire.json"
FORMAT_IDENTIFIANT = re.compile(r"[a-z][a-z0-9_]*")
QUESTIONS_TOLERANCE = ("reaction", "vecu_2022")
CHOIX_AUCUNE_EXCLUSION = "aucune"


class ReponsesInvalides(ValueError):
    """Réponses ou saisies refusées ; ``erreurs`` donne chaque motif, lisible par l'utilisateur."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__(" ; ".join(erreurs))


# --- Configuration et questions ----------------------------------------------------


@lru_cache(maxsize=1)
def charger_config() -> dict[str, Any]:
    """``config/questionnaire.json`` (mis en cache : ne pas le modifier)."""
    return json.loads(CHEMIN_CONFIG.read_text(encoding="utf-8"))


def _questions_config() -> dict[str, dict[str, Any]]:
    return {q["id"]: q for q in charger_config()["questions"]}


def _choix(question: dict[str, Any], id_choix: str) -> dict[str, Any] | None:
    return next((c for c in question.get("choix", []) if c["id"] == id_choix), None)


@lru_cache(maxsize=1)
def questions() -> list[dict[str, Any]]:
    """Les questions prêtes à afficher, dans l'ordre (copie : la config en cache reste intacte)."""
    return copy.deepcopy(charger_config()["questions"])


# --- Validation des réponses -------------------------------------------------------


def valider_reponses(reponses: dict[str, Any]) -> dict[str, Any]:
    """Réponses nettoyées (texte sans espaces superflus) ; ``ReponsesInvalides`` sinon."""
    if not isinstance(reponses, dict):
        raise ReponsesInvalides(["Les réponses doivent être un objet JSON : identifiant de question → réponse"])
    config = _questions_config()
    erreurs, propres = [], {}
    for qid in reponses:
        if qid not in config:
            erreurs.append(f"Question inconnue : « {qid} »")
    for qid, question in config.items():
        valeur = reponses.get(qid)
        if valeur is None or valeur == "" or valeur == []:
            if question.get("obligatoire"):
                erreurs.append(f"Réponse obligatoire manquante : « {question['libelle']} »")
            continue
        if question["type"] == "choix":
            if not isinstance(valeur, str) or _choix(question, valeur) is None:
                erreurs.append(f"Réponse « {valeur} » inconnue pour « {qid} »")
                continue
        elif question["type"] == "choix_multiples":
            if not isinstance(valeur, list) or any(not isinstance(v, str) or _choix(question, v) is None for v in valeur):
                erreurs.append(f"Réponses inconnues pour « {qid} » : {valeur}")
                continue
            if CHOIX_AUCUNE_EXCLUSION in valeur and len(valeur) > 1:
                erreurs.append(f"« {qid} » : « aucune » ne se combine pas avec d'autres choix")
                continue
            valeur = list(dict.fromkeys(valeur))
        elif question["type"] == "texte":
            if not isinstance(valeur, str):
                erreurs.append(f"« {qid} » doit être un texte")
                continue
            valeur = " ".join(valeur.split())
            if len(valeur) > question.get("longueur_max", 120):
                erreurs.append(f"« {qid} » : {question.get('longueur_max', 120)} caractères au plus")
                continue
            if not valeur:
                continue
        propres[qid] = valeur
    if erreurs:
        raise ReponsesInvalides(erreurs)
    return propres


# --- Barème ------------------------------------------------------------------------


@dataclass
class Analyse:
    """Tout ce que le barème tire des réponses, pour le profil et pour son explication."""

    horizon_ans: list
    profil_risque: str
    regles: list[dict[str, Any]] = field(default_factory=list)
    detail_regles: list[dict[str, Any]] = field(default_factory=list)
    resserrement: dict[str, Any] | None = None
    capacite: dict[str, Any] | None = None
    seuil: dict[str, Any] | None = None
    controles: list[dict[str, Any]] = field(default_factory=list)


def plafond_capacite(reponses: dict[str, Any]) -> dict[str, Any] | None:
    """Plafond de capacité : le plus contraignant des plafonds donnés par les réponses (None sans contrainte)."""
    config_questions = _questions_config()
    plafonds = charger_config()["bareme"]["capacite"]["plafonds"]
    contraintes = []
    for qid, table in plafonds.items():
        if qid in reponses and table.get(reponses[qid]) is not None:
            choix = _choix(config_questions[qid], reponses[qid])
            contraintes.append({"question": qid, "reponse": choix["libelle"], "plafond": table[reponses[qid]]})
    if not contraintes:
        return None
    plafond = max(c["plafond"] for c in contraintes)  # le plus proche de zéro est le plus contraignant
    return {"plafond": plafond, "decisifs": [c for c in contraintes if c["plafond"] == plafond], "contraintes": contraintes}


def resserrement(reponses: dict[str, Any]) -> dict[str, Any]:
    """La personne vend-elle quand ça baisse ? Le vécu de 2022 décide quand elle investissait, sinon la réaction."""
    config_questions = _questions_config()
    vecu = _choix(config_questions["vecu_2022"], reponses["vecu_2022"]) if "vecu_2022" in reponses else None
    reaction = _choix(config_questions["reaction"], reponses["reaction"]) if "reaction" in reponses else None
    if vecu and vecu.get("investissait"):
        source, vend = "vecu_2022", bool(vecu.get("vend"))
    elif reaction:
        source, vend = "reaction", bool(reaction.get("vend"))
    else:
        source, vend = None, False
    return {
        "resserre": vend,
        "cran": charger_config()["bareme"]["resserrement"]["cran_resserrement"],
        "source": source,
        "reponse_source": (vecu if source == "vecu_2022" else reaction or {}).get("libelle"),
    }


def arrondir_vers_le_prudent(seuil: float) -> float:
    """Arrondi au nombre de décimales de pourcentage de la config, vers zéro (le plus prudent)."""
    decimales = charger_config()["bareme"]["arrondi"]["decimales_pourcentage"]
    echelle = 100 * 10 ** decimales
    return math.ceil(round(seuil * echelle, 6)) / echelle


def profil_risque_du_seuil(seuil: float | None) -> str:
    if seuil is None:
        return "non_determine"
    for tranche in charger_config()["bareme"]["profil_risque"]["tranches"]:
        if seuil >= tranche["seuil_min"]:
            return tranche["profil"]
    return charger_config()["bareme"]["profil_risque"]["tranches"][-1]["profil"]


def _part(valeur: float) -> str:
    return f"{valeur * 100:.0f} %"


def _citation(question: dict[str, Any], valeur: Any) -> str:
    if isinstance(valeur, list):
        return ", ".join(f"« {_choix(question, v)['libelle']} »" for v in valeur)
    choix = _choix(question, valeur) if question["type"] != "texte" else None
    return f"« {choix['libelle'] if choix else valeur} »"


def analyser(reponses: dict[str, Any], date_reponses: str) -> Analyse:
    """Applique le barème aux réponses validées. Fonction pure : mêmes réponses, même analyse."""
    q = _questions_config()
    entete = f"Réponse au questionnaire du {date_reponses}"
    horizon = _choix(q["horizon"], reponses["horizon"])["horizon_ans"]

    comportement = resserrement(reponses)
    capacite = plafond_capacite(reponses)
    seuil = None
    if capacite:
        brut = capacite["plafond"] * (1 - comportement["cran"]) if comportement["resserre"] else capacite["plafond"]
        seuil = {"valeur": arrondir_vers_le_prudent(brut), "brut": round(brut, DECIMALES_VALEURS),
                 "resserre": comportement["resserre"]}

    analyse = Analyse(
        horizon_ans=list(horizon),
        profil_risque=profil_risque_du_seuil(seuil["valeur"] if seuil else None),
        resserrement=comportement, capacite=capacite, seuil=seuil,
    )

    def ajouter(regle: dict[str, Any], etiquette: str, questions_sources: list[str], explication: str) -> None:
        analyse.regles.append(regle)
        analyse.detail_regles.append({
            "id": regle["id"], "etiquette": etiquette,
            "reponses": {qid: reponses[qid] for qid in questions_sources if qid in reponses},
            "explication": explication,
        })

    def manquante(qid: str, consequence: str) -> None:
        analyse.controles.append({"statut": "a_verifier", "regle": "questionnaire",
                                  "message": f"Réponse manquante (« {q[qid]['nom_court']} ») : {consequence}"})

    # 1. Pire baisse tolérée : le plafond de capacité, resserré d'un cran si la personne vend.
    if seuil:
        raisons = ", ".join(f"{q[d['question']]['nom_court'].lower()} : « {d['reponse']} »" for d in capacite["decisifs"])
        texte_resserrement = (f", resserré d'un cran car « {comportement['reponse_source']} »"
                              if comportement["resserre"] else "")
        justification = (
            f"{entete}. Le seuil vient de votre capacité à encaisser une baisse : plafond "
            f"{formater_pourcentage(capacite['plafond'])} ({raisons}){texte_resserrement}. Seuil "
            f"{formater_pourcentage(seuil['valeur'])}, arrondi au dixième de point vers le plus prudent. "
            "La baisse que vous acceptez vraiment se mesure ensuite devant de vrais jours de marché (Pacte vécu). "
            "Barème : hypothèse de l'équipe (config/questionnaire.json)."
        )
        ajouter({"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": seuil["valeur"],
                 "libelle": f"Pire baisse tolérée : {formater_pourcentage(seuil['valeur'])}", "justification": justification},
                "hypothese", [*charger_config()["bareme"]["capacite"]["plafonds"], *QUESTIONS_TOLERANCE],
                f"Capacité {formater_pourcentage(capacite['plafond'])}"
                + (f", resserrée d'un cran (« {comportement['reponse_source']} »)" if comportement["resserre"] else "")
                + f" : seuil {formater_pourcentage(seuil['valeur'])}.")
    else:
        analyse.controles.append({"statut": "a_verifier", "regle": "questionnaire",
                                  "message": "Aucun plafond de capacité : aucune règle de pire baisse n'est créée"})

    # 2. Cryptoactifs.
    if "crypto" in reponses:
        maximum = _choix(q["crypto"], reponses["crypto"])["max"]
        libelle = "Crypto : exclue" if maximum == 0 else f"Crypto : {_part(maximum)} du portefeuille au maximum"
        ajouter({"id": "plafond_crypto", "type": "plafond", "categories": ["crypto"], "max": maximum, "libelle": libelle,
                 "justification": f"{entete} : {_citation(q['crypto'], reponses['crypto'])}."},
                "fait", ["crypto"], libelle)
    else:
        manquante("crypto", "aucun plafond sur les cryptoactifs n'est créé")

    # 3. Concentration dans un secteur (technologie).
    if "concentration" in reponses:
        maximum = _choix(q["concentration"], reponses["concentration"])["max"]
        if maximum is not None:
            libelle = f"Technologie : {_part(maximum)} du portefeuille au maximum"
            ajouter({"id": "plafond_tech", "type": "plafond", "categories": ["tech"], "max": maximum, "libelle": libelle,
                     "justification": f"{entete} : {_citation(q['concentration'], reponses['concentration'])}."},
                    "fait", ["concentration"], libelle)
    else:
        manquante("concentration", "aucun plafond sectoriel n'est créé")

    # 4. Placements hors du Canada (#112) : question facultative, passée sans aucun contrôle.
    if "hors_canada" in reponses:
        maximum = _choix(q["hors_canada"], reponses["hors_canada"])["max"]
        if maximum is not None:
            libelle = f"Hors du Canada : {_part(maximum)} du portefeuille au maximum"
            ajouter({"id": "plafond_hors_canada", "type": "plafond", "categories": ["hors_canada"], "max": maximum,
                     "libelle": libelle,
                     "justification": f"{entete} : {_citation(q['hors_canada'], reponses['hors_canada'])}. Hors du Canada : "
                                      "tout titre qui n'est pas coté à Toronto (config/categories.json), donc en dollars "
                                      "américains dans l'univers d'actifs : un risque de change en plus du risque des titres."},
                    "fait", ["hors_canada"], libelle)

    # 5. Exclusions : catégorie exclue (plafond à 0) ou critère documentaire.
    if "exclusions" in reponses:
        for id_choix in reponses["exclusions"]:
            choix = _choix(q["exclusions"], id_choix)
            justification = f"{entete} : « {choix['libelle']} » parmi les titres que vous ne voulez pas détenir."
            if "categorie" in choix:
                ajouter({"id": f"exclusion_{choix['categorie']}", "type": "plafond", "categories": [choix["categorie"]],
                         "max": 0.0, "libelle": f"{choix['libelle']} : exclues", "justification": justification},
                        "fait", ["exclusions"], f"{choix['libelle']} : exclues")
            elif "critere" in choix:
                libelle = "Exclure les entreprises liées à des controverses environnementales ou sociales importantes"
                ajouter({"id": "controverses_esg", "type": "critere_documentaire", "critere": choix["critere"],
                         "libelle": libelle, "justification": f"{justification} Il faut une source documentée : sans elle, le Greffier rend « à vérifier »."},
                        "fait", ["exclusions"], libelle)
    else:
        manquante("exclusions", "aucune exclusion n'est créée")

    # 6. Objectif et règle personnelle : règles qualitatives, à juger par l'utilisateur.
    if "objectif" in reponses:
        libelle = _choix(q["objectif"], reponses["objectif"])["regle"]
        ajouter({"id": "objectif", "type": "qualitative", "libelle": libelle,
                 "justification": f"{entete} : {_citation(q['objectif'], reponses['objectif'])}. Non mesurable par calcul : à juger par l'utilisateur."},
                "fait", ["objectif"], libelle)
    if "regle_perso" in reponses:
        ajouter({"id": "regle_personnelle", "type": "qualitative", "libelle": reponses["regle_perso"],
                 "justification": f"Règle personnelle écrite au questionnaire du {date_reponses}, reprise telle quelle (aucun LLM)."},
                "fait", ["regle_perso"], reponses["regle_perso"])

    # Contrôles sans effet sur les règles.
    for qid in charger_config()["bareme"]["capacite"]["plafonds"]:
        if qid not in reponses:
            manquante(qid, "le plafond de capacité est calculé sans cette réponse")
    if "quiz_baisse" in reponses and not _choix(q["quiz_baisse"], reponses["quiz_baisse"]).get("juste"):
        analyse.controles.append({"statut": "a_verifier", "regle": "questionnaire",
                                  "message": "La règle de pire baisse est peut-être mal comprise : après une baisse de 50 %, "
                                             "il faut une hausse de 100 % pour revenir au point de départ (aucune pénalité)."})
    return analyse


# --- Profil ------------------------------------------------------------------------


def _erreurs_saisies(capital: Any, portefeuille: Any, identifiant: str, date_reponses: str) -> list[str]:
    erreurs = []
    if not isinstance(identifiant, str) or not FORMAT_IDENTIFIANT.fullmatch(identifiant) or identifiant == CHEMIN_SCHEMA.stem:
        erreurs.append(f"Identifiant invalide : « {identifiant} » (minuscules, chiffres et « _ », commence par une lettre)")
    try:
        Date.fromisoformat(date_reponses)
    except (TypeError, ValueError):
        erreurs.append(f"Date invalide : « {date_reponses} » (format AAAA-MM-JJ)")
    if isinstance(capital, bool) or not isinstance(capital, (int, float)) or capital <= 0:
        erreurs.append("Capital fictif invalide : un montant positif en CAD")
    if not isinstance(portefeuille, list) or not portefeuille:
        erreurs.append("Portefeuille vide : une liste de lignes { ticker, poids }")
    else:
        connus = {t["ticker"] for t in charger_univers()}
        inconnus = sorted({str(ligne.get("ticker")) for ligne in portefeuille
                           if not isinstance(ligne, dict) or ligne.get("ticker") not in connus})
        if inconnus:
            erreurs.append(f"Titres hors de l'univers : {', '.join(inconnus)}")
    return erreurs


def profil_depuis_reponses(
    reponses: dict[str, Any],
    capital: float,
    portefeuille: list[dict[str, Any]],
    date_reponses: str,
    *,
    identifiant: str = "investisseur",
    nom: str = "Investisseur",
    decision: dict[str, Any] | None = None,
    etiquette_reponses: str = "fait",
) -> dict[str, Any]:
    """Fichier profil (format de ``personas/``) tiré des réponses ; valide pour ``pipeline.pacte``.

    Le profil garde ses réponses (champ ``questionnaire``) : pendant un procès, elles
    deviennent une pièce ``declaree`` et leurs contradictions des contrôles (#85).
    ``etiquette_reponses`` : ``fait`` pour les réponses d'une vraie personne, ``fictif``
    pour des réponses préenregistrées de démonstration.

    Raises:
        ReponsesInvalides: réponse inconnue, saisie invalide, aucune règle, ou profil refusé
            par ``erreurs_profil`` (chaque motif dans ``erreurs``).
    """
    erreurs = _erreurs_saisies(capital, portefeuille, identifiant, date_reponses)
    if erreurs:
        raise ReponsesInvalides(erreurs)
    if etiquette_reponses not in ("fait", "fictif"):
        raise ReponsesInvalides([f"Étiquette des réponses invalide : « {etiquette_reponses} » (fait ou fictif)"])
    propres = valider_reponses(reponses)
    analyse = analyser(propres, date_reponses)
    if not analyse.regles:
        raise ReponsesInvalides(["Aucune règle : répondez au moins à une question de capacité ou de préférence"])
    profil = {
        "id": identifiant,
        "nom": nom,
        "etiquette": "fictif",  # outil éducatif : tout profil reste un scénario simulé (schéma)
        "profil_risque": analyse.profil_risque,
        "horizon_ans": analyse.horizon_ans,
        "capital_fictif_cad": capital,
        "portefeuille": [{"ticker": ligne["ticker"], "poids": ligne["poids"]} for ligne in portefeuille],
        "pacte": {"date_signature": date_reponses, "regles": analyse.regles},
        "questionnaire": {"date": date_reponses, "etiquette": etiquette_reponses, "reponses": propres},
    }
    if decision is not None:
        profil["decision_demo"] = decision
    erreurs = erreurs_profil(profil, nom_fichier=identifiant)
    if erreurs:
        raise ReponsesInvalides(erreurs)
    return profil


def detail_bareme(reponses: dict[str, Any], date_reponses: str) -> dict[str, Any]:
    """Quelle réponse a produit quelle règle, la capacité, le resserrement et les contrôles « à vérifier »."""
    analyse = analyser(valider_reponses(reponses), date_reponses)
    return {
        "date": date_reponses,
        "etiquette_bareme": charger_config()["etiquette"],
        "resserrement": analyse.resserrement,
        "capacite": analyse.capacite,
        "seuil_retenu": analyse.seuil,
        "profil_risque": analyse.profil_risque,
        "regles": analyse.detail_regles,
        "controles": analyse.controles,
        "experience": valider_reponses(reponses).get("experience", []),
        "limites": [
            "Un questionnaire mesure ce que la personne dit ; le Pacte vécu (#68) mesure ce qu'elle choisit "
            "devant de vrais jours de marché. Les deux restent des indices, pas des garanties.",
            "Les barèmes sont des hypothèses de l'équipe, pas une méthode réglementaire.",
        ],
    }


def controle_experience(experience: list[str], decision: dict[str, Any]) -> dict[str, Any] | None:
    """Contrôle « à vérifier » si la décision porte sur un type de titre jamais détenu (question « experience »).

    Les types viennent de ``asset_class`` (assets_universe.csv), reliés aux choix par leurs ``classes``
    dans la config. Ne bloque rien ; un titre hors univers est laissé à l'agent Profil. ``None`` si rien à signaler.
    """
    choix = _questions_config()["experience"]["choix"]
    connues = {classe for c in choix if c["id"] in experience for classe in c.get("classes", [])}
    libelle_classe = {classe: c["libelle"] for c in choix for classe in c.get("classes", [])}
    classes = {t["ticker"]: t["asset_class"] for t in charger_univers()}
    tickers = [decision["ticker"]] if decision["type"] == "position" else [ligne["ticker"] for ligne in decision["panier"]]
    nouveaux = {t: classes[t] for t in tickers if t in classes and classes[t] not in connues}
    if not nouveaux:
        return None
    types = sorted({libelle_classe.get(classe, classe) for classe in nouveaux.values()})
    return {
        "statut": "a_verifier",
        "regle": "questionnaire",
        "message": f"Type de titre jamais détenu selon le questionnaire ({', '.join(types)}) : "
                   f"{', '.join(sorted(nouveaux))}. Rien n'est bloqué : à garder en tête avant de décider.",
    }


# --- Contradictions et pièce du procès (#85) ---------------------------------------

CONTROLE_COHERENCE = "coherence_questionnaire"
NOM_OUTIL_PIECE = "lire_questionnaire"


def _libelle_reponse(qid: str, valeur: Any) -> str:
    """« Libellé » de la réponse, tel qu'affiché dans le questionnaire (texte libre : repris tel quel)."""
    return _citation(_questions_config()[qid], valeur)


def contradictions(reponses: dict[str, Any]) -> list[dict[str, Any]]:
    """Réponses qui se contredisent, selon les règles de ``config/questionnaire.json`` (aucun LLM).

    Une contradiction est une paire de réponses incompatibles (ex. : « J'en rachète » et « J'ai
    vendu » en 2022). Elle ne change aucune règle du Pacte.

    Returns:
        ``[{"id", "questions", "message"}]``, dans l'ordre de la config ; liste vide si tout est cohérent.
    """
    reponses = valider_reponses(reponses)
    config = charger_config()["contradictions"]
    trouvees = []
    for paire in config["paires"]:
        if all(reponses.get(qid) in valeurs for qid, valeurs in paire["si"].items()):
            citations = {qid: _libelle_reponse(qid, reponses[qid]) for qid in paire["si"]}
            trouvees.append({"id": paire["id"], "questions": list(paire["si"]), "message": paire["message"].format_map(citations)})

    return trouvees


def piece_questionnaire(profil: dict[str, Any], id_piece: str) -> dict[str, Any]:
    """Pièce ``declaree`` : les réponses au questionnaire et ce que le barème en tire.

    Le Procureur et l'Avocat peuvent la citer ; ``verifier_chiffres`` en lit les valeurs
    (date, horizon, plafond de capacité, seuil retenu).

    Args:
        profil: profil validé qui porte ``questionnaire`` (``date``, ``reponses``, ``etiquette``).
        id_piece: numéro attribué par le Tribunal.
    """
    bloc = profil["questionnaire"]
    reponses = valider_reponses(bloc["reponses"])
    analyse = analyser(reponses, bloc["date"])
    capacite, seuil = analyse.capacite, analyse.seuil
    trouvees = contradictions(reponses)
    q = _questions_config()
    valeurs = {
        "date_reponses": bloc["date"],
        "horizon_ans": analyse.horizon_ans,
        "capacite_plafond": capacite["plafond"] if capacite else None,
        "seuil_retenu": seuil["valeur"] if seuil else None,
        "seuil_resserre": bool(seuil and seuil["resserre"]),
        "questions": [q[qid]["nom_court"] for qid in reponses],
        "reponses": [_libelle_reponse(qid, valeur) for qid, valeur in reponses.items()],
        "contradictions": [c["id"] for c in trouvees],
    }
    morceaux = [f"Capacité {formater_pourcentage(capacite['plafond'])}" if capacite else "Capacité sans plafond"]
    if seuil:
        morceaux.append(f"seuil retenu {formater_pourcentage(seuil['valeur'])}" + (" (resserré)" if seuil["resserre"] else ""))
    if trouvees:
        morceaux.append(f"{len(trouvees)} contradiction{'s' if len(trouvees) > 1 else ''}")
    etiquette = bloc.get("etiquette", "fait")
    provenance = "Réponses préenregistrées d'un profil fictif" if etiquette == "fictif" else "Vos réponses"
    return {
        "id": id_piece,
        "type": "declaree",
        "etiquette": etiquette,
        "titre": f"Questionnaire : {len(reponses)} réponses du {bloc['date']}",
        "outil": NOM_OUTIL_PIECE,
        "valeurs": valeurs,
        "valeur_affichee": " · ".join(morceaux),
        "source": f"{provenance} au questionnaire du {bloc['date']}",
        "traitement": "Barème de config/questionnaire.json : capacité = plafond le plus contraignant ; "
                      "seuil retenu = ce plafond, resserré d'un cran si la personne vend, arrondi vers le "
                      "prudent. Contradictions : règles de la même config. Aucun LLM.",
        "limites": "Un questionnaire mesure ce que la personne dit, pas ce qu'elle fera. "
                   "Barèmes et règles de contradiction : hypothèses de l'équipe.",
    }


def controles_questionnaire(
    profil: dict[str, Any],
    id_piece: str,
    decision: dict[str, Any] | None = None,
    piece_calibrage: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Contrôles « à vérifier » tirés du questionnaire, à verser au contrat.

    - un contrôle ``coherence_questionnaire`` par contradiction ;
    - si le Pacte vécu (#68) a mesuré un autre seuil que le seuil retenu au questionnaire,
      un contrôle ``coherence_questionnaire`` qui le dit (le seuil mesuré l'emporte) ;
    - ``controle_experience`` si la décision porte sur un type de titre jamais détenu.
    """
    bloc = profil["questionnaire"]
    reponses = valider_reponses(bloc["reponses"])
    controles = [
        {"statut": "a_verifier", "regle": CONTROLE_COHERENCE, "message": f"Questionnaire : {c['message']}",
         "pieces": [id_piece]}
        for c in contradictions(reponses)
    ]

    seuil = analyser(reponses, bloc["date"]).seuil
    mesure = piece_calibrage["valeurs"].get("seuil_mesure") if piece_calibrage else None
    if seuil and mesure is not None and round(mesure, 3) != round(seuil["valeur"], 3):
        controles.append({
            "statut": "a_verifier",
            "regle": CONTROLE_COHERENCE,
            "message": f"Vous aviez déclaré {formater_pourcentage(seuil['valeur'])} au questionnaire ; devant de "
                       f"vrais jours de marché, vous êtes resté jusqu'à {formater_pourcentage(mesure)}. "
                       "Le seuil mesuré l'emporte.",
            "pieces": [id_piece, piece_calibrage["id"]],
        })

    if decision is not None:
        experience = controle_experience(reponses.get("experience", []), decision)
        if experience:
            controles.append({**experience, "pieces": [id_piece]})
    return controles


# --- Commande ----------------------------------------------------------------------


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description="Questionnaire investisseur (#84) : réponses → fichier profil")
    lecteur.add_argument("reponses", nargs="?", type=Path, help="fichier JSON : id, nom, date, capital_cad, portefeuille, reponses")
    lecteur.add_argument("--questions", action="store_true", help="afficher les questions prêtes à afficher (JSON)")
    lecteur.add_argument("--sortie", type=Path, help="fichier profil à écrire (défaut : personas/<id>.json)")
    lecteur.add_argument("--forcer", action="store_true", help="remplacer le fichier de sortie s'il existe")
    options = lecteur.parse_args(arguments)

    if options.questions:
        print(json.dumps(questions(), ensure_ascii=False, indent=2))
        return 0
    if options.reponses is None:
        lecteur.error("indiquez un fichier de réponses, ou --questions")

    saisie = json.loads(options.reponses.read_text(encoding="utf-8"))
    date_reponses = saisie.get("date") or Date.today().isoformat()
    try:
        profil = profil_depuis_reponses(
            saisie.get("reponses", {}), saisie.get("capital_cad"), saisie.get("portefeuille"), date_reponses,
            identifiant=saisie.get("id", "investisseur"), nom=saisie.get("nom", "Investisseur"),
            decision=saisie.get("decision"),
        )
    except ReponsesInvalides as erreur:
        print("Réponses refusées :", *erreur.erreurs, sep="\n- ", file=sys.stderr)
        return 1

    sortie = options.sortie or DOSSIER_PERSONAS / f"{profil['id']}.json"
    if sortie.exists() and not options.forcer:
        print(f"{sortie} existe déjà : choisissez un autre id ou --sortie, ou ajoutez --forcer", file=sys.stderr)
        return 1
    sortie.write_text(json.dumps(profil, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    detail = detail_bareme(saisie.get("reponses", {}), date_reponses)
    print(f"Profil écrit : {sortie} (profil de risque : {profil['profil_risque']})")
    for regle, explication in zip(profil["pacte"]["regles"], detail["regles"]):
        print(f"- {regle['libelle']}  [{explication['etiquette']}]")
    for controle in detail["controles"]:
        print(f"  à vérifier : {controle['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
