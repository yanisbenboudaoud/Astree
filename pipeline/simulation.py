"""Outil 2 : simuler_portefeuille — le portefeuille du profil avant et après la décision.

C'est la pièce principale du procès (REFERENCE_DU_PROJET.md, sections 4 bis et 6 bis) : que
serait devenu le portefeuille sur la période d'analyse, avec et sans la
décision ? Elle remplit ``comparaison.actuel`` et ``comparaison.apres`` du
contrat, et c'est la seule pièce obligatoire de l'orchestrateur.
``taille_max_compatible`` (#21) l'appelle en boucle : les rendements quotidiens
sont donc chargés une seule fois par ensemble de titres.

Méthode (REFERENCE_DU_PROJET.md, section 6 bis) :

- **Prix** : ``charger_donnees`` (``adj_close`` en CAD, séances américaines).
- **Rééquilibrage quotidien** aux poids cibles : le rendement du portefeuille un
  jour donné est la moyenne pondérée des rendements des titres ce jour-là.
- **Financement** ``proportionnel`` (toutes les lignes réduites au prorata) ou
  ``depuis_<ticker>`` (une seule ligne réduite).
- **Indicateurs** : les fonctions de calcul de ``pipeline.indicateurs`` (#6),
  appliquées à la série de valeurs du portefeuille.
- **Pouvoir d'achat** (#111) : inflation, rendements réels, taux et ratio de Sharpe,
  tirés de ``pipeline.macro`` (Banque du Canada). Sans données macro, la pièce reste
  celle des prix seuls : la pièce obligatoire du procès n'en dépend pas.
- **Exposition en devise** (#112) : part du portefeuille dans chaque devise de cotation
  (``part_usd``, ``part_cad``), avant et après la décision, dans la pièce de la période
  complète : le risque de change d'un investisseur qui vit en CAD.
- **Frais des FNB** (#114) : coût annuel des frais de gestion avant et après, tiré de
  ``pipeline.frais``. Déjà prélevés dans les cours, ils sont affichés, jamais déduits.

Le code ne connaît aucun persona : il lit seulement le portefeuille reçu.
V1 : décisions de type « position ». Les réallocations vers un panier arrivent
avec #16.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from pipeline import frais, macro
from pipeline.donnees import ErreurDonnees, charger_donnees, charger_univers, date_extraction
from pipeline.indicateurs import (
    DECIMALES_VALEURS,
    calculer_pire_baisse,
    calculer_rendement_2022,
    calculer_rendement_annualise,
    calculer_volatilite_annuelle,
)
from pipeline.llm import decrire_outil

NOM_OUTIL = "simuler_portefeuille"

# Écart toléré sur la somme des poids d'un portefeuille (arrondis des fichiers JSON).
TOLERANCE_POIDS = 1e-6

LIMITES_PERIODE_COMPLETE = "Une seule période de {annees} ans ; biais du survivant ; le passé ne prédit pas l'avenir"
LIMITES_REJEU = "Une seule année de crise ; la suivante peut être différente"
# Ajoutée aux limites quand la pièce contient les données macro (#111). Sans chiffre : les
# agents ne reprennent aucun nombre des limites (REFERENCE_DU_PROJET.md, section 4 ter).
LIMITES_MACRO = "inflation moyenne du Canada, pas celle de l'investisseur ; impôts non comptés"
# Exposition en devise de la pièce de la période complète (#112), sans chiffre non plus.
TRAITEMENT_DEVISES = "exposition en devise : part du portefeuille par devise de cotation (assets_universe.csv)"
LIMITES_DEVISES = "exposition selon la devise de cotation, pas selon celle des titres détenus par un fonds"


class ErreurSimulation(ValueError):
    """Décision ou portefeuille impossible à simuler : l'outil le signale au lieu de deviner.

    Les données absentes (titre hors de l'univers, titre sans prix au début de
    la période) lèvent ``pipeline.donnees.ErreurDonnees``.
    """


# --- Poids après la décision --------------------------------------------------


def poids_apres_decision(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, float]:
    """Poids cibles du portefeuille une fois la décision appliquée.

    Args:
        portefeuille: lignes ``{"ticker", "poids"}`` du profil (poids totalisant 1).
        decision: décision du contrat (section 5), de l'un des deux types :
            - « position » : ``ticker``, ``taille`` (part du portefeuille, entre
              0 et 1) et ``financement`` (``proportionnel`` ou ``depuis_<ticker>``) ;
            - « reallocation » : ``panier`` (lignes ``{"ticker", "poids"}``
              totalisant 1) et ``part_reallouee`` (entre 0 et 1), prise au
              prorata de toutes les lignes du portefeuille (#16).

    Returns:
        Un poids par titre, totalisant 1. Une ligne vidée (financement
        ``depuis_<ticker>``, ou réallocation de 100 %) disparaît.

    Raises:
        ErreurSimulation: portefeuille ou panier mal formé, type de décision
            inconnu, taille hors de [0, 1], financement inconnu ou impossible.
    """
    poids = _poids_actuels(portefeuille)

    if decision.get("type") == "reallocation":
        return _poids_apres_reallocation(poids, decision)
    if decision.get("type") != "position":
        raise ErreurSimulation(
            f"Type de décision « {decision.get('type')} » inconnu : « position » ou « reallocation » attendu"
        )
    ticker = decision["ticker"]
    taille = decision["taille"]
    if isinstance(taille, bool) or not isinstance(taille, (int, float)) or not 0 <= taille <= 1:
        raise ErreurSimulation(f"Taille « {taille} » impossible : elle doit être comprise entre 0 et 1")
    financement = decision["financement"]

    if financement == "proportionnel":
        apres = {t: p * (1 - taille) for t, p in poids.items()}
    elif financement.startswith("depuis_"):
        source = financement.removeprefix("depuis_")
        if source == ticker:
            raise ErreurSimulation(f"Financement depuis {source} impossible : c'est le titre acheté")
        if source not in poids:
            raise ErreurSimulation(f"Financement depuis {source} impossible : titre absent du portefeuille")
        if poids[source] < taille - TOLERANCE_POIDS:
            raise ErreurSimulation(
                f"Financement depuis {source} impossible : la ligne pèse moins que la taille demandée"
            )
        apres = dict(poids)
        apres[source] = max(poids[source] - taille, 0.0)
        if apres[source] <= TOLERANCE_POIDS:
            del apres[source]
    else:
        raise ErreurSimulation(
            f"Financement « {financement} » inconnu : « proportionnel » ou « depuis_<ticker> » attendu"
        )

    apres[ticker] = apres.get(ticker, 0.0) + taille
    return apres


def _poids_apres_reallocation(poids: dict[str, float], decision: dict[str, Any]) -> dict[str, float]:
    """Retire la part réallouée de chaque ligne au prorata, puis la répartit selon le panier."""
    part = decision["part_reallouee"]
    if isinstance(part, bool) or not isinstance(part, (int, float)) or not 0 <= part <= 1:
        raise ErreurSimulation(f"Part réallouée « {part} » impossible : elle doit être comprise entre 0 et 1")
    panier = decision["panier"]
    if not panier:
        raise ErreurSimulation("Panier vide : rien à réallouer")
    tickers = [ligne["ticker"] for ligne in panier]
    if len(set(tickers)) != len(tickers):
        raise ErreurSimulation("Un titre apparaît deux fois dans le panier")
    if any(isinstance(ligne["poids"], bool) or not ligne["poids"] > 0 for ligne in panier):
        raise ErreurSimulation("Chaque titre du panier doit avoir un poids positif")
    total = sum(ligne["poids"] for ligne in panier)
    if abs(total - 1) > TOLERANCE_POIDS:
        raise ErreurSimulation(f"Les poids du panier totalisent {total} au lieu de 1")

    apres = {t: p * (1 - part) for t, p in poids.items()}
    for ligne in panier:
        apres[ligne["ticker"]] = apres.get(ligne["ticker"], 0.0) + part * ligne["poids"]
    return {t: p for t, p in apres.items() if p > TOLERANCE_POIDS}


def _poids_actuels(portefeuille: list[dict[str, Any]]) -> dict[str, float]:
    """Poids du portefeuille de départ, vérifiés (un titre par ligne, total de 1)."""
    if not portefeuille:
        raise ErreurSimulation("Portefeuille vide : rien à simuler")
    poids: dict[str, float] = {}
    for ligne in portefeuille:
        ticker, part = ligne["ticker"], ligne["poids"]
        if ticker in poids:
            raise ErreurSimulation(f"Le titre {ticker} apparaît deux fois dans le portefeuille")
        if not 0 < part <= 1:
            raise ErreurSimulation(f"Poids de {ticker} impossible : {part}")
        poids[ticker] = float(part)
    if abs(sum(poids.values()) - 1) > TOLERANCE_POIDS:
        raise ErreurSimulation(f"Les poids du portefeuille totalisent {sum(poids.values())}, pas 1")
    return poids


# --- Simulation ---------------------------------------------------------------


def simuler_portefeuille(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Indicateurs du portefeuille avant et après la décision, valeurs brutes.

    Returns:
        ``{"actuel": {...}, "apres": {...}}``, chacun avec ``rendement_annuel``,
        ``volatilite_annuelle``, ``pire_baisse`` et ``rendement_2022`` : le format
        de ``comparaison`` du contrat. Les valeurs ne sont pas arrondies (les
        pièces, elles, le sont à ``DECIMALES_VALEURS``).

    Raises:
        ErreurSimulation: voir ``poids_apres_decision``.
        ErreurDonnees: titre hors de l'univers, ou sans prix au début de la période.
    """
    actuel, apres = _deux_simulations(portefeuille, decision)
    return {"actuel": actuel.indicateurs(), "apres": apres.indicateurs()}


def piece_simulation(
    id_piece: str,
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any],
    periode: str = "complete",
    capital: float | None = None,
) -> dict[str, Any]:
    """Pièce du contrat produite par l'outil, étiquette « fictif ».

    Args:
        id_piece: identifiant attribué par l'orchestrateur (ex. : « P1 »).
        portefeuille, decision: voir ``poids_apres_decision``.
        periode: ``complete`` (toute la période d'analyse : pire baisse,
            rendement annualisé et volatilité, avant et après) ou ``2022``
            (rejeu de l'année de crise : rendement 2022 avant et après).
        capital: capital fictif du profil, en CAD. S'il est connu, la pièce ajoute
            les comparaisons concrètes (``comparaisons_periode_complete`` et
            ``comparaisons_2022``, frais en dollars) : les agents ne calculent rien, ils
            citent ces valeurs.

    Returns:
        La pièce au format du contrat : ``valeurs`` brutes (arrondies à
        ``DECIMALES_VALEURS``, comme les pièces de ``indicateurs_actif``),
        ``valeur_affichee`` arrondie par Python.
    """
    actuel, apres = _deux_simulations(portefeuille, decision)
    if periode == "complete":
        piece = _piece_periode_complete(id_piece, actuel, apres, decision)
        if capital:
            piece["valeurs"].update(comparaisons_periode_complete(piece["valeurs"], capital))
        piece = _avec_contexte_macro(piece, lambda: contexte_macro_periode_complete(piece["valeurs"], apres.valeurs))
        return _avec_frais(piece, _poids_actuels(portefeuille), poids_apres_decision(portefeuille, decision), capital)
    if periode == "2022":
        piece = _piece_rejeu_2022(id_piece, actuel, apres, decision)
        if capital:
            piece["valeurs"].update(comparaisons_2022(piece["valeurs"], capital))
        return _avec_contexte_macro(piece, lambda: contexte_macro_2022(piece["valeurs"]))
    raise ErreurSimulation(f"Période « {periode} » inconnue : « complete » ou « 2022 » attendue")


def contexte_macro_periode_complete(valeurs: dict[str, Any], serie_apres: pd.Series) -> tuple[dict[str, float], str]:
    """Inflation, rendements réels et ratio de Sharpe de la période complète (#111).

    Calculés ici pour que l'agent n'en dérive aucun (section 4 ter, règle 6). Le ratio de
    Sharpe reprend les valeurs affichées dans la pièce, pour qu'un lecteur puisse le refaire :
    (rendement annualisé − taux sans risque moyen) ÷ volatilité annuelle.

    Returns:
        Les valeurs à ajouter à la pièce, et la phrase de méthode à ajouter au traitement.
    """
    debut, fin = serie_apres.index[0], serie_apres.index[-1]
    mesure = macro.inflation(debut, fin)
    sans_risque = macro.taux_moyen(macro.SERIE_TAUX_DIRECTEUR, debut, fin)
    contexte = {
        "inflation_annuelle": mesure.annuelle,
        "rendement_reel_annuel": macro.rendement_reel(valeurs["rendement_annuel"], mesure.annuelle),
        "rendement_reel_annuel_actuel": macro.rendement_reel(valeurs["rendement_annuel_actuel"], mesure.annuelle),
        "taux_sans_risque_moyen": sans_risque,
    }
    for nom, rendement, volatilite in (
        ("ratio_sharpe", "rendement_annuel", "volatilite_annuelle"),
        ("ratio_sharpe_actuel", "rendement_annuel_actuel", "volatilite_annuelle_actuelle"),
    ):
        if valeurs[volatilite] > 0:
            contexte[nom] = (valeurs[rendement] - sans_risque) / valeurs[volatilite]
    traitement = (
        f"inflation : IPC du Canada de {mesure.mois_debut} à {mesure.mois_fin} (dernier mois publié, "
        "chaque mois étant supposé publié à la fin du mois suivant) ; "
        "rendement réel = (1 + rendement) ÷ (1 + inflation) − 1 ; ratio de Sharpe = (rendement annualisé "
        "− taux directeur moyen) ÷ volatilité annuelle"
    )
    return _arrondir(contexte), traitement


def contexte_macro_2022(valeurs: dict[str, Any]) -> tuple[dict[str, float], str]:
    """L'année 2022 en pouvoir d'achat, et les taux qui l'expliquent (#111).

    Inflation de l'année (IPC de décembre à décembre), rendements réels avant et après la
    décision, taux directeur et obligation du Canada à 10 ans au début et à la fin de
    l'année, et taux directeur moyen (ce qu'a rapporté un placement liquide en CAD).
    """
    debut, fin = (pd.Timestamp(date) for date in valeurs["periode"])
    mesure = macro.inflation(debut, fin)
    contexte = {
        "inflation_2022": mesure.cumulee,
        "rendement_reel_2022_actuel": macro.rendement_reel(valeurs["rendement_2022_actuel"], mesure.cumulee),
        "rendement_reel_2022_apres": macro.rendement_reel(valeurs["rendement_2022_apres"], mesure.cumulee),
        "taux_directeur_debut_2022": macro.taux_au(macro.SERIE_TAUX_DIRECTEUR, debut),
        "taux_directeur_fin_2022": macro.taux_au(macro.SERIE_TAUX_DIRECTEUR, fin),
        "taux_directeur_moyen_2022": macro.taux_moyen(macro.SERIE_TAUX_DIRECTEUR, debut, fin),
        "obligation_10_ans_debut_2022": macro.taux_au(macro.SERIE_OBLIGATION_10_ANS, debut),
        "obligation_10_ans_fin_2022": macro.taux_au(macro.SERIE_OBLIGATION_10_ANS, fin),
    }
    traitement = (
        f"inflation : IPC du Canada de {mesure.mois_debut} à {mesure.mois_fin} ; rendement réel = "
        "(1 + rendement) ÷ (1 + inflation) − 1 ; taux directeur et obligation à 10 ans au début et à la fin "
        "de l'année"
    )
    return _arrondir(contexte), traitement


def _avec_contexte_macro(piece: dict[str, Any], calculer) -> dict[str, Any]:
    """Ajoute les données macro à la pièce ; sans elles, la pièce reste celle des prix seuls.

    Une donnée macro manquante (fichier absent du bucket, mois non publié) ne doit pas
    faire échouer la pièce obligatoire du procès : elle est signalée dans CloudWatch.
    """
    try:
        contexte, traitement = calculer()
        source = macro.source_macro()
    except ErreurDonnees as erreur:
        print(f"Données macro non ajoutées à {piece['id']} : {erreur}")
        return piece
    piece["valeurs"].update(contexte)
    piece["source"] = f"{piece['source']} ; {source}"
    piece["traitement"] = f"{piece['traitement']} ; {traitement}"
    piece["limites"] = f"{piece['limites']} ; {LIMITES_MACRO}"
    return piece


def _avec_frais(piece: dict[str, Any], poids_actuels: dict[str, float], poids_apres: dict[str, float],
                capital: float | None) -> dict[str, Any]:
    """Ajoute le coût annuel des frais des FNB (#114) ; sans relevé des frais, la pièce reste la même.

    Comme les données macro, une donnée de contexte manquante ne doit pas faire échouer la
    pièce obligatoire du procès : elle est signalée dans CloudWatch.
    """
    try:
        valeurs, traitement = frais.contexte_frais(poids_actuels, poids_apres, capital)
        source = frais.source_frais()
    except ErreurDonnees as erreur:
        print(f"Frais non ajoutés à {piece['id']} : {erreur}")
        return piece
    piece["valeurs"].update(valeurs)
    piece["source"] = f"{piece['source']} ; {source}"
    piece["traitement"] = f"{piece['traitement']} ; {traitement}"
    piece["limites"] = f"{piece['limites']} ; {frais.LIMITES_FRAIS}"
    return piece


def comparaisons_periode_complete(valeurs: dict[str, float], capital: float) -> dict[str, float]:
    """Comparaisons prêtes à citer, calculées ici pour que l'agent n'en dérive aucune (section 4 ter, règle 6).

    Une perte en dollars se comprend mieux qu'un pourcentage : « au pire moment, 33 660 $
    perdus sur 180 000 $, contre 27 180 $ sans la décision ». Les pertes et les écarts sont
    positifs (valeur absolue) : le texte dit lui-même dans quel sens va la comparaison.
    Les montants sont arrondis au dollar : des centimes n'apprendraient rien au lecteur.

    Returns:
        ``capital`` ; ``perte_au_pire_moment_cad`` et ``perte_au_pire_moment_cad_actuelle``
        (capital × pire baisse, en dollars) et leur écart ; l'écart de pire baisse et de
        rendement annuel en points de pourcentage ; ``rapport_volatilite`` (après / avant).
    """
    perte_apres = capital * abs(valeurs["pire_baisse"])
    perte_actuelle = capital * abs(valeurs["pire_baisse_actuelle"])
    comparaisons = {
        "capital": round(capital),
        "perte_au_pire_moment_cad": round(perte_apres),
        "perte_au_pire_moment_cad_actuelle": round(perte_actuelle),
        "ecart_perte_au_pire_moment_cad": round(abs(perte_apres - perte_actuelle)),
        "ecart_pire_baisse_points": round(abs(valeurs["pire_baisse"] - valeurs["pire_baisse_actuelle"]) * 100, 4),
        "ecart_rendement_annuel_points": round(
            abs(valeurs["rendement_annuel"] - valeurs["rendement_annuel_actuel"]) * 100, 4),
    }
    if valeurs["volatilite_annuelle_actuelle"] > 0:
        comparaisons["rapport_volatilite"] = round(
            valeurs["volatilite_annuelle"] / valeurs["volatilite_annuelle_actuelle"], 4)
    return comparaisons


def comparaisons_2022(valeurs: dict[str, Any], capital: float) -> dict[str, float]:
    """Le rejeu de 2022 en dollars : résultat de l'année sur le capital, avec et sans la décision.

    Les résultats gardent leur signe (une perte est négative) ; l'écart est positif.
    """
    apres = capital * valeurs["rendement_2022_apres"]
    actuel = capital * valeurs["rendement_2022_actuel"]
    return {
        "capital": round(capital),
        "resultat_2022_cad_apres": round(apres),
        "resultat_2022_cad_actuel": round(actuel),
        "ecart_2022_cad": round(abs(apres - actuel)),
        "ecart_2022_points": round(abs(valeurs["rendement_2022_apres"] - valeurs["rendement_2022_actuel"]) * 100, 4),
    }


def exposition_devises(poids: dict[str, float]) -> dict[str, float]:
    """Part du portefeuille dans chaque devise de cotation de l'univers (#112), valeurs brutes.

    C'est le risque de devise : pour un investisseur qui vit en CAD, un titre coté en USD
    varie aussi avec le taux USD/CAD. Toutes les devises de l'univers sont présentes, même
    à 0, pour que la pièce ait toujours les mêmes clés et qu'aucun agent n'ait à calculer
    la part restante (section 4 ter, règle 6).

    Args:
        poids: un poids par titre (``poids_apres_decision`` ou portefeuille de départ).

    Returns:
        Une part par devise, ex. ``{"CAD": 0.6, "USD": 0.4}``.

    Raises:
        ErreurDonnees: titre absent de assets_universe.csv (sa devise n'est jamais devinée).
    """
    devises = charger_univers().set_index("ticker")["currency"]
    parts = {devise: 0.0 for devise in sorted(devises.unique())}
    for ticker, part in poids.items():
        if ticker not in devises.index:
            raise ErreurDonnees(f"« {ticker} » est absent de assets_universe.csv : sa devise est inconnue")
        parts[devises[ticker]] += part
    return parts


def valeurs_exposition_devises(poids_actuels: dict[str, float], poids_apres: dict[str, float]) -> dict[str, float]:
    """Valeurs de la pièce : ``part_usd`` (après la décision) et ``part_usd_actuelle``, pour chaque devise."""
    valeurs = {f"part_{devise.lower()}": part for devise, part in exposition_devises(poids_apres).items()}
    valeurs.update({f"part_{devise.lower()}_actuelle": part
                    for devise, part in exposition_devises(poids_actuels).items()})
    return _arrondir(valeurs)


def decision_simulee(decision: dict[str, Any]) -> tuple[str, dict[str, float]]:
    """Ce que la pièce dit de la décision simulée : un libellé pour le titre, et sa taille brute.

    La taille figure dans les ``valeurs`` : un agent peut alors écrire « à 15 % en TSLA »
    (le Greffier la retrouve dans la pièce) au lieu de deviner quelle taille a été simulée,
    ce qui compte quand plusieurs simulations sont au dossier (contre-interrogatoire, #55).
    """
    if decision["type"] == "reallocation":
        part = decision["part_reallouee"]
        return f"réallocation de {_part(part)} du portefeuille", {"part_reallouee": round(part, DECIMALES_VALEURS)}
    libelle = f"{_part(decision['taille'])} en {decision['ticker']}"
    if decision["financement"].startswith("depuis_"):
        libelle += f", financé par {decision['financement'].removeprefix('depuis_')}"
    return libelle, {"taille": round(decision["taille"], DECIMALES_VALEURS)}


def _part(part: float) -> str:
    """0.15 → « 15 % » ; 0.075 → « 7,5 % » (une décimale au plus, sans signe)."""
    texte = f"{part * 100:.1f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


class _Simulation:
    """Valeurs quotidiennes d'un portefeuille rééquilibré chaque jour (départ à 1)."""

    def __init__(self, debut: pd.Timestamp, rendements_titres: pd.DataFrame, poids: dict[str, float]):
        self.poids = poids
        ponderation = pd.Series(poids).reindex(rendements_titres.columns, fill_value=0.0)
        valeurs = (1 + rendements_titres @ ponderation).cumprod()
        # La valeur de départ (1) est datée de la première séance : un sommet possible.
        self.valeurs = pd.concat([pd.Series([1.0], index=[debut]), valeurs])

    def indicateurs(self) -> dict[str, float]:
        return {
            "rendement_annuel": float(calculer_rendement_annualise(self.valeurs)),
            "volatilite_annuelle": float(calculer_volatilite_annuelle(self.valeurs)),
            "pire_baisse": float(calculer_pire_baisse(self.valeurs)),
            "rendement_2022": float(calculer_rendement_2022(self.valeurs)),
        }


def valeurs_avant_apres(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    """Valeurs quotidiennes (départ à 1) du portefeuille actuel et après la décision.

    Sert aux scénarios de sensibilité (#15), par exemple pour recalculer les
    indicateurs sur une sous-période. Les séries sont des copies.
    """
    actuel, apres = _deux_simulations(portefeuille, decision)
    return actuel.valeurs.copy(), apres.valeurs.copy()


def _deux_simulations(portefeuille, decision) -> tuple[_Simulation, _Simulation]:
    """Le portefeuille actuel et le portefeuille après la décision, sur les mêmes séances."""
    poids_actuels = _poids_actuels(portefeuille)
    poids_apres = poids_apres_decision(portefeuille, decision)
    tickers = tuple(sorted(set(poids_actuels) | set(poids_apres)))
    debut, rendements = _rendements_quotidiens(tickers)
    return _Simulation(debut, rendements, poids_actuels), _Simulation(debut, rendements, poids_apres)


@lru_cache(maxsize=32)
def _rendements_quotidiens(tickers: tuple[str, ...]) -> tuple[pd.Timestamp, pd.DataFrame]:
    """Première séance et rendements quotidiens en CAD des titres, calculés une seule fois.

    Le cache sert ``taille_max_compatible`` (#21), qui simule le même ensemble de
    titres une trentaine de fois. Le DataFrame renvoyé est partagé : ne pas le modifier.
    """
    prix = charger_donnees(list(tickers))
    return prix.index[0], prix.pct_change().iloc[1:]


def _bornes_2022(valeurs: pd.Series) -> list[str]:
    """Dates ISO de la dernière séance de 2021 et de la dernière séance de 2022.

    Ce sont les bornes du rendement de ``calculer_rendement_2022``, affichées dans la pièce.
    """
    fin_2021 = valeurs.index[valeurs.index.year == 2021]
    fin_2022 = valeurs.index[valeurs.index.year == 2022]
    if fin_2021.empty or fin_2022.empty:
        raise ErreurDonnees("La série ne couvre pas la fin de 2021 et la fin de 2022")
    return [fin_2021[-1].date().isoformat(), fin_2022[-1].date().isoformat()]


# --- Pièces -------------------------------------------------------------------


def _piece_periode_complete(id_piece: str, actuel: _Simulation, apres: _Simulation,
                            decision: dict[str, Any]) -> dict[str, Any]:
    ind_actuel, ind_apres = actuel.indicateurs(), apres.indicateurs()
    debut, fin = apres.valeurs.index[0], apres.valeurs.index[-1]
    annees = round((fin - debut).days / 365.25)
    libelle, valeurs_decision = decision_simulee(decision)
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": f"Simulation du portefeuille avec {libelle}",
        "outil": NOM_OUTIL,
        "valeurs": _arrondir({
            **valeurs_decision,
            "pire_baisse": ind_apres["pire_baisse"],
            "rendement_annuel": ind_apres["rendement_annuel"],
            "volatilite_annuelle": ind_apres["volatilite_annuelle"],
            "pire_baisse_actuelle": ind_actuel["pire_baisse"],
            "rendement_annuel_actuel": ind_actuel["rendement_annuel"],
            "volatilite_annuelle_actuelle": ind_actuel["volatilite_annuelle"],
        }) | valeurs_exposition_devises(actuel.poids, apres.poids),
        "valeur_affichee": (
            f"{formater_pourcentage(ind_apres['pire_baisse'])} max · "
            f"{formater_pourcentage(ind_apres['rendement_annuel'])}/an"
        ),
        "source": source_des_prix(),
        "traitement": (
            "Rendements quotidiens en CAD, calendrier des séances américaines, rééquilibrage "
            f"quotidien, {debut.date().isoformat()} → {fin.date().isoformat()} ; {TRAITEMENT_DEVISES}"
        ),
        "limites": f"{LIMITES_PERIODE_COMPLETE.format(annees=annees)} ; {LIMITES_DEVISES}",
    }


def _piece_rejeu_2022(id_piece: str, actuel: _Simulation, apres: _Simulation,
                      decision: dict[str, Any]) -> dict[str, Any]:
    rendement_actuel = actuel.indicateurs()["rendement_2022"]
    rendement_apres = apres.indicateurs()["rendement_2022"]
    libelle, valeurs_decision = decision_simulee(decision)
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": f"Rejeu de 2022 avec {libelle}",
        "outil": NOM_OUTIL,
        "valeurs": {
            **valeurs_decision,
            "periode": _bornes_2022(apres.valeurs),
            **_arrondir({"rendement_2022_actuel": rendement_actuel, "rendement_2022_apres": rendement_apres}),
        },
        "valeur_affichee": f"{formater_pourcentage(rendement_actuel)} → {formater_pourcentage(rendement_apres)}",
        "source": source_des_prix(),
        "traitement": (
            "Portefeuille avec et sans la position, de la dernière séance de 2021 "
            "à la dernière séance de 2022"
        ),
        "limites": LIMITES_REJEU,
    }


def _arrondir(valeurs: dict[str, float]) -> dict[str, float]:
    """Valeurs brutes d'une pièce : arrondies à DECIMALES_VALEURS, comme dans pipeline.indicateurs."""
    return {nom: round(valeur, DECIMALES_VALEURS) for nom, valeur in valeurs.items()}


@lru_cache(maxsize=1)
def source_des_prix() -> str:
    """Source des prix et du taux de change, avec la date d'extraction des prix."""
    return (
        f"Yahoo Finance via yfinance (adj_close), extrait le {date_extraction('prices_daily.csv')} ; "
        "USD/CAD Banque du Canada"
    )


def formater_pourcentage(valeur: float, decimales: int = 1) -> str:
    """-0.2897 → « −29,0 % » ; 0.1198 → « +12,0 % » (signe écrit, virgule française).

    Le signe moins est le caractère « − » (U+2212), comme dans la maquette. Une
    valeur qui s'arrondit à zéro n'a pas de signe.
    """
    texte = f"{abs(valeur) * 100:.{decimales}f}".replace(".", ",")
    if not texte.strip("0,"):
        return f"{texte} %"
    return f"{'−' if valeur < 0 else '+'}{texte} %"


# --- Description pour l'orchestrateur Bedrock (#12) --------------------------

DESCRIPTION = (
    "Simule le portefeuille du profil avant et après la décision (prix en CAD, rééquilibrage "
    "quotidien) et produit une pièce. periode « complete » : pire baisse, rendement annualisé "
    "et volatilité sur toute la période d'analyse, et part du portefeuille cotée en USD (risque "
    "de devise). periode « 2022 » : rejeu de l'année où "
    "actions et obligations ont baissé ensemble. Pièce obligatoire : la simulation complète "
    "de la décision demandée."
)


def decrire_simuler_portefeuille(tickers_univers: list[str], portefeuille: list[dict[str, Any]]) -> dict[str, Any]:
    """Description de l'outil pour Bedrock (*tool use*), propre au portefeuille du profil.

    Les listes de valeurs permises empêchent le modèle de demander un titre hors
    de l'univers ou un financement depuis un titre absent du portefeuille. La
    taille n'a pas de borne dans le schéma : Python la vérifie
    (``poids_apres_decision``) et renvoie une erreur lisible.
    """
    tickers_portefeuille = sorted({ligne["ticker"] for ligne in portefeuille})
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ticker", "taille", "financement", "periode"],
        "properties": {
            "ticker": {
                "type": "string",
                "enum": sorted(tickers_univers),
                "description": "Titre de la décision",
            },
            "taille": {
                "type": "number",
                "description": "Part du portefeuille visée, en décimale entre 0 et 1 (0.30 = 30 %)",
            },
            "financement": {
                "type": "string",
                "enum": ["proportionnel"] + [f"depuis_{t}" for t in tickers_portefeuille],
                "description": "« proportionnel » : toutes les lignes réduites au prorata ; "
                "« depuis_<ticker> » : seule cette ligne est réduite",
            },
            "periode": {
                "type": "string",
                "enum": ["complete", "2022"],
                "description": "« complete » : toute la période d'analyse ; « 2022 » : rejeu de l'année de crise",
            },
        },
    }
    return decrire_outil(NOM_OUTIL, DESCRIPTION, schema)


def decrire_simuler_reallocation() -> dict[str, Any]:
    """Description de l'outil pour une décision de **réallocation** (#16).

    Le panier est celui de la décision (lu par Python) : le modèle choisit
    seulement la part réallouée et la période.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["part_reallouee", "periode"],
        "properties": {
            "part_reallouee": {
                "type": "number",
                "description": "Part du portefeuille réallouée vers le panier de la décision, "
                "en décimale entre 0 et 1 (1.0 = tout le portefeuille)",
            },
            "periode": {
                "type": "string",
                "enum": ["complete", "2022"],
                "description": "« complete » : toute la période d'analyse ; « 2022 » : rejeu de l'année de crise",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        DESCRIPTION + " Ici, la décision est une réallocation vers le panier qu'elle décrit : "
        "la part réallouée est prise au prorata de toutes les lignes.",
        schema,
    )
