"""Procès-verbal d'un procès : le contrat JSON rendu en page HTML imprimable (#57).

Un procès archivé contient déjà tout ce qu'un dossier de décision doit garder :
la décision, le Pacte et sa date de signature, les pièces (source, traitement,
limites), les contrôles du Greffier, les arguments (acceptés et rejetés), la trace
et le verdict de l'utilisateur. Ce module les met en page, rien de plus.

Garanties :
- **Python seul, sans LLM** : chaque texte vient du contrat, ou d'un libellé fixe
  de ``LIBELLES`` (titres de sections, noms de colonnes) ;
- tout texte du contrat est échappé (``html.escape``) : un contrat ne peut pas
  injecter de HTML ;
- même contrat → même page (aucune date ni valeur aléatoire ajoutée).

Usage :
    python -m pipeline.proces_verbal docs/exemples/contrat_robert.json -o pv.html
    python -m pipeline.proces_verbal --demo   # procès enregistrés de l'interface (frontend/public/proces-verbaux/)
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PROCES_DEMO = RACINE / "frontend" / "src" / "data" / "proces"
DOSSIER_PV_DEMO = RACINE / "frontend" / "public" / "proces-verbaux"

LIBELLES = {
    "titre": "Procès-verbal d'audience",
    "bandeau": "Simulation · aucune transaction réelle · aucun conseil personnalisé",
    "origine": "Document produit par Python à partir du contrat JSON du procès, sans texte ajouté "
               "par un modèle de langage. Les arguments du Procureur et de l'Avocat sont reproduits "
               "tels qu'ils ont été vérifiés par le Greffier.",
    "audience": "Audience",
    "profil": "Profil",
    "demande": "Demande",
    "decision": "Décision jugée",
    "pacte": "Pacte",
    "signe_le": "Signé le",
    "profil_risque": "Profil de risque",
    "horizon": "Horizon",
    "comparaison": "Portefeuille avant et après la décision",
    "taille_max": "Taille maximale compatible avec les règles calculables du Pacte",
    "taille_max_nulle": "Aucune : même 0 % viole le Pacte",
    "controles": "Contrôles du Greffier",
    "requisitoire": "Réquisitoire (Procureur, contre la décision)",
    "plaidoirie": "Plaidoirie (Avocat, pour la décision)",
    "rejetes": "Arguments rejetés par le Greffier",
    "aucun_rejet": "Aucun argument rejeté.",
    "contre_interrogatoire": "Contre-interrogatoire",
    "question": "Question",
    "pieces": "Pièces à conviction",
    "trace": "Trace d'exécution",
    "hypotheses": "Hypothèses",
    "sources": "Sources",
    "limites": "Limites",
    "verdict": "Verdict de l'utilisateur",
    "avertissement": "Avertissement",
    "aucun": "Aucun.",
    "ans_et_plus": "ans et plus",
    "ans": "ans",
    "a": "à",
    "pieces_citees": "Pièces citées",
    "raison": "Motif du rejet",
    "extrait_le": "extrait le",
    "controle_de": "Contrôle de la règle",
}

VERDICTS = {
    "maintenu": "Décision maintenue par l'utilisateur",
    "modifie": "Décision modifiée par l'utilisateur",
    "pacte_ajuste": "Pacte ajusté par l'utilisateur",
    None: "Verdict non encore rendu au moment de l'export",
}
STATUTS = {"conforme": "Conforme", "violation": "Violation", "a_verifier": "À vérifier"}
ETIQUETTES = {"fait": "Fait", "hypothese": "Hypothèse", "fictif": "Fictif"}
COTES = {"requisitoire": "Procureur", "plaidoirie": "Avocat"}
INDICATEURS = {
    "rendement_annuel": "Rendement annualisé",
    "volatilite_annuelle": "Volatilité annualisée",
    "pire_baisse": "Pire baisse",
    "rendement_2022": "Rendement 2022",
}
COLONNES = {
    "indicateur": "Indicateur", "actuel": "Actuel", "apres": "Après la décision",
    "statut": "Statut", "regle": "Règle", "message": "Message", "libelle": "Libellé",
    "etape": "Étape", "outil": "Outil", "entree": "Entrée", "sortie": "Sortie",
    "type": "Type", "etiquette": "Étiquette", "valeur": "Valeur affichée",
    "valeurs": "Valeurs brutes", "source": "Source", "traitement": "Traitement",
    "utilisee_par": "Utilisée par (et pourquoi)",
}

STYLE = """
  :root{--encre:#1A1712;--encre2:#3F3A31;--discret:#675F52;--filet:#D9D2C3;--fond:#FFFFFF;
        --violation:#A1281D;--verifier:#8A5800;--conforme:#2B6A3E}
  *{box-sizing:border-box}
  body{margin:0;background:var(--fond);color:var(--encre);
       font:15px/1.5 "Atkinson Hyperlegible Next",system-ui,-apple-system,"Segoe UI",sans-serif}
  main{max-width:860px;margin:0 auto;padding:32px 24px 48px}
  h1,h2{font-family:Newsreader,Georgia,"Times New Roman",serif;font-weight:500}
  h1{font-size:34px;margin:8px 0 4px} h2{font-size:21px;margin:32px 0 10px;padding-top:14px;border-top:1.5px solid var(--encre)}
  h3{font-size:15px;margin:18px 0 6px}
  .bandeau{display:inline-block;border:1px solid var(--encre);padding:4px 10px;font-size:12px;letter-spacing:.01em}
  .discret{color:var(--discret)} .petit{font-size:13px}
  table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0}
  th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--filet)}
  th{font-weight:600;color:var(--encre2)}
  code,pre,.mono{font-family:"Atkinson Hyperlegible Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12px}
  pre{white-space:pre-wrap;word-break:break-word;margin:0}
  .statut{font-weight:600} .statut-violation{color:var(--violation)} .statut-a_verifier{color:var(--verifier)}
  .statut-conforme{color:var(--conforme)}
  ul{padding-left:20px} li{margin:4px 0}
  .piece{border-top:1px solid var(--filet);padding:10px 0}
  dl{display:grid;grid-template-columns:150px 1fr;gap:4px 12px;margin:6px 0;font-size:13px}
  dt{color:var(--discret)} dd{margin:0}
  footer{margin-top:40px;font-size:12px;color:var(--discret)}
  @media print{main{padding:0;max-width:none} h2{break-after:avoid} .piece,tr{break-inside:avoid}
               a{color:inherit;text-decoration:none}}
"""


# --- Mise en forme --------------------------------------------------------------

def _t(valeur: Any) -> str:
    """Texte du contrat, échappé."""
    return escape("" if valeur is None else str(valeur))


def _pourcentage(valeur: float | None) -> str:
    """0.30 → « 30,0 % » ; -0.2897 → « −29,0 % » (signe moins U+2212, virgule)."""
    if valeur is None:
        return "—"
    texte = f"{abs(valeur) * 100:.1f}".replace(".", ",")
    return f"{'−' if valeur < 0 and texte.strip('0,') else ''}{texte} %"


def _json(valeur: Any) -> str:
    """Entrée ou sortie d'une étape de trace, telle qu'archivée."""
    if isinstance(valeur, str):
        return _t(valeur)
    return _t(json.dumps(valeur, ensure_ascii=False, sort_keys=False))


def _statut(statut: str) -> str:
    return f'<span class="statut statut-{_t(statut)}">{_t(STATUTS.get(statut, statut))}</span>'


def _pieces_citees(pieces: list[str] | None) -> str:
    return ", ".join(_t(p) for p in pieces or []) or "—"


def _liste(elements: list[str]) -> str:
    if not elements:
        return f"<p>{LIBELLES['aucun']}</p>"
    return "<ul>" + "".join(f"<li>{_t(e)}</li>" for e in elements) + "</ul>"


# --- Sections -------------------------------------------------------------------

def _entete(contrat: dict[str, Any], identifiant: str | None) -> str:
    lignes = [
        f'<p class="bandeau">{LIBELLES["bandeau"]}</p>',
        f"<h1>{LIBELLES['titre']}</h1>",
        "<dl>",
    ]
    if identifiant:
        lignes.append(f"<dt>{LIBELLES['audience']}</dt><dd class=\"mono\">{_t(identifiant)}</dd>")
    decision = contrat.get("decision") or {}
    lignes += [
        f"<dt>{LIBELLES['profil']}</dt><dd>{_t(contrat['persona'])}</dd>",
        f"<dt>{LIBELLES['demande']}</dt><dd>« {_t(contrat['demande'])} »</dd>",
        f"<dt>{LIBELLES['decision']}</dt><dd>{_t(decision.get('libelle', '—'))}</dd>",
        "</dl>",
    ]
    return "\n".join(lignes)


def _pacte(pacte: dict[str, Any]) -> str:
    minimum, maximum = pacte["horizon_ans"]
    horizon = (f"{_t(minimum)} {LIBELLES['ans_et_plus']}" if maximum is None
               else f"{_t(minimum)} {LIBELLES['a']} {_t(maximum)} {LIBELLES['ans']}")
    regles = "".join(
        f"<tr><td class=\"mono\">{_t(r['id'])}</td><td>{_t(r['libelle'])}</td></tr>" for r in pacte["regles"]
    )
    return (
        f"<h2>{LIBELLES['pacte']}</h2>"
        f"<dl><dt>{LIBELLES['signe_le']}</dt><dd>{_t(pacte['date_signature'])}</dd>"
        f"<dt>{LIBELLES['profil_risque']}</dt><dd>{_t(pacte['profil_risque'])}</dd>"
        f"<dt>{LIBELLES['horizon']}</dt><dd>{horizon}</dd></dl>"
        f"<table><thead><tr><th>{COLONNES['regle']}</th><th>{COLONNES['libelle']}</th></tr></thead>"
        f"<tbody>{regles}</tbody></table>"
    )


def _comparaison(contrat: dict[str, Any]) -> str:
    if "comparaison" not in contrat:
        return ""
    actuel, apres = contrat["comparaison"]["actuel"], contrat["comparaison"]["apres"]
    lignes = "".join(
        f"<tr><td>{libelle}</td><td class=\"mono\">{_pourcentage(actuel.get(cle))}</td>"
        f"<td class=\"mono\">{_pourcentage(apres.get(cle))}</td></tr>"
        for cle, libelle in INDICATEURS.items()
    )
    taille = contrat.get("taille_max_compatible", "absente")
    if taille == "absente":
        taille_html = ""
    elif taille is None:
        taille_html = f"<p>{LIBELLES['taille_max']} : {LIBELLES['taille_max_nulle']}</p>"
    else:
        taille_html = f"<p>{LIBELLES['taille_max']} : <strong>{_pourcentage(taille)}</strong></p>"
    return (
        f"<h2>{LIBELLES['comparaison']}</h2>"
        f"<table><thead><tr><th>{COLONNES['indicateur']}</th><th>{COLONNES['actuel']}</th>"
        f"<th>{COLONNES['apres']}</th></tr></thead><tbody>{lignes}</tbody></table>{taille_html}"
    )


def _controles(controles: list[dict[str, Any]]) -> str:
    lignes = "".join(
        f"<tr><td>{_statut(c['statut'])}</td><td class=\"mono\">{_t(c['regle'])}</td>"
        f"<td>{_t(c['message'])}</td><td class=\"mono\">{_pieces_citees(c.get('pieces'))}</td></tr>"
        for c in controles
    )
    return (
        f"<h2>{LIBELLES['controles']}</h2>"
        f"<table><thead><tr><th>{COLONNES['statut']}</th><th>{COLONNES['regle']}</th>"
        f"<th>{COLONNES['message']}</th><th>{LIBELLES['pieces_citees']}</th></tr></thead>"
        f"<tbody>{lignes}</tbody></table>"
    )


def _arguments(titre: str, arguments: list[dict[str, Any]], niveau: str = "h2") -> str:
    elements = "".join(
        f"<li><span class=\"petit discret\">{_t(ETIQUETTES.get(a['etiquette'], a['etiquette']))}</span> "
        f"{_t(a['texte'])} <span class=\"mono discret\">({_pieces_citees(a['pieces'])})</span></li>"
        for a in arguments
    )
    corps = f"<ul>{elements}</ul>" if arguments else f"<p>{LIBELLES['aucun']}</p>"
    return f"<{niveau}>{titre}</{niveau}>{corps}"


def _rejetes(rejetes: list[dict[str, Any]], niveau: str = "h2") -> str:
    if not rejetes:
        return f"<{niveau}>{LIBELLES['rejetes']}</{niveau}><p>{LIBELLES['aucun_rejet']}</p>"
    elements = "".join(
        f"<li><strong>{_t(COTES.get(a['cote'], a['cote']))}</strong> : {_t(a['texte'])} "
        f"<span class=\"mono discret\">({_pieces_citees(a['pieces'])})</span><br>"
        f"<span class=\"petit\">{LIBELLES['raison']} : {_t(a['raison'])}</span></li>"
        for a in rejetes
    )
    return f"<{niveau}>{LIBELLES['rejetes']}</{niveau}><ul>{elements}</ul>"


def _contre_interrogatoire(echanges: list[dict[str, Any]]) -> str:
    if not echanges:
        return ""
    blocs = [f"<h2>{LIBELLES['contre_interrogatoire']}</h2>"]
    for echange in echanges:
        controle = echange["controle_chiffres"]
        blocs += [
            f"<h3>{LIBELLES['question']} : « {_t(echange['question'])} »</h3>",
            _arguments(LIBELLES["requisitoire"], echange["requisitoire"], "h3"),
            _arguments(LIBELLES["plaidoirie"], echange["plaidoirie"], "h3"),
            _rejetes(echange["arguments_rejetes"], "h3"),
            f"<p>{_statut(controle['statut'])} {_t(controle['message'])}</p>",
        ]
    return "".join(blocs)


def _pieces(pieces: list[dict[str, Any]]) -> str:
    blocs = [f"<h2>{LIBELLES['pieces']}</h2>"]
    for p in pieces:
        blocs.append(
            f"<div class=\"piece\"><h3><span class=\"mono\">{_t(p['id'])}</span> · {_t(p['titre'])}</h3><dl>"
            f"<dt>{COLONNES['type']}</dt><dd>{_t(p['type'])} · {_t(ETIQUETTES.get(p['etiquette'], p['etiquette']))}</dd>"
            f"<dt>{COLONNES['outil']}</dt><dd class=\"mono\">{_t(p['outil'])}</dd>"
            f"<dt>{COLONNES['valeur']}</dt><dd>{_t(p['valeur_affichee'])}</dd>"
            f"<dt>{COLONNES['valeurs']}</dt><dd><pre>{_json(p['valeurs'])}</pre></dd>"
            f"<dt>{COLONNES['source']}</dt><dd>{_t(p['source'])}</dd>"
            f"<dt>{COLONNES['traitement']}</dt><dd>{_t(p['traitement'])}</dd>"
            f"<dt>{LIBELLES['limites']}</dt><dd>{_t(p['limites'])}</dd>"
            "</dl></div>"
        )
    return "".join(blocs)


def _trace(trace: list[dict[str, Any]]) -> str:
    lignes = "".join(
        f"<tr><td class=\"mono\">{_t(e['etape'])}</td><td class=\"mono\">{_t(e['outil'])}</td>"
        f"<td>{_t(e.get('raison', ''))}</td><td><pre>{_json(e['entree'])}</pre></td>"
        f"<td><pre>{_json(e['sortie'])}</pre></td></tr>"
        for e in trace
    )
    return (
        f"<h2>{LIBELLES['trace']}</h2>"
        f"<table><thead><tr><th>{COLONNES['etape']}</th><th>{COLONNES['outil']}</th><th>{LIBELLES['raison']}</th>"
        f"<th>{COLONNES['entree']}</th><th>{COLONNES['sortie']}</th></tr></thead><tbody>{lignes}</tbody></table>"
    )


def _sources(sources: list[dict[str, Any]]) -> str:
    """Chaque source, son usage et les pièces qui l'utilisent, avec la raison donnée (#111)."""
    if not sources:
        return f"<h2>{LIBELLES['sources']}</h2><p>{LIBELLES['aucun']}</p>"
    lignes = []
    for s in sources:
        description = _t(s["nom"])
        details = ", ".join(_t(d) for d in (s.get("fichier"), s.get("format")) if d)
        if details:
            description += f" ({details})"
        description += f", {LIBELLES['extrait_le']} {_t(s['date_extraction'])}"
        if s.get("usage"):
            description += f"<br><span class=\"discret\">{_t(s['usage'])}</span>"
        utilisations = [
            f"<li>{_t(u['id'])}" + (f" : {_t(u['raison'])}" if u.get("raison") else "") + "</li>"
            for u in s.get("pieces", [])
        ]
        utilisations += [f"<li>{LIBELLES['controle_de']} « {_t(r)} »</li>" for r in s.get("controles", [])]
        utilisee = f"<ul>{''.join(utilisations)}</ul>" if utilisations else "—"
        lignes.append(f"<tr><td>{description}</td><td>{utilisee}</td></tr>")
    return (
        f"<h2>{LIBELLES['sources']}</h2>"
        f"<table><thead><tr><th>{COLONNES['source']}</th><th>{COLONNES['utilisee_par']}</th></tr></thead>"
        f"<tbody>{''.join(lignes)}</tbody></table>"
    )


# --- Page complète --------------------------------------------------------------

def proces_verbal_html(contrat: dict[str, Any], identifiant: str | None = None) -> str:
    """Le procès-verbal complet d'un contrat, en page HTML autonome et imprimable.

    Args:
        contrat: contrat du procès (format de ``contrat/schema_sortie.json``), avec
            ou sans verdict.
        identifiant: identifiant de l'audience (en-tête ``X-Proces-Id``), s'il existe.
    """
    sections = [
        _entete(contrat, identifiant),
        _pacte(contrat["pacte"]),
        _comparaison(contrat),
        _controles(contrat["controles"]),
        _arguments(LIBELLES["requisitoire"], contrat.get("requisitoire", [])),
        _arguments(LIBELLES["plaidoirie"], contrat.get("plaidoirie", [])),
        _rejetes(contrat.get("arguments_rejetes", [])),
        _contre_interrogatoire(contrat.get("contre_interrogatoire", [])),
        f"<h2>{LIBELLES['verdict']}</h2><p><strong>{_t(VERDICTS.get(contrat.get('verdict'), contrat.get('verdict')))}</strong></p>",
        _pieces(contrat["pieces"]),
        _trace(contrat["trace"]),
        f"<h2>{LIBELLES['hypotheses']}</h2>{_liste(contrat.get('hypotheses', []))}",
        _sources(contrat.get("sources", [])),
        f"<h2>{LIBELLES['limites']}</h2>{_liste(contrat.get('limites', []))}",
        f"<h2>{LIBELLES['avertissement']}</h2><p>{_t(contrat['avertissement'])}</p>",
        f"<footer>{LIBELLES['origine']}</footer>",
    ]
    titre = f"{LIBELLES['titre']} · {_t(contrat['persona'])}"
    return (
        "<!doctype html>\n<html lang=\"fr-CA\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{titre}</title>\n<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        + "\n".join(s for s in sections if s)
        + "\n</main>\n</body>\n</html>\n"
    )


# --- Procès enregistrés de l'interface -------------------------------------------

def proces_demo() -> list[tuple[str, dict[str, Any]]]:
    """(identifiant, contrat) des procès enregistrés de l'interface (``frontend/src/data/proces``).

    Ce sont de vrais procès archivés dans S3 : leur identifiant est celui de l'audience.
    """
    index = json.loads((DOSSIER_PROCES_DEMO / "index.json").read_text(encoding="utf-8"))
    return [
        (entree["procesId"],
         json.loads((DOSSIER_PROCES_DEMO / f"{entree['procesId']}.json").read_text(encoding="utf-8")))
        for entree in index["proces"]
    ]


def ecrire_proces_verbaux_demo(dossier: Path = DOSSIER_PV_DEMO) -> list[Path]:
    """Écrit le procès-verbal de chaque procès enregistré (``<identifiant>.html``), et seulement eux."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = []
    for identifiant, contrat in proces_demo():
        chemin = dossier / f"{identifiant}.html"
        chemin.write_text(proces_verbal_html(contrat, identifiant), encoding="utf-8")
        chemins.append(chemin)
    for perime in set(dossier.glob("*.html")) - set(chemins):  # procès retiré de l'index
        perime.unlink()
    return chemins


def main(arguments: list[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(description="Procès-verbal HTML d'un contrat de procès.")
    lecteur.add_argument("contrat", nargs="?", type=Path, help="fichier JSON du contrat")
    lecteur.add_argument("-o", "--sortie", type=Path, help="fichier HTML à écrire (sinon : sortie standard)")
    lecteur.add_argument("--id", help="identifiant de l'audience, s'il existe")
    lecteur.add_argument("--demo", action="store_true", help="réécrit les procès-verbaux de l'interface")
    options = lecteur.parse_args(arguments)

    if options.demo:
        for chemin in ecrire_proces_verbaux_demo():
            print(chemin)
        return 0
    if options.contrat is None:
        lecteur.error("indiquez un fichier de contrat, ou --demo")
    contrat = json.loads(options.contrat.read_text(encoding="utf-8"))
    page = proces_verbal_html(contrat, options.id)
    if options.sortie:
        options.sortie.write_text(page, encoding="utf-8")
    else:
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
