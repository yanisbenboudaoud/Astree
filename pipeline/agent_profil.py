"""Agent Profil : transforme la demande de l'utilisateur en décision structurée.

Première phase du Tribunal (REFERENCE_DU_PROJET.md, section 4). Le LLM sert seulement à
**comprendre le texte** : il repère le titre, la taille et le financement.
Python vérifie ensuite chaque champ et fait les calculs (ex. : un montant en
dollars converti en part du portefeuille).

Si la demande est incomplète ou ambiguë, l'agent ne devine pas : il ajoute un
contrôle « a_verifier » (règle « interpretation_demande »). Si la décision ne
peut pas être construite (titre hors de l'univers, taille absente…), il ne
renvoie aucune décision : le procès ne peut pas commencer et l'interface doit
demander à l'utilisateur de préciser.

Le code ne connaît aucun persona : ``lancer_agent_profil`` reçoit l'identifiant
de n'importe quel profil, le charge et le valide (``charger_profil`` : un fichier
de ``personas/`` ou un profil créé par le questionnaire, #87), puis ne lit que son
portefeuille et son capital.

Deux types de décisions (REFERENCE_DU_PROJET.md, section 5) :
- « position » : un titre, une taille et un financement ;
- « reallocation » (#16) : un panier de titres avec leurs poids, et la part du
  portefeuille réallouée, prise au prorata de toutes les lignes. Un panier
  vague (« un panier crypto-tech ») n'est jamais complété au hasard : il faut
  que l'utilisateur donne les titres et leurs poids.

Profil à poches (#115, ``pipeline.poches``) : la décision est jugée dans une seule
poche. La poche est celle **imposée** par l'appelant (l'interface), sinon celle que
le modèle **déduit** de la demande, sinon la poche la plus prudente (horizon le plus
court), avec un contrôle « a_verifier ». Le profil est ensuite projeté sur cette
poche : taille, montant et financement se lisent dans la poche, et tout l'aval du
procès travaille sur elle. Sans poches, rien ne change (ni prompt, ni contrat).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.llm import appeler_llm, au_nom_de
from pipeline.pacte import (
    CHEMIN_SCHEMA,
    DOSSIER_PERSONAS,
    PacteInvalide,
    charger_pacte,
    erreurs_profil,
    pacte_pour_contrat,
    piece_pacte,
)
from pipeline.poches import (
    a_des_poches,
    formater_horizon,
    poche_la_plus_prudente,
    profil_de_la_poche,
    trouver_poche,
)
from pipeline.profils import cle_profil, lire_profil_cree
from pipeline.univers import charger_univers

REGLE_CONTROLE = "interpretation_demande"

# Écart d'arrondi toléré sur le total des poids d'un panier, corrigé par
# normalisation (ex. : 3 × 0,3333). Au-delà, la répartition est ambiguë.
TOLERANCE_TOTAL_PANIER = 0.01

# Même format que l'« id » d'un profil (personas/schema_pacte.json). Il empêche
# aussi un identifiant venu de l'interface de désigner un fichier hors de personas/.
FORMAT_IDENTIFIANT = re.compile(r"[a-z][a-z0-9_]*")


class ProfilInconnu(Exception):
    """Aucun fichier profil ne porte cet identifiant : le procès ne peut pas commencer."""


@dataclass
class ResultatAgentProfil:
    """Ce que l'Agent Profil transmet à l'orchestrateur."""

    decision: dict[str, Any] | None  # format « decision » du contrat ; None si impossible
    controles: list[dict[str, Any]] = field(default_factory=list)  # contrôles « a_verifier »
    hypotheses: list[str] = field(default_factory=list)  # à ajouter aux hypothèses du contrat
    trace: list[dict[str, Any]] = field(default_factory=list)  # étapes « agent_profil »
    # Profil jugé (portefeuille, règles typées du Pacte) : le profil validé, ou sa
    # projection sur la poche jugée (#115). Rempli par structurer_decision.
    profil: dict[str, Any] | None = None
    # Remplis par lancer_agent_profil :
    pacte: dict[str, Any] | None = None  # champ « pacte » du contrat
    piece_pacte: dict[str, Any] | None = None  # pièce « Pacte », citable par les agents


def lancer_agent_profil(
    demande: str,
    identifiant_profil: str,
    id_piece_pacte: str,
    poche: str | None = None,
) -> ResultatAgentProfil:
    """Phase 1 du Tribunal : charge et valide le Pacte, puis structure la demande.

    Point d'entrée de l'orchestrateur (#12). Le Pacte est chargé **avant** l'appel
    au LLM : un profil inconnu ou invalide ne coûte aucun appel Bedrock.

    Args:
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        identifiant_profil: ``id`` du profil, c'est-à-dire le nom du fichier
            ``personas/<id>.json`` (n'importe quel profil, pas seulement les profils de test).
        id_piece_pacte: numéro de la pièce « Pacte » (ex. : « P3 »), donné par le
            pipeline, qui numérote toutes les pièces.
        poche: profil à poches (#115) : id de la poche choisie par l'utilisateur ;
            None : le modèle la déduit de la demande.

    Raises:
        ProfilInconnu: aucun profil ne porte cet identifiant.
        PacteInvalide: le fichier profil ne respecte pas le format commun.
        PocheInconnue: ``poche`` donnée, mais absente du profil (vérifié avant Bedrock).
    """
    profil = charger_profil(identifiant_profil)
    if poche is not None:
        trouver_poche(profil, poche)
    resultat = structurer_decision(demande, profil, charger_univers(), poche)
    etape_pacte = {
        "etape": "agent_profil",
        "outil": "charger_pacte",
        "entree": identifiant_profil,
        "sortie": id_piece_pacte,
    }
    resultat.trace = [etape_pacte, *resultat.trace]
    resultat.pacte = pacte_pour_contrat(resultat.profil)
    resultat.piece_pacte = piece_pacte(resultat.profil, id_piece_pacte)
    return resultat


def chemin_profil(identifiant: str) -> Path:
    """Fichier ``personas/<identifiant>.json`` ; lève ``ProfilInconnu`` s'il n'existe pas."""
    if not isinstance(identifiant, str) or not FORMAT_IDENTIFIANT.fullmatch(identifiant):
        raise ProfilInconnu(f"Identifiant de profil invalide : {identifiant!r}")
    chemin = DOSSIER_PERSONAS / f"{identifiant}.json"
    if chemin == CHEMIN_SCHEMA or not chemin.is_file():
        raise ProfilInconnu(f"Aucun profil « {identifiant} » dans {DOSSIER_PERSONAS.name}/")
    return chemin


def charger_profil(identifiant: str) -> dict[str, Any]:
    """Profil validé : ``personas/<identifiant>.json``, sinon le profil créé sous cet identifiant (#87).

    Raises:
        ProfilInconnu: identifiant invalide, ou aucun profil ne le porte.
        PacteInvalide: le profil ne respecte pas le format commun.
        ErreurDonnees: profil créé illisible (source ou bucket inaccessible).
    """
    try:
        return charger_pacte(chemin_profil(identifiant))
    except ProfilInconnu:
        if not isinstance(identifiant, str) or not FORMAT_IDENTIFIANT.fullmatch(identifiant):
            raise
    profil = lire_profil_cree(identifiant)
    if profil is None:
        raise ProfilInconnu(f"Aucun profil « {identifiant} » dans {DOSSIER_PERSONAS.name}/ "
                            "ni parmi les profils créés")
    erreurs = erreurs_profil(profil, nom_fichier=identifiant)
    if erreurs:
        raise PacteInvalide(Path(cle_profil(identifiant)), erreurs)
    return profil


def structurer_decision(
    demande: str,
    profil: dict[str, Any],
    univers: list[dict[str, str]],
    poche: str | None = None,
) -> ResultatAgentProfil:
    """Transforme une demande en langage naturel en décision du contrat.

    Appelée par ``lancer_agent_profil`` une fois le profil validé.

    Args:
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        profil: profil déjà validé par ``charger_pacte`` ; seuls « portefeuille »,
            « capital_fictif_cad » et, s'il y en a, « poches » sont lus.
        univers: titres connus du système (``pipeline.univers.charger_univers``).
        poche: profil à poches (#115) : poche imposée par l'appelant, ou None.
    """
    with au_nom_de("agent_profil"):
        extraction = appeler_llm(
            construire_systeme(univers),
            construire_message(demande, profil, univers),
            schema_extraction(univers, profil),
        )
    trace = [{"etape": "agent_profil", "outil": "bedrock", "entree": demande, "sortie": extraction}]
    profil_juge, controles_poche, hypotheses_poche = profil, [], []
    if a_des_poches(profil):
        id_poche, controles_poche, hypotheses_poche, etape = choisir_poche(profil, extraction.get("poche"), poche)
        profil_juge = profil_de_la_poche(profil, id_poche)
        trace.append(etape)
    decision, controles, hypotheses = interpreter_extraction(extraction, profil_juge, univers)
    if decision is not None and "poche" in profil_juge:
        decision["poche"] = profil_juge["poche"]["id"]
        decision["libelle"] += f" (poche « {profil_juge['poche']['objectif']} »)"
    controles = [*controles_poche, *controles]
    trace.append({
        "etape": "agent_profil",
        "outil": "valider_decision",
        "entree": extraction,
        "sortie": decision if decision is not None else [c["message"] for c in controles],
    })
    return ResultatAgentProfil(decision, controles, [*hypotheses_poche, *hypotheses], trace, profil=profil_juge)


def choisir_poche(
    profil: dict[str, Any],
    deduite: str | None,
    imposee: str | None,
) -> tuple[str, list[dict[str, Any]], list[str], dict[str, Any]]:
    """Poche où la décision est jugée (#115) : imposée, sinon déduite par le modèle, sinon la plus prudente.

    Le modèle ne fait que lire la demande ; Python choisit. Une poche déduite qui
    contredit la poche imposée, ou une poche non précisée, donne un contrôle
    « a_verifier » (``interpretation_demande``) : rien n'est deviné en silence.

    Returns:
        (id de la poche, contrôles « a_verifier », hypothèses, étape de trace « choisir_poche »)
    """
    poches = {poche["id"]: poche for poche in profil["poches"]}
    controles: list[dict[str, Any]] = []
    hypotheses: list[str] = []
    deduite = deduite if deduite in poches else None

    def nom(id_poche: str) -> str:
        return f"« {poches[id_poche]['objectif']} »"

    if imposee is not None:
        choisie, motif = imposee, "poche choisie par l'utilisateur"
        if deduite is not None and deduite != imposee:
            controles.append({"statut": "a_verifier", "regle": REGLE_CONTROLE, "message": (
                f"La demande semble viser la poche {nom(deduite)} (interprétation du modèle), mais la poche "
                f"{nom(imposee)} a été choisie : la décision est jugée dans la poche choisie.")})
    elif deduite is not None:
        choisie, motif = deduite, "poche déduite de la demande par le modèle"
        hypotheses.append(f"Poche {nom(deduite)} déduite de la demande (interprétation du modèle)")
    else:
        choisie = poche_la_plus_prudente(profil)["id"]
        motif = "poche non précisée : la plus prudente (horizon le plus court)"
        controles.append({"statut": "a_verifier", "regle": REGLE_CONTROLE, "message": (
            f"Poche non précisée : la décision est jugée dans la poche {nom(choisie)} "
            f"(horizon de {formater_horizon(poches[choisie]['horizon_ans'])}), la plus courte donc la plus "
            "prudente. Précisez la poche si ce n'est pas elle.")})
    hypotheses.append(
        f"Décision jugée dans la poche {nom(choisie)} ({formater_part(poches[choisie]['part'])} du portefeuille) : "
        "la taille est une part de cette poche ; simulation, taille maximale et règles portent sur la poche, "
        "pas sur le portefeuille global")
    etape = {"etape": "agent_profil", "outil": "choisir_poche",
             "entree": {"poche_imposee": imposee, "poche_deduite": deduite},
             "sortie": f"{choisie} ({motif})"}
    return choisie, controles, hypotheses, etape


# --- Ce que l'on demande au LLM ---------------------------------------------

CONSIGNES = """Tu es l'Agent Profil d'un outil éducatif de simulation d'investissement.
Ton seul rôle : lire la demande de l'utilisateur et la convertir en champs structurés.
Tu ne donnes aucun avis, tu ne calcules rien et tu n'inventes rien.

Règles :
- type_decision : « position » s'il s'agit d'ajouter ou d'augmenter un seul titre ;
  « reallocation » s'il s'agit de déplacer une part du portefeuille vers plusieurs titres
  (un panier) ; « autre » sinon.
- actif_mentionne : le titre (position) ou le panier (réallocation) tel que l'utilisateur
  l'a écrit.
- ticker : position seulement, et uniquement un ticker de l'univers d'actifs ci-dessous.
  Si le titre demandé n'y est pas, ou si tu ne peux pas l'identifier avec certitude, ou
  s'il s'agit d'une réallocation, mets null.
- taille : la part du portefeuille visée (position) ou réallouée (réallocation), en
  décimale (30 % → 0.30 ; un tiers → 0.3333 ; la moitié → 0.5 ; tout → 1.0). Si
  l'utilisateur donne un montant en argent plutôt qu'une part, mets taille à null et
  remplis montant.
- montant : le montant en argent s'il est donné (50 000 $ → 50000), sinon null.
- devise_montant : « CAD » ou « USD » si l'utilisateur le précise, sinon « non_precisee ».
- panier : réallocation seulement. Les titres du panier et leur poids dans le panier, en
  décimales (30 % → 0.30), uniquement s'ils sont donnés explicitement. Ne complète jamais
  un panier vague (« un panier tech ») : laisse la liste vide et signale-le dans
  ambiguites. Liste vide pour une position.
- actifs_hors_univers : les titres mentionnés qui ne sont pas dans l'univers d'actifs,
  tels qu'écrits ; liste vide sinon.
- financement_depuis : position seulement. Le titre du portefeuille que l'utilisateur dit
  vendre ou réduire pour financer la décision ; sinon null (financement proportionnel
  par défaut). Toujours null pour une réallocation, prise au prorata de toutes les lignes.
- ambiguites : une phrase courte par point incertain ou manquant ; liste vide si tout est
  clair. En cas de doute, ne devine pas : signale-le ici. Ne signale pas l'absence de
  financement : le financement proportionnel s'applique par défaut."""


def construire_systeme(univers: list[dict[str, str]]) -> str:
    """Consignes de l'agent, suivies de l'univers d'actifs."""
    lignes = "\n".join(
        f"- {actif['ticker']} : {actif['name']} ({actif['asset_class']}, {actif['sector']})"
        for actif in univers
    )
    return f"{CONSIGNES}\n\nUnivers d'actifs :\n{lignes}"


CONSIGNES_POCHES = """Ce portefeuille est divisé en poches, chacune avec son objectif et son horizon.
Une décision vise une seule poche ; sa taille est une part de cette poche.
- poche : l'id de la poche visée, seulement si la demande la nomme ou la désigne clairement
  (par son objectif, son horizon ou son usage) ; sinon null. Ne devine pas d'après les titres
  demandés, et ne signale pas une poche absente dans ambiguites : Python s'en charge."""


def construire_message(demande: str, profil: dict[str, Any], univers: list[dict[str, str]]) -> str:
    """Portefeuille actuel (titres seulement), ses poches s'il en a (#115), et demande de l'utilisateur."""
    noms = {actif["ticker"]: actif["name"] for actif in univers}
    lignes = "\n".join(
        f"- {ligne['ticker']} : {noms.get(ligne['ticker'], 'hors univers')}"
        for ligne in profil["portefeuille"]
    )
    message = f"Portefeuille actuel :\n{lignes}\n\n"
    if a_des_poches(profil):
        poches = "\n".join(
            f"- {poche['id']} : {poche['objectif']} (horizon : {formater_horizon(poche['horizon_ans'])} ; "
            f"titres : {', '.join(ligne['ticker'] for ligne in poche['portefeuille'])})"
            for poche in profil["poches"]
        )
        message += f"{CONSIGNES_POCHES}\n\nPoches :\n{poches}\n\n"
    return f"{message}Demande de l'utilisateur :\n{demande}"


def schema_extraction(univers: list[dict[str, str]], profil: dict[str, Any]) -> dict[str, Any]:
    """Schéma imposé à la réponse du LLM.

    Les listes de valeurs permises (« enum ») empêchent le modèle de répondre
    par un ticker hors de l'univers ou un financement hors du portefeuille.
    """
    tickers_univers = sorted(actif["ticker"] for actif in univers)
    tickers_portefeuille = sorted({ligne["ticker"] for ligne in profil["portefeuille"]})

    def ou_null(schema: dict[str, Any]) -> dict[str, Any]:
        return {"anyOf": [schema, {"type": "null"}]}

    proprietes = {
        "type_decision": {"type": "string", "enum": ["position", "reallocation", "autre"]},
        "actif_mentionne": {"type": "string"},
        "ticker": ou_null({"type": "string", "enum": tickers_univers}),
        "taille": ou_null({"type": "number"}),
        "montant": ou_null({"type": "number"}),
        "devise_montant": {"type": "string", "enum": ["CAD", "USD", "non_precisee"]},
        "panier": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ticker", "poids"],
                "properties": {
                    "ticker": {"type": "string", "enum": tickers_univers},
                    "poids": {"type": "number"},
                },
            },
        },
        "actifs_hors_univers": {"type": "array", "items": {"type": "string"}},
        "financement_depuis": (
            ou_null({"type": "string", "enum": tickers_portefeuille})
            if tickers_portefeuille
            else {"type": "null"}
        ),
        "ambiguites": {"type": "array", "items": {"type": "string"}},
    }
    if a_des_poches(profil):  # #115 : seulement pour un profil à poches (sans poches, schéma inchangé)
        proprietes["poche"] = ou_null({"type": "string", "enum": [poche["id"] for poche in profil["poches"]]})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(proprietes),
        "properties": proprietes,
    }


# --- Ce que Python vérifie et calcule ---------------------------------------


def interpreter_extraction(
    extraction: dict[str, Any],
    profil: dict[str, Any],
    univers: list[dict[str, str]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    """Vérifie l'extraction du LLM et construit la décision du contrat.

    Returns:
        (decision ou None, contrôles « a_verifier », hypothèses)
    """
    controles: list[dict[str, Any]] = []
    hypotheses: list[str] = []

    def a_verifier(message: str) -> None:
        controles.append({"statut": "a_verifier", "regle": REGLE_CONTROLE, "message": message})

    for ambiguite in extraction["ambiguites"]:
        a_verifier(f"Point à confirmer dans la demande (interprétation du modèle) : {ambiguite}")

    if extraction["type_decision"] == "position":
        decision = _decision_position(extraction, profil, univers, a_verifier, hypotheses)
    elif extraction["type_decision"] == "reallocation":
        decision = _decision_reallocation(extraction, profil, univers, a_verifier, hypotheses)
    else:
        a_verifier(
            "Décision non reconnue : précisez un titre et une taille, ou un panier de titres "
            "et la part du portefeuille à réallouer."
        )
        decision = None
    return decision, controles, hypotheses


def _decision_position(extraction, profil, univers, a_verifier, hypotheses) -> dict[str, Any] | None:
    """Décision « position » : un titre de l'univers, une taille et un financement."""
    ticker = extraction["ticker"]
    if ticker not in {actif["ticker"] for actif in univers}:
        a_verifier(
            f"Titre « {extraction['actif_mentionne']} » introuvable dans l'univers d'actifs : "
            "il n'est jamais remplacé par un titre approchant."
        )
        return None

    taille = _part_valide(extraction, profil, a_verifier, hypotheses, nom="Taille")
    if taille is None:
        return None

    financement = _financement(extraction["financement_depuis"], ticker, profil, a_verifier, hypotheses)
    libelle = f"{formater_part(taille)} en {ticker}"
    if financement.startswith("depuis_"):
        libelle += f", financé par {financement.removeprefix('depuis_')}"

    return {
        "type": "position",
        "ticker": ticker,
        "taille": taille,
        "financement": financement,
        "libelle": libelle,
    }


def _decision_reallocation(extraction, profil, univers, a_verifier, hypotheses) -> dict[str, Any] | None:
    """Décision « reallocation » : un panier explicite (titres et poids) et la part réallouée."""
    if extraction["actifs_hors_univers"]:
        a_verifier(
            "Titre(s) du panier introuvable(s) dans l'univers d'actifs : "
            f"{', '.join(extraction['actifs_hors_univers'])}. Ils ne sont jamais remplacés par un "
            "titre approchant."
        )
        return None
    if not extraction["panier"]:
        a_verifier(
            f"Composition du panier « {extraction['actif_mentionne']} » non précisée : indiquez "
            "les titres et leur poids (ex. : 50 % BTC-USD et 50 % ETH-USD)."
        )
        return None

    tickers = [ligne["ticker"] for ligne in extraction["panier"]]
    poids = [float(ligne["poids"]) for ligne in extraction["panier"]]
    inconnus = [t for t in tickers if t not in {actif["ticker"] for actif in univers}]
    if inconnus:
        a_verifier(f"Titre(s) du panier hors de l'univers d'actifs : {', '.join(inconnus)}.")
        return None
    if len(set(tickers)) != len(tickers):
        a_verifier("Un titre apparaît deux fois dans le panier : précisez son poids.")
        return None
    if any(p <= 0 for p in poids):
        a_verifier("Chaque titre du panier doit avoir un poids positif.")
        return None
    poids = _poids_normalises(poids, a_verifier, hypotheses)
    if poids is None:
        return None

    part = _part_valide(extraction, profil, a_verifier, hypotheses, nom="Part réallouée")
    if part is None:
        return None

    if extraction["financement_depuis"] is not None:
        a_verifier(
            f"Financement depuis {extraction['financement_depuis']} ignoré : une réallocation "
            "est prise au prorata de toutes les lignes du portefeuille."
        )
    hypotheses.append("Réallocation prise au prorata de toutes les lignes du portefeuille")

    panier = [{"ticker": t, "poids": p} for t, p in zip(tickers, poids)]
    return {
        "type": "reallocation",
        "panier": panier,
        "part_reallouee": part,
        "libelle": f"{formater_part(part)} réalloué vers {_decrire_panier(panier)}",
    }


def _poids_normalises(poids, a_verifier, hypotheses) -> list[float] | None:
    """Poids du panier ramenés à un total exact de 1 (le contrat l'exige).

    Seuls de petits écarts d'arrondi sont corrigés (ex. : trois tiers écrits
    0,3333). Au-delà, la répartition est ambiguë : l'utilisateur doit la préciser.
    """
    total = sum(poids)
    if abs(total - 1) > TOLERANCE_TOTAL_PANIER:
        a_verifier(
            f"Les poids du panier totalisent {formater_part(total)} au lieu de 100 % : "
            "précisez la répartition."
        )
        return None
    if total != 1:
        hypotheses.append(
            f"Poids du panier ajustés pour totaliser exactement 100 % (total écrit : "
            f"{total * 100:.2f} %)".replace(".", ",")
        )
    return [p / total for p in poids]


def _decrire_panier(panier) -> str:
    """« BTC-USD 30 %, ETH-USD 20 % et NVDA 50 % »."""
    lignes = [f"{ligne['ticker']} {formater_part(ligne['poids'])}" for ligne in panier]
    return lignes[0] if len(lignes) == 1 else f"{', '.join(lignes[:-1])} et {lignes[-1]}"


def _part_valide(extraction, profil, a_verifier, hypotheses, nom) -> float | None:
    """Part demandée (taille ou part réallouée), comprise entre 0 et 100 % du portefeuille."""
    part = _taille_demandee(extraction, profil, a_verifier, hypotheses, nom)
    if part is None:
        return None
    if not 0 < part <= 1:
        a_verifier(
            f"{nom} de {formater_part(part)} impossible : elle doit être comprise "
            "entre 0 et 100 % du portefeuille."
        )
        return None
    return part


def _taille_demandee(extraction, profil, a_verifier, hypotheses, nom="Taille") -> float | None:
    """Part du portefeuille demandée : donnée directement, ou calculée depuis un montant."""
    taille, montant = extraction["taille"], extraction["montant"]

    if taille is not None and montant is not None:
        a_verifier("La demande donne à la fois une part et un montant : précisez lequel retenir.")
        return None
    if taille is not None:
        return float(taille)
    if montant is None:
        a_verifier(f"{nom} absente : précisez une part du portefeuille (ex. : 10 %) ou un montant.")
        return None

    devise = extraction["devise_montant"]
    if devise == "USD":
        a_verifier("Montant en USD : exprimez la taille en part du portefeuille ou en CAD.")
        return None
    capital = profil.get("capital_fictif_cad")
    if not capital:
        a_verifier("Capital du profil inconnu : impossible de convertir le montant en part.")
        return None

    taille = montant / capital
    hypotheses.append(
        f"Montant de {formater_montant(montant)} $ converti en part du capital fictif "
        f"({formater_montant(capital)} $ CAD), soit {formater_part(taille)}"
    )
    if devise == "non_precisee":
        hypotheses.append("Devise du montant non précisée : interprétée comme des dollars canadiens")
    return taille


def _financement(depuis, ticker, profil, a_verifier, hypotheses) -> str:
    """« proportionnel » par défaut, ou « depuis_<ticker> » si un titre du portefeuille est désigné."""
    if depuis is None:
        hypotheses.append(
            "Financement proportionnel par défaut : toutes les lignes du portefeuille "
            "sont réduites au prorata"
        )
        return "proportionnel"
    if depuis not in {ligne["ticker"] for ligne in profil["portefeuille"]} or depuis == ticker:
        a_verifier(
            f"Financement depuis {depuis} impossible (titre absent du portefeuille ou "
            "identique au titre acheté) : financement proportionnel retenu."
        )
        return "proportionnel"
    return f"depuis_{depuis}"


def formater_part(part: float) -> str:
    """0.30 → « 30 % » ; 0.0769 → « 7,7 % » (une décimale au plus, virgule française)."""
    texte = f"{part * 100:.1f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


def formater_montant(montant: float) -> str:
    """50000 → « 50 000 » (espace des milliers, sans décimales)."""
    return f"{montant:,.0f}".replace(",", " ")
