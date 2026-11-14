"""Outil 4 : taille_max_compatible (CLAUDE.md, section 4 bis).

La réponse utile n'est souvent pas « non », mais « pas à cette taille ».
L'outil cherche la plus grande taille de la décision qui respecte **toutes les
règles calculables** du Pacte (``pire_baisse_max`` et ``plafond``), avec le
même mode de financement.

Méthode, fixée par l'équipe : simuler la décision de 0 jusqu'à la taille
demandée, **par pas de 1 point**, sans dichotomie (rien ne garantit que la
pire baisse évolue toujours dans le même sens avec la taille). À chaque taille,
les règles sont jugées par les **contrôles du Greffier** (``verifier_pacte``) :
l'outil ne peut donc pas déclarer compatible une taille que le Greffier
jugerait en violation.

Pour une réallocation, la « taille » est la part réallouée. Si même 0 % viole
le Pacte (portefeuille de départ déjà hors Pacte), l'outil le signale au lieu
de renvoyer une taille.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.categories import TitreHorsUnivers, categories_du_titre
from pipeline.greffier import verifier_pacte
from pipeline.llm import decrire_outil
from pipeline.simulation import poids_apres_decision, simuler_portefeuille, source_des_prix

NOM_OUTIL = "taille_max_compatible"
PAS_DE_RECHERCHE = 0.01
TYPES_CALCULABLES = ("pire_baisse_max", "plafond")

# Les valeurs des pièces sont brutes : au moins 4 décimales (CLAUDE.md, section 5).
DECIMALES_VALEURS = 6


@dataclass(frozen=True)
class EtapeRecherche:
    """Une taille testée et ce que le Greffier en dit."""

    taille: float
    pire_baisse: float  # pire baisse du portefeuille après la décision, à cette taille
    parts: dict[str, float]  # part des catégories de chaque règle « plafond » (id → part)
    violations: list[str]  # id des règles calculables qui ne sont pas « conforme »

    @property
    def compatible(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class ResultatRecherche:
    taille_demandee: float
    taille_max: float | None  # None : même 0 % viole le Pacte
    etapes: list[EtapeRecherche]
    regles: list[dict[str, Any]]  # règles calculables vérifiées

    def etape(self, taille: float | None) -> EtapeRecherche | None:
        return next((e for e in self.etapes if taille is not None and e.taille == taille), None)

    def etape_suivante(self) -> EtapeRecherche | None:
        """Première taille testée au-delà de la taille maximale (elle viole le Pacte)."""
        if self.taille_max is None:
            return None
        return next((e for e in self.etapes if e.taille > self.taille_max), None)


# --- Recherche ------------------------------------------------------------------


def tailles_a_tester(taille_demandee: float) -> list[float]:
    """0, 1 %, 2 %… jusqu'à la taille demandée, incluse même hors de la grille (ex. : 7,69 %)."""
    nombre_de_pas = int(taille_demandee / PAS_DE_RECHERCHE + 1e-9)
    tailles = [round(i * PAS_DE_RECHERCHE, 2) for i in range(nombre_de_pas + 1)]
    if taille_demandee - tailles[-1] > 1e-9:
        tailles.append(taille_demandee)
    return tailles


def rechercher_taille_max(
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any],
    regles: list[dict[str, Any]],
) -> ResultatRecherche:
    """Simule chaque taille et garde la plus grande qui respecte les règles calculables.

    Args:
        portefeuille: lignes ``{"ticker", "poids"}`` du profil.
        decision: décision du contrat (« position » ; « reallocation » dès que
            ``simuler_portefeuille`` la prendra en charge, #16).
        regles: règles du Pacte ; seules ``pire_baisse_max`` et ``plafond`` comptent.

    Raises:
        ErreurSimulation, ErreurDonnees: décision impossible à simuler (message lisible).
    """
    calculables = [regle for regle in regles if regle["type"] in TYPES_CALCULABLES]
    taille_demandee = _taille(decision)
    etapes = [_evaluer(portefeuille, _a_la_taille(decision, taille), taille, calculables)
              for taille in tailles_a_tester(taille_demandee)]
    compatibles = [etape.taille for etape in etapes if etape.compatible]
    return ResultatRecherche(
        taille_demandee=taille_demandee,
        taille_max=max(compatibles) if compatibles else None,
        etapes=etapes,
        regles=calculables,
    )


def _evaluer(portefeuille, decision, taille, regles) -> EtapeRecherche:
    """Simule une taille et la fait juger par les contrôles du Greffier."""
    pire_baisse = simuler_portefeuille(portefeuille, decision)["apres"]["pire_baisse"]
    poids = poids_apres_decision(portefeuille, decision)
    simulation = {"id": "recherche", "valeurs": {"pire_baisse": pire_baisse}}
    controles = verifier_pacte(regles, poids, simulation, id_piece_pacte="pacte")
    return EtapeRecherche(
        taille=taille,
        pire_baisse=pire_baisse,
        parts={regle["id"]: _part_des_categories(poids, regle["categories"])
               for regle in regles if regle["type"] == "plafond"},
        violations=[controle["regle"] for controle in controles if controle["statut"] != "conforme"],
    )


def _part_des_categories(poids: dict[str, float], categories: list[str]) -> float:
    part = 0.0
    for ticker, poids_titre in poids.items():
        try:
            if categories_du_titre(ticker) & set(categories):
                part += poids_titre
        except TitreHorsUnivers:
            pass  # le Greffier rend alors « a_verifier » : la taille n'est pas compatible
    return part


def _taille(decision: dict[str, Any]) -> float:
    return decision["part_reallouee"] if decision.get("type") == "reallocation" else decision["taille"]


def _a_la_taille(decision: dict[str, Any], taille: float) -> dict[str, Any]:
    cle = "part_reallouee" if decision.get("type") == "reallocation" else "taille"
    return {**decision, cle: taille}


# --- La pièce -----------------------------------------------------------------


def piece_taille_max(
    id_piece: str,
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any],
    regles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pièce « Taille maximale compatible avec le Pacte », au format du contrat (étiquette « fictif »)."""
    resultat = rechercher_taille_max(portefeuille, decision, regles)
    a_taille_max = resultat.etape(resultat.taille_max)
    suivante = resultat.etape_suivante()
    limitantes = suivante.violations if suivante else (
        resultat.etapes[0].violations if resultat.taille_max is None else [])

    valeurs: dict[str, Any] = {
        "taille_max_compatible": resultat.taille_max,
        "taille_demandee": resultat.taille_demandee,
        "pas_de_recherche": PAS_DE_RECHERCHE,
        "regles_verifiees": [regle["id"] for regle in resultat.regles],
        "regle_limitante": limitantes[0] if limitantes else None,
        "pire_baisse_a_taille_max": a_taille_max.pire_baisse if a_taille_max else None,
        "pire_baisse_a_taille_suivante": suivante.pire_baisse if suivante else None,
    }
    for regle in resultat.regles:
        if regle["type"] == "plafond":
            nom = "part_" + "_".join(regle["categories"])
            valeurs[f"{nom}_a_taille_max"] = a_taille_max.parts[regle["id"]] if a_taille_max else None
            valeurs[f"{nom}_a_taille_suivante"] = suivante.parts[regle["id"]] if suivante else None
    valeurs = {cle: _brute(valeur) for cle, valeur in valeurs.items()}

    reallocation = decision.get("type") == "reallocation"
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": ("Part maximale réallouable compatible avec le Pacte" if reallocation
                  else "Taille maximale compatible avec le Pacte"),
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": _valeur_affichee(resultat, limitantes),
        "source": source_des_prix(),
        "traitement": (
            f"Simulation de la décision de 0 à {_part(resultat.taille_demandee)} par pas de 1 point, "
            "même financement, sur toute la période ; à chaque taille, contrôles du Greffier "
            f"(verifier_pacte) sur les règles calculables : {', '.join(valeurs['regles_verifiees']) or 'aucune'}"
        ),
        "limites": (
            "Une seule période passée ; seules les règles calculables (pire baisse, plafonds) sont "
            "prises en compte, pas les règles qualitatives ni documentaires ; le passé ne prédit pas l'avenir"
        ),
    }


def decrire_taille_max(tickers_univers: list[str], portefeuille: list[dict[str, Any]]) -> dict[str, Any]:
    """Description de l'outil pour l'orchestrateur Bedrock, propre au portefeuille du profil."""
    tickers_portefeuille = sorted({ligne["ticker"] for ligne in portefeuille})
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ticker", "taille", "financement"],
        "properties": {
            "ticker": {"type": "string", "enum": sorted(tickers_univers), "description": "Titre de la décision"},
            "taille": {
                "type": "number",
                "description": "Taille demandée par la décision, en décimale (0.30 = 30 %) : "
                "la recherche va de 0 jusqu'à elle",
            },
            "financement": {
                "type": "string",
                "enum": ["proportionnel"] + [f"depuis_{t}" for t in tickers_portefeuille],
                "description": "Même financement que la décision",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        "Plus grande taille de la position, de 0 jusqu'à la taille demandée par pas de 1 point, "
        "qui respecte toutes les règles calculables du Pacte (pire baisse, plafonds), avec le même "
        "financement. Utile quand la décision semble dépasser un seuil du Pacte : montre si une "
        "version plus modeste serait compatible, ou si même 0 % viole déjà le Pacte.",
        schema,
    )


def decrire_taille_max_reallocation() -> dict[str, Any]:
    """Description de l'outil pour une décision de **réallocation** (#16) : la taille est la part réallouée."""
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["part_reallouee"],
        "properties": {
            "part_reallouee": {
                "type": "number",
                "description": "Part réallouée demandée par la décision, en décimale (1.0 = tout) : "
                "la recherche va de 0 jusqu'à elle",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        "Plus grande part du portefeuille réallouable vers le panier de la décision, de 0 jusqu'à "
        "la part demandée par pas de 1 point, qui respecte toutes les règles calculables du Pacte "
        "(pire baisse, plafonds). Utile quand la réallocation semble dépasser un seuil ou un "
        "plafond du Pacte : montre si une réallocation plus modeste serait compatible.",
        schema,
    )


# --- Mise en forme ------------------------------------------------------------


def _brute(valeur: Any) -> Any:
    return round(valeur, DECIMALES_VALEURS) if isinstance(valeur, float) else valeur


def _part(part: float) -> str:
    """0.09 → « 9 % » ; 0.0769 → « 7,7 % »."""
    texte = f"{part * 100:.1f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


def _valeur_affichee(resultat: ResultatRecherche, limitantes: list[str]) -> str:
    if resultat.taille_max is None:
        return f"Aucune taille compatible : le portefeuille actuel enfreint déjà {', '.join(limitantes)}"
    if resultat.taille_max == resultat.taille_demandee:
        return f"{_part(resultat.taille_max)} : la taille demandée respecte les règles calculables"
    return f"{_part(resultat.taille_max)} au maximum"
