"""Données précalculées de l'interface Astrée (spec de l'interface, annexe B).

    .venv\\Scripts\\python -X utf8 scripts\\build_ui_series.py

Lit les mêmes fichiers que le pipeline (``alphaforge_starter/``, ``personas/``,
``config/``, ``donnees_externes/``) et **réutilise ses fonctions de calcul**
(``pipeline.simulation``, ``pipeline.indicateurs``, ``pipeline.greffier``, rassemblées
dans ``pipeline.vues_interface``, que la Lambda utilise aussi pour un profil créé, #86) :
l'interface affiche exactement les chiffres que le Tribunal citerait. Le script
écrit du JSON dans ``frontend/src/data/generated/`` :

- ``calendrier.json`` : séances retenues pour les courbes (une par semaine) ;
- ``univers.json`` : les 31 titres, libellés français, indicateurs en CAD, documents ESG ;
- ``profils/<id>.json`` : portefeuille actuel, indicateurs, courbe de valeur, Pacte ;
- ``decisions/<id>/<ticker>.json`` : une position de 0 à 50 %, par pas de 1 point ;
- ``paniers/<id>.json`` : chaque composition du panier de démonstration, par pas de 5 points ;
- ``calibrage/<id>.json`` : le Pacte vécu (#68), un vrai jour de marché par niveau de baisse,
  les questions complémentaires et les réponses préenregistrées du profil de test ;
- ``questionnaire.json`` : les questions du questionnaire investisseur (#84), et pour le mode
  démonstration de l'écran « Construire mon Pacte » (#86), l'exemple de réponses
  ``docs/exemples/reponses_questionnaire.json`` avec ce que la Lambda renverrait (aperçu, profil
  signé et ses vues) ; ses tables de décision vont dans ``decisions/<id de l'exemple>/``.

Rien n'est estimé dans le navigateur : le curseur et le panier lisent ces tables.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from pipeline.categories import categories_du_titre, charger_categories  # noqa: E402
from pipeline.documents import charger_corpus  # noqa: E402
from pipeline.donnees import charger_donnees, charger_univers, date_extraction  # noqa: E402
from pipeline.indicateurs import calculer_temps_recuperation  # noqa: E402
from pipeline.pacte import charger_pacte  # noqa: E402
from pipeline.questionnaire import (  # noqa: E402
    contradictions,
    detail_bareme,
    profil_depuis_reponses,
    questions,
    valider_reponses,
)
from pipeline.vues_interface import (  # noqa: E402
    ECHELLE_RECUL,
    TAILLES,
    brut,
    construire_calibrage,
    construire_profil,
    groupe_du_titre,
    indicateurs,
    positions_hebdomadaires,
    table_panier,
    table_position,
    valeurs_actuelles,
    vues_profil,
)

DONNEES_FRONT = RACINE / "frontend" / "src" / "data"
SORTIE = DONNEES_FRONT / "generated"
DOSSIER_PERSONAS = RACINE / "personas"
EXEMPLE_QUESTIONNAIRE = RACINE / "docs" / "exemples" / "reponses_questionnaire.json"



def construire_univers(libelles: dict[str, Any]) -> list[dict[str, Any]]:
    univers = charger_univers()
    documents = charger_corpus()["documents"]
    titres = []
    for _, ligne in univers.iterrows():
        ticker = ligne["ticker"]
        prix = charger_donnees([ticker])[ticker]
        recuperation = calculer_temps_recuperation(prix)
        titres.append({
            "ticker": ticker,
            "nom": libelles["noms"].get(ticker, ligne["name"]),
            "nomOriginal": ligne["name"],
            "classe": libelles["classes"].get(ligne["asset_class"], ligne["asset_class"]),
            "classeId": ligne["asset_class"],
            "bourse": libelles["bourses"].get(ligne["market"], ligne["market"]),
            "devise": ligne["currency"],
            "secteur": libelles["secteurs"].get(ligne["sector"], ligne["sector"]),
            "groupe": groupe_du_titre(ligne),
            "categories": sorted(categories_du_titre(ticker)),
            **indicateurs(prix),
            "anneesRecuperation": (brut(recuperation["annees_recuperation"])
                                   if recuperation["annees_recuperation"] is not None else None),
            "documents": [
                {"critere": d["critere"], "valeur": d["valeur"], "valeurAffichee": d["valeur_affichee"],
                 "titre": d["titre"], "source": d["source"], "dateConsultation": d["date_consultation"]}
                for d in documents if d["ticker"] == ticker
            ],
        })
    return titres


# --- Écriture -----------------------------------------------------------------------


def construire_questionnaire() -> tuple[dict[str, Any], dict[str, Any]]:
    """Questions, et exemple de démonstration rejoué comme la Lambda le ferait (routes /profil, #86).

    Les réponses de l'exemple sont préenregistrées : elles portent l'étiquette « fictif ».
    Renvoie aussi le profil signé, pour en écrire les tables de décision.
    """
    saisie = json.loads(EXEMPLE_QUESTIONNAIRE.read_text(encoding="utf-8"))
    profil = profil_depuis_reponses(saisie["reponses"], saisie["capital_cad"], saisie["portefeuille"],
                                    saisie["date"], identifiant=saisie["id"], nom=saisie["nom"],
                                    etiquette_reponses="fictif")
    resultat = {"profil": profil, "bareme": detail_bareme(saisie["reponses"], saisie["date"]),
                "contradictions": contradictions(valider_reponses(saisie["reponses"]))}
    demo = {
        "saisie": {cle: saisie[cle] for cle in ("nom", "reponses", "portefeuille")} | {"capital": saisie["capital_cad"]},
        "apercu": resultat,
        "signe": {"id": profil["id"], **resultat, "vues": vues_profil(profil)},
    }
    return {"questions": questions(), "demo": demo}, profil


def ecrire(chemin: Path, contenu: Any, compact: bool = False) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    options = {"separators": (",", ":")} if compact else {"indent": 1}
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, **options) + "\n", encoding="utf-8")


def main(arguments: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parseur.add_argument("--profils", nargs="*", help="identifiants des profils (défaut : tous)")
    options = parseur.parse_args(arguments)

    debut = time.perf_counter()
    libelles = json.loads((DONNEES_FRONT / "libelles.json").read_text(encoding="utf-8"))
    profils_ui = json.loads((DONNEES_FRONT / "profils_ui.json").read_text(encoding="utf-8"))["profils"]
    fichiers = sorted(DOSSIER_PERSONAS.glob("*.json"))
    profils = [charger_pacte(f) for f in fichiers if f.name != "schema_pacte.json"]
    if options.profils:
        profils = [p for p in profils if p["id"] in options.profils]

    univers = construire_univers(libelles)
    par_ticker = {t["ticker"]: t for t in univers}
    reference = valeurs_actuelles(profils[0]["portefeuille"])
    semaines = positions_hebdomadaires(reference.index)
    ecrire(SORTIE / "calendrier.json", {
        "debut": reference.index[0].date().isoformat(),
        "fin": reference.index[-1].date().isoformat(),
        "extraction": date_extraction("prices_daily.csv"),
        "seances": len(reference),
        "semaines": [reference.index[i].date().isoformat() for i in semaines],
        "echelleRecul": ECHELLE_RECUL,
    })
    ecrire(SORTIE / "univers.json", univers)
    ecrire(SORTIE / "categories.json", {nom: definition["libelle"]
                                         for nom, definition in charger_categories().items()})
    print(f"Univers : {len(univers)} titres")

    for profil in profils:
        ecrire(SORTIE / "profils" / f"{profil['id']}.json", construire_profil(profil, par_ticker, semaines))
        ecrire(SORTIE / "calibrage" / f"{profil['id']}.json", construire_calibrage(profil), compact=True)
        mode = profils_ui.get(profil["id"], {}).get("recherche", {}).get("mode")
        if mode is None:
            mode = "panier" if (profil.get("decision_demo") or {}).get("type") == "reallocation" else "position"
        if mode == "panier":
            candidats = profils_ui[profil["id"]]["panierDemo"]
            table = table_panier(profil, candidats, semaines)
            ecrire(SORTIE / "paniers" / f"{profil['id']}.json", table, compact=True)
            print(f"{profil['id']} : {len(table['compositions'])} compositions du panier {candidats}")
        else:
            for ticker in par_ticker:
                ecrire(SORTIE / "decisions" / profil["id"] / f"{ticker}.json",
                       table_position(profil, ticker, semaines), compact=True)
            print(f"{profil['id']} : {len(par_ticker)} titres × {len(TAILLES)} tailles")
    questionnaire, exemple = construire_questionnaire()
    ecrire(SORTIE / "questionnaire.json", questionnaire)
    for ticker in par_ticker:
        ecrire(SORTIE / "decisions" / exemple["id"] / f"{ticker}.json",
               table_position(exemple, ticker, semaines), compact=True)
    print(f"Questionnaire : {len(questionnaire['questions'])} questions ; exemple « {exemple['id']} » "
          f"et ses {len(par_ticker)} tables de décision")
    print(f"Terminé en {time.perf_counter() - debut:.0f} s → {SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
