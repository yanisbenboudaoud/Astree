"""Outil 6 du Greffier : verifier_chiffres (CLAUDE.md, section 4 ter).

Promesse du pitch : « aucun chiffre inventé ne passe ». Chaque nombre écrit
dans un argument (Procureur, Avocat, contre-interrogatoire) doit exister dans
une pièce **citée par l'argument**, dans la décision ou dans la période
d'analyse. Python seul, sans LLM.

Règles appliquées (numéros de la section 4 ter) :
1. extraits : pourcentages, décimaux, entiers, années, dates ; pas les id de
   pièces (« P1 »), les nombres collés à des lettres, ni les noms d'actifs
   (« S&P 500 ») ; la virgule n'est décimale que si un chiffre la suit ;
2. comparés aux pièces citées, à la décision et à la période seulement ;
3. arrondi au nombre de décimales écrit (× 100 pour un « % ») ; « près de »
   ou « environ » ne donnent aucune tolérance ;
4. signe écrit obligatoire, sauf juste après « chute de », « baisse de »,
   « perte de », « recul de » (valeur absolue) ;
5. une date doit correspondre à une date ISO des sources ;
6. aucun nombre dérivé (un écart ou un ratio absent des pièces est rejeté) ;
7. plages vérifiées nombre par nombre, listes des pièces aplaties ;
8. argument refusé : renvoyé une fois à son agent, puis rejeté (``trier_arguments``) ;
9. compte rendu : ``controle_verifier_chiffres``.

``trier_arguments`` applique aussi le contrôle du cadre « simulation seulement »
(``pipeline.cadre_simulation``, #60) : un argument qui conseille une transaction ou
promet un rendement suit la même boucle, et les deux motifs partent dans la même relance.

Le dossier a le format de ``pipeline.debat`` : ``decision``, ``pieces`` et
``periode`` (``[debut, fin]`` en dates ISO).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Iterator

from pipeline.cadre_simulation import VerificationCadre, verifier_cadre_simulation

# --- Extraction -----------------------------------------------------------------

MOIS = {
    "janvier": 1, "janv": 1, "février": 2, "fevrier": 2, "févr": 2, "fevr": 2, "fév": 2,
    "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7,
    "août": 8, "aout": 8, "septembre": 9, "sept": 9, "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11, "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}
_MOIS = "|".join(sorted(MOIS, key=len, reverse=True))

RE_DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
RE_JOUR_MOIS = re.compile(
    rf"(?<![\w.,])(\d{{1,2}})(?:er)?\s+({_MOIS})\.?(?!\w)(?:\s+(\d{{4}})(?!\d))?", re.IGNORECASE
)
RE_MOIS_ANNEE = re.compile(rf"(?<!\w)({_MOIS})\.?\s+(\d{{4}})(?!\d)", re.IGNORECASE)

# Entier (avec espaces de milliers) et partie décimale facultative. La virgule
# ou le point n'est décimal que si un chiffre le suit (« en 2022, TSLA »).
RE_NOMBRE = re.compile(r"(?<![\w.,])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?(?!\w)")
RE_POURCENT = re.compile(r"[   ]*%")

# Noms d'actifs qui contiennent un nombre : jamais extraits.
NOMS_ACTIFS_AVEC_NOMBRE = re.compile(
    r"S&P\s*/\s*TSX\s*60|S&P\s*500|Nasdaq[\s-]?100|TSX\s*60|20\+\s*(?:Year|ans)", re.IGNORECASE
)

SIGNE_PLUS = "+"
SIGNES_MOINS = "-−–"  # trait d'union, signe moins (U+2212), tiret demi-cadratin

# « chute de 29 % » : le nombre est comparé en valeur absolue.
RE_MOT_BAISSE = re.compile(
    r"\b(?:chute|baisse|perte|recul)s?\s+(?:de\s+|d['’]\s*)"
    r"(?:(?:près\s+de|environ|d['’]environ)\s+)?$",
    re.IGNORECASE,
)

ANNEE_MIN, ANNEE_MAX = 1900, 2099


@dataclass(frozen=True)
class NombreCite:
    """Un nombre ou une date écrits dans un argument."""

    texte: str                       # tel qu'écrit (« −29,0 % », « janv. 2022 »)
    genre: str                       # « nombre », « annee » ou « date »
    valeur: Decimal | None = None    # sans signe ; None pour une date
    decimales: int = 0
    pourcentage: bool = False
    signe: str | None = None         # « + », « - » ou None
    apres_baisse: bool = False
    date: tuple[int | None, int | None, int | None] | None = None  # (année, mois, jour)


def extraire_nombres(texte: str) -> list[NombreCite]:
    """Nombres et dates d'un texte, dans l'ordre où ils apparaissent."""
    masque = NOMS_ACTIFS_AVEC_NOMBRE.sub(lambda m: " " * len(m.group()), texte)
    trouves: list[tuple[int, NombreCite]] = []

    def masquer(m: re.Match) -> None:
        nonlocal masque
        masque = masque[:m.start()] + " " * (m.end() - m.start()) + masque[m.end():]

    for m in list(RE_DATE_ISO.finditer(masque)):
        jour = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        trouves.append((m.start(), NombreCite(m.group(), "date", date=jour)))
        masquer(m)
    for m in list(RE_JOUR_MOIS.finditer(masque)):
        annee = int(m.group(3)) if m.group(3) else None
        jour = (annee, MOIS[m.group(2).lower()], int(m.group(1)))
        trouves.append((m.start(), NombreCite(texte[m.start():m.end()], "date", date=jour)))
        masquer(m)
    for m in list(RE_MOIS_ANNEE.finditer(masque)):
        jour = (int(m.group(2)), MOIS[m.group(1).lower()], None)
        trouves.append((m.start(), NombreCite(texte[m.start():m.end()], "date", date=jour)))
        masquer(m)

    for m in RE_NOMBRE.finditer(masque):
        nombre = _lire_nombre(texte, masque, m)
        if nombre is not None:
            trouves.append(nombre)
    return [nombre for _, nombre in sorted(trouves, key=lambda t: t[0])]


def _lire_nombre(texte: str, masque: str, m: re.Match) -> tuple[int, NombreCite] | None:
    debut, fin = m.start(), m.end()
    signe = None
    precedent = masque[debut - 1] if debut > 0 else ""
    if precedent and precedent in SIGNE_PLUS + SIGNES_MOINS:
        avant = masque[debut - 2] if debut > 1 else ""
        if avant.isalpha():
            return None  # collé à des lettres (« COVID-19 »)
        if not avant.isdigit():  # un tiret entre deux nombres est une plage (« 3-5 »)
            signe = "+" if precedent == SIGNE_PLUS else "-"
            debut -= 1

    pourcent = RE_POURCENT.match(masque, fin)
    if pourcent:
        fin = pourcent.end()
    entier = re.sub(r"\D", "", m.group(1))
    decimales = m.group(2) or ""
    valeur = Decimal(f"{entier}.{decimales}" if decimales else entier)

    est_annee = (
        signe is None and not pourcent and not decimales and len(m.group(1)) == 4
        and ANNEE_MIN <= int(entier) <= ANNEE_MAX
    )
    return debut, NombreCite(
        texte=texte[debut:fin],
        genre="annee" if est_annee else "nombre",
        valeur=valeur,
        decimales=len(decimales),
        pourcentage=bool(pourcent),
        signe=signe,
        apres_baisse=signe is None and bool(RE_MOT_BAISSE.search(masque[:debut])),
        date=(int(entier), None, None) if est_annee else None,
    )


# --- Sources admises ------------------------------------------------------------

RE_ISO_COMPLETE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Sources:
    """Valeurs auxquelles un nombre cité peut correspondre."""

    nombres: list[Decimal] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)

    def ajouter(self, valeur: Any) -> None:
        for feuille in _aplatir(valeur):
            if isinstance(feuille, bool) or feuille is None:
                continue
            if isinstance(feuille, (int, float)):
                self.nombres.append(Decimal(str(feuille)))
            elif isinstance(feuille, str) and RE_ISO_COMPLETE.match(feuille):
                try:
                    self.dates.append(date.fromisoformat(feuille))
                except ValueError:
                    pass


def _aplatir(valeur: Any) -> Iterator[Any]:
    """Feuilles d'une valeur de pièce : les listes et les dict sont aplatis."""
    if isinstance(valeur, dict):
        for sous_valeur in valeur.values():
            yield from _aplatir(sous_valeur)
    elif isinstance(valeur, (list, tuple)):
        for sous_valeur in valeur:
            yield from _aplatir(sous_valeur)
    else:
        yield valeur


def sources_toujours_admises(dossier: dict[str, Any]) -> Sources:
    """La décision et la période d'analyse, admises pour tout argument."""
    sources = Sources()
    sources.ajouter(dossier["decision"])
    sources.ajouter(list(dossier["periode"]))
    return sources


def sources_piece(piece: dict[str, Any]) -> Sources:
    sources = Sources()
    sources.ajouter(piece["valeurs"])
    return sources


# --- Correspondance -------------------------------------------------------------

def correspond(nombre: NombreCite, sources: Sources) -> bool:
    """Le nombre cité existe-t-il dans ces sources (règles 3 à 5) ?"""
    if nombre.genre == "date":
        return any(_meme_date(nombre.date, d) for d in sources.dates)
    if nombre.genre == "annee" and any(d.year == nombre.date[0] for d in sources.dates):
        return True
    return any(_meme_nombre(nombre, v) for v in sources.nombres)


def _meme_date(ecrite: tuple, source: date) -> bool:
    annee, mois, jour = ecrite
    return (
        (annee is None or annee == source.year)
        and (mois is None or mois == source.month)
        and (jour is None or jour == source.day)
    )


def _meme_nombre(nombre: NombreCite, valeur: Decimal) -> bool:
    convertie = valeur * 100 if nombre.pourcentage else valeur
    arrondie = convertie.quantize(Decimal(1).scaleb(-nombre.decimales), rounding=ROUND_HALF_UP)
    if nombre.signe == "-":
        return arrondie == -nombre.valeur
    if nombre.signe is None and nombre.apres_baisse:
        return abs(arrondie) == nombre.valeur
    return arrondie == nombre.valeur  # signe « + » ou sans signe : lu comme positif


# --- Vérification d'un argument -------------------------------------------------

@dataclass
class VerificationArgument:
    nombres: list[NombreCite]
    introuvables: list[NombreCite]
    motif: str | None  # None si l'argument est prouvé

    @property
    def valide(self) -> bool:
        return self.motif is None


def verifier_argument(argument: dict[str, Any], dossier: dict[str, Any]) -> VerificationArgument:
    """Vérifie chaque nombre de l'argument contre ses pièces citées, la décision et la période."""
    pieces = {piece["id"]: piece for piece in dossier["pieces"]}
    citees = list(argument.get("pieces", []))
    nombres = extraire_nombres(argument["texte"])

    if not citees:
        return VerificationArgument(nombres, [], "Aucune pièce citée : un argument cite au moins une pièce")
    inconnues = [p for p in citees if p not in pieces]
    if inconnues:
        return VerificationArgument(nombres, [], f"Pièce citée inexistante : {', '.join(inconnues)}")

    admises = sources_toujours_admises(dossier)
    for id_piece in citees:
        sources_citee = sources_piece(pieces[id_piece])
        admises.nombres += sources_citee.nombres
        admises.dates += sources_citee.dates

    introuvables = [n for n in nombres if not correspond(n, admises)]
    if not introuvables:
        return VerificationArgument(nombres, [], None)
    non_citees = {i: sources_piece(p) for i, p in pieces.items() if i not in citees}
    motif = " ; ".join(_motif(n, citees, admises, non_citees) for n in introuvables)
    return VerificationArgument(nombres, introuvables, motif)


def _motif(nombre: NombreCite, citees: list[str], admises: Sources, non_citees: dict[str, Sources]) -> str:
    """Motif exact renvoyé à l'agent : nombre fautif, pièces citées, et une piste si possible."""
    motif = f"« {nombre.texte} » introuvable dans {', '.join(citees)}"
    ailleurs = [i for i, sources in non_citees.items() if correspond(nombre, sources)]
    if ailleurs:
        return f"{motif} (présent dans {', '.join(ailleurs)}, pièce non citée)"
    if nombre.genre != "date" and nombre.signe is None:
        negatif = NombreCite(nombre.texte, "nombre", nombre.valeur, nombre.decimales, nombre.pourcentage, signe="-")
        if correspond(negatif, admises):
            return f"{motif} : valeur négative, écrire le signe « − »"
    return motif


def detailler_argument(argument: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    """La vérification d'un argument, nombre par nombre, pour l'afficher (« Trompez le Greffier », #69).

    Mêmes règles et même verdict que ``verifier_argument`` ; en plus, pour chaque nombre :
    où il a été trouvé (pièce citée, « décision » ou « période ») ou, s'il est introuvable,
    son motif exact.

    Returns:
        ``valide``, ``motif`` (None si l'argument est prouvé), ``nombres`` (``texte``,
        ``trouve``, ``sources``, ``motif``) et ``compte`` (« 2/3 »).
    """
    verification = verifier_argument(argument, dossier)
    pieces = {piece["id"]: piece for piece in dossier["pieces"]}
    citees = [p for p in dict.fromkeys(argument.get("pieces", [])) if p in pieces]
    par_source = {id_piece: sources_piece(pieces[id_piece]) for id_piece in citees}
    decision, periode = Sources(), Sources()
    decision.ajouter(dossier["decision"])
    periode.ajouter(list(dossier["periode"]))
    par_source.update({"décision": decision, "période": periode})

    admises = sources_toujours_admises(dossier)
    for id_piece in citees:
        admises.nombres += par_source[id_piece].nombres
        admises.dates += par_source[id_piece].dates
    non_citees = {i: sources_piece(p) for i, p in pieces.items() if i not in citees}

    nombres = []
    for nombre in verification.nombres:
        sources = [nom for nom, valeurs in par_source.items() if correspond(nombre, valeurs)]
        nombres.append({
            "texte": nombre.texte,
            "trouve": bool(sources),
            "sources": sources,
            "motif": None if sources or not citees else _motif(nombre, citees, admises, non_citees),
        })
    trouves = sum(n["trouve"] for n in nombres)
    return {"valide": verification.valide, "motif": verification.motif, "nombres": nombres,
            "compte": f"{trouves}/{len(nombres)}"}


# --- Tri des arguments et compte rendu ------------------------------------------

@dataclass
class TriArguments:
    """Arguments d'un côté après vérification (et une relance au plus par argument)."""

    valides: list[dict[str, Any]]
    rejetes: list[dict[str, Any]]   # format « arguments_rejetes » du contrat
    nombres_verifies: int           # nombres des arguments valides (une date compte pour un)
    relances: int
    rejetes_chiffres: int = 0       # rejetés pour un chiffre introuvable
    rejetes_cadre: int = 0          # rejetés pour un conseil ou une promesse (#60)


def trier_arguments(
    arguments: list[dict[str, Any]],
    cote: str,
    dossier: dict[str, Any],
    corriger: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
) -> TriArguments:
    """Vérifie les arguments d'un côté ; un argument refusé est renvoyé **une fois** à son agent.

    Deux vérifications par argument : ses chiffres (``verifier_argument``) et le cadre
    « simulation seulement » (``verifier_cadre_simulation``, #60). Un argument qui échoue
    à l'une ou à l'autre est renvoyé avec tous ses motifs, en une seule relance.

    Args:
        arguments: arguments du Procureur ou de l'Avocat (etiquette, texte, pieces).
        cote: « requisitoire » ou « plaidoirie ».
        dossier: décision, pièces et période (format de ``pipeline.debat``).
        corriger: ``corriger(argument, motif) -> argument réécrit`` ; en pratique
            ``pipeline.debat.corriger_argument`` (l'orchestrateur garde la trace).
            None : aucun renvoi, l'argument refusé est rejeté tout de suite.
    """
    tri = TriArguments([], [], 0, 0)
    for argument in arguments:
        chiffres, cadre, motif = _verifier(argument, dossier)
        if motif and corriger is not None:
            tri.relances += 1
            argument = corriger(argument, motif)
            chiffres, cadre, motif = _verifier(argument, dossier)
        if not motif:
            tri.valides.append(argument)
            tri.nombres_verifies += len(chiffres.nombres)
            continue
        tri.rejetes.append({
            "cote": cote,
            "etiquette": argument["etiquette"],
            "texte": argument["texte"],
            "pieces": list(argument["pieces"]),
            "raison": motif,
        })
        tri.rejetes_chiffres += int(not chiffres.valide)
        tri.rejetes_cadre += int(not cadre.valide)
    return tri


def _verifier(
    argument: dict[str, Any], dossier: dict[str, Any]
) -> tuple[VerificationArgument, VerificationCadre, str | None]:
    """Chiffres et cadre d'un argument, et le motif commun (None si l'argument passe les deux)."""
    chiffres = verifier_argument(argument, dossier)
    cadre = verifier_cadre_simulation(argument)
    motif = " ; ".join(m for m in (chiffres.motif, cadre.motif) if m) or None
    return chiffres, cadre, motif


def controle_verifier_chiffres(*tris: TriArguments) -> dict[str, Any]:
    """Contrôle de synthèse du contrat (« 17/17 chiffres, 7 arguments »)."""
    nombres = sum(t.nombres_verifies for t in tris)
    arguments = sum(len(t.valides) for t in tris)
    rejetes = sum(t.rejetes_chiffres for t in tris)
    if arguments == 0:
        return {"statut": "a_verifier", "regle": "verifier_chiffres",
                "message": "Aucun argument vérifié : rien à afficher"}
    message = (
        f"Chiffres cités vérifiés contre leurs pièces : {nombres}/{nombres} {_pluriel(nombres, 'chiffre')}, "
        f"{arguments} {_pluriel(arguments, 'argument')}"
    )
    if rejetes:
        relance = " après une relance" if sum(t.relances for t in tris) else ""
        message += f" ; {rejetes} {_pluriel(rejetes, 'argument')} {_pluriel(rejetes, 'rejeté')}{relance}"
    return {"statut": "conforme", "regle": "verifier_chiffres", "message": message}


def _pluriel(nombre: int, mot: str) -> str:
    return mot if nombre <= 1 else mot + "s"
