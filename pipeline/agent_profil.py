"""Agent Profil : transforme la demande de l'utilisateur en décision structurée.

Première phase du Tribunal (CLAUDE.md, section 4). Le LLM sert seulement à
**comprendre le texte** : il repère le titre, la taille et le financement.
Python vérifie ensuite chaque champ et fait les calculs (ex. : un montant en
dollars converti en part du portefeuille).

Si la demande est incomplète ou ambiguë, l'agent ne devine pas : il ajoute un
contrôle « a_verifier » (règle « interpretation_demande »). Si la décision ne
peut pas être construite (titre hors de l'univers, taille absente…), il ne
renvoie aucune décision : le procès ne peut pas commencer et l'interface doit
demander à l'utilisateur de préciser.

Le code ne connaît aucun persona : il lit seulement le portefeuille et le
capital du profil reçu.

V1 : décisions de type « position » (un seul titre). Les réallocations vers
un panier arrivent avec #16.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipeline.llm import appeler_llm

REGLE_CONTROLE = "interpretation_demande"


@dataclass
class ResultatAgentProfil:
    """Ce que l'Agent Profil transmet à l'orchestrateur."""

    decision: dict[str, Any] | None  # format « decision » du contrat ; None si impossible
    controles: list[dict[str, Any]] = field(default_factory=list)  # contrôles « a_verifier »
    hypotheses: list[str] = field(default_factory=list)  # à ajouter aux hypothèses du contrat
    trace: list[dict[str, Any]] = field(default_factory=list)  # étapes « agent_profil »


def structurer_decision(
    demande: str,
    profil: dict[str, Any],
    univers: list[dict[str, str]],
) -> ResultatAgentProfil:
    """Transforme une demande en langage naturel en décision du contrat.

    Args:
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        profil: profil chargé (fichier personas/<id>.json) ; seuls
            « portefeuille » et « capital_fictif_cad » sont lus.
        univers: titres connus du système (``pipeline.univers.charger_univers``).
    """
    extraction = appeler_llm(
        construire_systeme(univers),
        construire_message(demande, profil, univers),
        schema_extraction(univers, profil),
    )
    decision, controles, hypotheses = interpreter_extraction(extraction, profil, univers)
    trace = [
        {"etape": "agent_profil", "outil": "bedrock", "entree": demande, "sortie": extraction},
        {
            "etape": "agent_profil",
            "outil": "valider_decision",
            "entree": extraction,
            "sortie": decision if decision is not None else [c["message"] for c in controles],
        },
    ]
    return ResultatAgentProfil(decision, controles, hypotheses, trace)


# --- Ce que l'on demande au LLM ---------------------------------------------

CONSIGNES = """Tu es l'Agent Profil d'un outil éducatif de simulation d'investissement.
Ton seul rôle : lire la demande de l'utilisateur et la convertir en champs structurés.
Tu ne donnes aucun avis, tu ne calcules rien et tu n'inventes rien.

Règles :
- type_decision : « position » s'il s'agit d'ajouter ou d'augmenter un seul titre ;
  « reallocation » s'il s'agit de déplacer une part du portefeuille vers plusieurs titres
  (un panier) ; « autre » sinon.
- actif_mentionne : le titre tel que l'utilisateur l'a écrit.
- ticker : uniquement un ticker de l'univers d'actifs ci-dessous. Si le titre demandé n'y
  est pas, ou si tu ne peux pas l'identifier avec certitude, mets null.
- taille : la part du portefeuille visée, en décimale (30 % → 0.30 ; un tiers → 0.3333 ;
  la moitié → 0.5). Si l'utilisateur donne un montant en argent plutôt qu'une part,
  mets taille à null et remplis montant.
- montant : le montant en argent s'il est donné (50 000 $ → 50000), sinon null.
- devise_montant : « CAD » ou « USD » si l'utilisateur le précise, sinon « non_precisee ».
- financement_depuis : seulement si l'utilisateur dit quel titre de son portefeuille vendre
  ou réduire pour financer la décision ; sinon null (financement proportionnel par défaut).
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


def construire_message(demande: str, profil: dict[str, Any], univers: list[dict[str, str]]) -> str:
    """Portefeuille actuel (titres seulement) et demande de l'utilisateur."""
    noms = {actif["ticker"]: actif["name"] for actif in univers}
    lignes = "\n".join(
        f"- {ligne['ticker']} : {noms.get(ligne['ticker'], 'hors univers')}"
        for ligne in profil["portefeuille"]
    )
    return f"Portefeuille actuel :\n{lignes}\n\nDemande de l'utilisateur :\n{demande}"


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
        "financement_depuis": (
            ou_null({"type": "string", "enum": tickers_portefeuille})
            if tickers_portefeuille
            else {"type": "null"}
        ),
        "ambiguites": {"type": "array", "items": {"type": "string"}},
    }
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

    if extraction["type_decision"] != "position":
        a_verifier(
            "Seules les décisions portant sur un seul titre sont prises en charge pour "
            "l'instant : précisez un titre et une taille."
        )
        return None, controles, hypotheses

    ticker = extraction["ticker"]
    if ticker not in {actif["ticker"] for actif in univers}:
        a_verifier(
            f"Titre « {extraction['actif_mentionne']} » introuvable dans l'univers d'actifs : "
            "il n'est jamais remplacé par un titre approchant."
        )
        return None, controles, hypotheses

    taille = _taille_demandee(extraction, profil, a_verifier, hypotheses)
    if taille is None:
        return None, controles, hypotheses
    if not 0 < taille <= 1:
        a_verifier(
            f"Taille de {formater_part(taille)} impossible : elle doit être comprise "
            "entre 0 et 100 % du portefeuille."
        )
        return None, controles, hypotheses

    financement = _financement(extraction["financement_depuis"], ticker, profil, a_verifier, hypotheses)
    libelle = f"{formater_part(taille)} en {ticker}"
    if financement.startswith("depuis_"):
        libelle += f", financé par {financement.removeprefix('depuis_')}"

    decision = {
        "type": "position",
        "ticker": ticker,
        "taille": taille,
        "financement": financement,
        "libelle": libelle,
    }
    return decision, controles, hypotheses


def _taille_demandee(extraction, profil, a_verifier, hypotheses) -> float | None:
    """Part du portefeuille demandée : donnée directement, ou calculée depuis un montant."""
    taille, montant = extraction["taille"], extraction["montant"]

    if taille is not None and montant is not None:
        a_verifier("La demande donne à la fois une part et un montant : précisez lequel retenir.")
        return None
    if taille is not None:
        return float(taille)
    if montant is None:
        a_verifier("Taille absente : précisez une part du portefeuille (ex. : 10 %) ou un montant.")
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
