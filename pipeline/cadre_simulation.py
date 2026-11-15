"""Contrôle du cadre « simulation seulement » (#60) : aucun conseil personnalisé, aucune promesse.

Selon le case officiel, la gouvernance vérifie les contraintes de l'investisseur **et** le
cadre « simulation seulement » du défi (p. 9), et le prototype ne doit pas se présenter
comme du conseil financier personnalisé (p. 17). Le Procureur et l'Avocat argumentent à
partir des pièces : ils ne recommandent aucune transaction et ne prédisent pas l'avenir.

Python seul, sans LLM : des expressions régulières fixes et testées
(``tests/test_cadre_simulation.py``). Deux familles d'infractions :

1. **conseil** : recommandation ou ordre (« vous devriez », « je recommande »,
   « il faut vendre », « Robert devrait alléger », impératif comme « achetez ») ;
2. **promesse** : prévision ou garantie sur l'avenir, à la hausse comme à la baisse
   (« va monter », « rapportera », « TSLA devrait rebondir », « garanti », « à coup sûr »).

Ce qui n'est pas visé :
- les citations entre guillemets (« Préserver mon capital ») : c'est le Pacte de l'utilisateur ;
- une prévision ou une garantie **niée** (« le passé ne prédit pas l'avenir », « rien ne
  garantit », « ne se répétera pas forcément »). Un conseil nié reste un conseil
  (« ne vendez pas ») ;
- le conditionnel d'un scénario (« si 2022 se répétait, le portefeuille ferait… »), le
  passé (« TSLA a rapporté ») et la possibilité (« il peut s'exposer au titre ») ;
- le présent de l'indicatif après « vous » (« si vous vendez… ») : ce n'est pas un impératif ;
- une interrogation indirecte ou une hypothèse (« le Tribunal ne dit pas s'il faut vendre »,
  « savoir si TSLA va remonter ») : c'est la réponse attendue à une demande de conseil au
  contre-interrogatoire (#55).

Un argument fautif suit la boucle de ``pipeline.chiffres.trier_arguments`` : il est renvoyé
une fois à son agent avec le motif, puis rangé dans ``arguments_rejetes``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.chiffres import TriArguments

APOSTROPHE = "['’]"

# --- Ce qui est masqué ou neutralisé ----------------------------------------------

# Citations : le Pacte ou un document cité mot pour mot n'est pas un conseil de l'agent.
RE_CITATION = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"")

# Une prévision ou une garantie est niée si l'un de ces mots la précède dans la même
# proposition (« rien ne permet de dire que TSLA va monter »). Une proposition s'arrête à
# une ponctuation ou à une conjonction (« Ce n'est pas garanti, mais TSLA va monter »).
NEGATIONS = {"ne", "n", "rien", "aucun", "aucune", "jamais", "nul", "nulle", "non", "sans", "ni", "guère"}
RE_FIN_PROPOSITION = re.compile(r"[.;:!?,()\[\]—–]|\b(?:et|mais|car|donc|or)\b", re.IGNORECASE)

# Interrogation indirecte ou hypothèse, dans la même proposition : ni conseil ni promesse.
# « Le Tribunal ne dit pas s'il faut vendre », « savoir si TSLA va remonter » : c'est la
# réponse attendue à une demande de conseil au contre-interrogatoire (#55).
RE_INTERROGATION_INDIRECTE = re.compile(
    rf"\bsi\b|\bs{APOSTROPHE}ils?\b|\bquand\b|\blorsqu(?:e\b|{APOSTROPHE})|\bce\s+qu(?:e\b|{APOSTROPHE})",
    re.IGNORECASE,
)

# --- 1. Conseil ---------------------------------------------------------------------

# Actions de l'utilisateur sur son portefeuille, à l'infinitif (après « il faut », « devrait »…).
# Exclus exprès, car courants dans une argumentation : « garder (à l'esprit) », « attendre »,
# « choisir », « éviter (de confondre) », « entrer (dans le détail) ».
ACTIONS = (
    "acheter", "racheter", "vendre", "revendre", "investir", "réinvestir", "placer", "miser",
    "parier", "renforcer", "alléger", "réduire", "limiter", "plafonner", "liquider", "céder",
    "solder", "réallouer", "rééquilibrer", "diversifier", "privilégier", "retirer", "renoncer",
    "abandonner", "reconsidérer", "revoir", "conserver", "profiter", "opter",
)
# Impératif (2e personne du pluriel) des actions, plus « choisissez » et « évitez ».
IMPERATIFS = (
    "achetez", "rachetez", "vendez", "revendez", "investissez", "réinvestissez", "placez",
    "misez", "pariez", "renforcez", "allégez", "réduisez", "limitez", "plafonnez", "liquidez",
    "cédez", "soldez", "réallouez", "rééquilibrez", "diversifiez", "privilégiez", "retirez",
    "renoncez", "abandonnez", "reconsidérez", "revoyez", "conservez", "profitez", "optez",
    "choisissez", "évitez",
)

_ACTION = "|".join(ACTIONS)
_DE = rf"d(?:e\s+|{APOSTROPHE}\s*)"
_MOTS = r"(?:[\w'’-]+\s+){0,2}?"  # jusqu'à deux mots entre le verbe et l'action (« donc », « pas »)

RE_CONSEILS = [
    # « vous devriez », « vous ne devriez pas », « vous auriez intérêt à », « vous feriez mieux de »
    re.compile(
        rf"\bvous\s+(?:ne\s+|n{APOSTROPHE}\s*)?"
        r"(?:devriez|auriez\s+(?:intérêt|avantage)|gagneriez\s+à|feriez\s+(?:bien|mieux))\b",
        re.IGNORECASE,
    ),
    # « je recommande », « nous vous conseillons », « je lui suggère », « mon conseil »
    re.compile(
        r"\b(?:je|j['’]|nous)\s*(?:vous\s+|lui\s+|leur\s+)?"
        r"(?:recommande|recommandons|conseille|conseillons|suggère|suggérons|préconise|préconisons)\b"
        r"|\b(?:mon|ma|notre)\s+(?:recommandation|conseil|suggestion)\b",
        re.IGNORECASE,
    ),
    # « il est recommandé de », « il serait conseillé d'alléger » (pas « le seuil recommandé de −12 % »)
    re.compile(
        rf"\b(?:est|serait|sont|seraient)\s+(?:[\w-]+\s+)?(?:recommandé|conseillé|préconisé)e?s?\s+{_DE}",
        re.IGNORECASE,
    ),
    # Obligation ou préférence suivie d'une action : « il faut vendre », « il vaudrait mieux
    # alléger », « il serait prudent de réduire », « Robert devrait vendre », « vous devez renoncer ».
    re.compile(
        r"\b(?:il\s+(?:ne\s+)?(?:vous\s+|lui\s+|leur\s+)?(?:faut|faudrait|faudra)"
        r"|il\s+(?:ne\s+)?(?:vaut|vaudrait)\s+mieux|mieux\s+vaut"
        rf"|(?:est|serait)\s+(?:donc\s+|plus\s+|bien\s+)?"
        rf"(?:préférable|prudent|sage|judicieux|raisonnable|avisé|souhaitable)\s+{_DE}"
        rf"|le\s+mieux\s+(?:est|serait)\s+{_DE}"
        r"|devez|doit|doivent|devrait|devraient|devrions|devons)"
        rf"\s*{_MOTS}(?:{_ACTION})\b",
        re.IGNORECASE,
    ),
]

RE_IMPERATIF = re.compile(rf"\b(?:{'|'.join(IMPERATIFS)})\b(?!\s*-\s*vous\b)", re.IGNORECASE)
# « si vous vendez », « que vous en achetez » : présent de l'indicatif, pas un ordre.
RE_SUJET_VOUS = re.compile(
    rf"\bvous\s+(?:ne\s+|n{APOSTROPHE}\s*)?(?:(?:le|la|les|en|y|lui|leur)\s+|l{APOSTROPHE}\s*)*$",
    re.IGNORECASE,
)

# --- 2. Promesse ----------------------------------------------------------------------

# Mouvements de prix ou de rendement (infinitifs, sans le pronom « se »).
MOUVEMENTS = (
    "monter", "grimper", "progresser", "croître", "croitre", "rebondir", "remonter", "envoler",
    "flamber", "décoller", "redresser", "repartir", "récupérer", "rattraper", "surperformer",
    "sous-performer", "rapporter", "fructifier", "gagner", "chuter", "effondrer", "écrouler",
    "plonger", "dégringoler", "reculer", "décliner", "perdre", "continuer", "poursuivre",
    "répéter", "reproduire",
)
# Verbes aussi transitifs : « va doubler la part crypto » décrit la décision, pas l'avenir.
# Ils ne comptent que sans complément d'objet (« TSLA va doubler en un an »).
MOUVEMENTS_AMBIGUS = ("augmenter", "doubler", "tripler", "baisser", "diminuer")
_OBJET = rf"(?!\s+(?:la|le|les|votre|vos|son|sa|ses|leur|leurs|ce|cette|ces|cet|un|une|des|du)\b|\s+l{APOSTROPHE})"
# « revenir » : « TSLA reviendra à son sommet », mais pas « le verdict vous reviendra ».
_SANS_COMPLEMENT_INDIRECT = r"(?<!vous\s)(?<!lui\s)(?<!leur\s)"


def _radical_futur(infinitif: str) -> str:
    """« monter » → « monter » (montera), « perdre » → « perdr » (perdra)."""
    return infinitif[:-1] if infinitif.endswith("re") else infinitif


def _alternative(verbes: tuple[str, ...], fin: str) -> str:
    return "|".join(f"{verbe}{fin}" for verbe in verbes)


# Infinitif d'un mouvement, après « va » ou « devrait » (« continuer à » et « se » facultatifs).
_INFINITIF_MOUVEMENT = (
    rf"(?:continuer\s+(?:à|de|d{APOSTROPHE})\s*)?(?:se\s+|s{APOSTROPHE}\s*)?"
    rf"(?:(?:{'|'.join(MOUVEMENTS)})\b|(?:{'|'.join(MOUVEMENTS_AMBIGUS)})\b{_OBJET}"
    rf"|{_SANS_COMPLEMENT_INDIRECT}revenir\b)"
)
# Futur simple, 3e personne et « vous » seulement (« montera », « perdront », « gagnerez ») :
# le conditionnel (« monterait ») n'est pas visé.
_FINS_FUTUR = r"(?:a|ont|ez)\b"
_FUTUR = (
    rf"(?:{_alternative(tuple(map(_radical_futur, MOUVEMENTS)), _FINS_FUTUR)})"
    rf"|(?:{_alternative(tuple(map(_radical_futur, MOUVEMENTS_AMBIGUS)), _FINS_FUTUR)}){_OBJET}"
    rf"|{_SANS_COMPLEMENT_INDIRECT}reviendr{_FINS_FUTUR}"
)

RE_PROMESSES = [
    # Futur proche : « va monter », « vont continuer à progresser », « allez perdre »
    re.compile(rf"\b(?:va|vont|allez)\s+{_MOTS}{_INFINITIF_MOUVEMENT}", re.IGNORECASE),
    # Prévision au conditionnel de « devoir » : « TSLA devrait rebondir »
    re.compile(rf"\b(?:devrait|devraient)\s+{_MOTS}{_INFINITIF_MOUVEMENT}", re.IGNORECASE),
    # Futur simple : « rapportera », « se répétera », « chuteront »
    re.compile(rf"\b(?:{_FUTUR})", re.IGNORECASE),
    # Garantie et certitude : « garanti », « à coup sûr », « sans risque », « gain assuré »
    re.compile(
        r"\bgarant(?:i|ie|ies|is|it|issent|ir|ira|iront|issant)\b"
        r"|\bà\s+coup\s+sûr\b|\bsans\s+(?:aucun\s+)?risque\b|\brisque\s+nul\b"
        r"|\b(?:gains?|rendements?|profits?|bénéfices?|plus-values?)\s+(?:[\w-]+\s+)?"
        r"(?:assurée?s?|certaine?s?|sûre?s?)\b",
        re.IGNORECASE,
    ),
    # « le passé prédit l'avenir », « je prédis »
    re.compile(r"\bprédi(?:s|t|sent|ra|ront|re)\b", re.IGNORECASE),
]

# --- Motifs renvoyés à l'agent --------------------------------------------------------

FAMILLES = {
    "conseil": (
        "Conseil personnalisé",
        "le Tribunal ne recommande aucune transaction : exposer ce que montrent les pièces "
        "et laisser l'utilisateur décider",
    ),
    "promesse": (
        "Promesse ou prévision sur l'avenir",
        "le passé ne prédit pas l'avenir : décrire ce que montrent les pièces, ou un scénario "
        "au conditionnel avec l'étiquette « hypothese »",
    ),
}


@dataclass(frozen=True)
class Infraction:
    """Une tournure interdite trouvée dans un argument."""

    famille: str      # « conseil » ou « promesse »
    expression: str   # telle qu'écrite dans l'argument
    debut: int = field(default=0, compare=False)


@dataclass
class VerificationCadre:
    infractions: list[Infraction]
    motif: str | None  # None si l'argument respecte le cadre

    @property
    def valide(self) -> bool:
        return self.motif is None


# --- Détection ----------------------------------------------------------------------

def detecter_infractions(texte: str) -> list[Infraction]:
    """Conseils et promesses d'un texte, dans l'ordre où ils apparaissent (citations exclues)."""
    masque = RE_CITATION.sub(lambda m: " " * len(m.group()), texte)
    conseils = [m for regex in RE_CONSEILS for m in regex.finditer(masque)]
    conseils += [m for m in RE_IMPERATIF.finditer(masque) if not RE_SUJET_VOUS.search(masque[:m.start()])]
    promesses = [m for regex in RE_PROMESSES for m in regex.finditer(masque) if not est_niee(masque, m.start())]
    trouvees = [
        _infraction(famille, texte, m)
        for famille, matches in (("conseil", conseils), ("promesse", promesses))
        for m in matches
        if not est_interrogation_indirecte(masque, m.start())
    ]
    return _sans_chevauchement(trouvees)


def est_niee(texte: str, position: int) -> bool:
    """Un mot de négation précède-t-il la position dans la même proposition ?

    « rien ne garantit », « ne va pas forcément monter », « n'est pas garanti », « sans garantie ».
    """
    mots = re.findall(r"[\w'’]+", _proposition(texte, position))
    return any(morceau.lower() in NEGATIONS for mot in mots for morceau in re.split(APOSTROPHE, mot))


def est_interrogation_indirecte(texte: str, position: int) -> bool:
    """La position est-elle dans une interrogation indirecte ou une hypothèse ?

    « le Tribunal ne dit pas s'il faut vendre », « savoir si TSLA va remonter »,
    « les pièces ne disent pas quand il faut vendre ».
    """
    avant = _proposition(texte, position)
    if RE_INTERROGATION_INDIRECTE.search(avant):
        return True
    # « s'il faut vendre » : la tournure commence à « il », juste après « s' »
    # (mais « s'effondreront » reste une promesse).
    return bool(re.search(rf"\bs{APOSTROPHE}$", avant) and re.match(r"ils?\b", texte[position:], re.IGNORECASE))


def _proposition(texte: str, position: int) -> str:
    """Le début de la proposition qui contient la position (depuis la dernière ponctuation ou conjonction)."""
    return RE_FIN_PROPOSITION.split(texte[:position])[-1]


def _infraction(famille: str, texte: str, m: re.Match) -> Infraction:
    return Infraction(famille, texte[m.start():m.end()].strip(), m.start())


def _sans_chevauchement(infractions: list[Infraction]) -> list[Infraction]:
    """Garde une seule infraction par passage du texte (la plus longue), dans l'ordre du texte."""
    gardees: list[Infraction] = []
    for infraction in sorted(infractions, key=lambda i: (i.debut, -len(i.expression))):
        if gardees and infraction.debut < gardees[-1].debut + len(gardees[-1].expression):
            continue
        gardees.append(infraction)
    return gardees


# --- Vérification d'un argument et compte rendu --------------------------------------

def verifier_cadre_simulation(argument: dict[str, Any]) -> VerificationCadre:
    """Vérifie qu'un argument ne conseille aucune transaction et ne promet rien sur l'avenir."""
    infractions = detecter_infractions(argument["texte"])
    return VerificationCadre(infractions, motif_cadre(infractions))


def motif_cadre(infractions: list[Infraction]) -> str | None:
    """Motif exact renvoyé à l'agent, par famille : les tournures fautives et la règle à suivre.

    Ex. : « Conseil personnalisé : « vous devriez » (le Tribunal ne recommande aucune
    transaction : exposer ce que montrent les pièces et laisser l'utilisateur décider) ».
    """
    parties = []
    for famille, (nom, regle) in FAMILLES.items():
        expressions = list(dict.fromkeys(i.expression for i in infractions if i.famille == famille))
        if expressions:
            parties.append(f"{nom} : {', '.join(f'« {e} »' for e in expressions)} ({regle})")
    return " ; ".join(parties) or None


def controle_cadre_simulation(*tris: TriArguments) -> dict[str, Any]:
    """Contrôle de synthèse du contrat (« Aucun conseil personnalisé ni promesse sur l'avenir : 7 arguments vérifiés »).

    Args:
        tris: résultats de ``pipeline.chiffres.trier_arguments`` (réquisitoire, plaidoirie),
            qui appliquent déjà ce contrôle à chaque argument.
    """
    arguments = sum(len(t.valides) for t in tris)
    rejetes = sum(t.rejetes_cadre for t in tris)
    if arguments == 0:
        return {"statut": "a_verifier", "regle": "cadre_simulation",
                "message": "Aucun argument vérifié : rien à afficher"}
    message = (
        f"Aucun conseil personnalisé ni promesse sur l'avenir : {arguments} "
        f"{_pluriel(arguments, 'argument')} {_pluriel(arguments, 'vérifié')}"
    )
    if rejetes:
        relance = " après une relance" if sum(t.relances for t in tris) else ""
        message += f" ; {rejetes} {_pluriel(rejetes, 'argument')} {_pluriel(rejetes, 'rejeté')}{relance}"
    return {"statut": "conforme", "regle": "cadre_simulation", "message": message}


def _pluriel(nombre: int, mot: str) -> str:
    return mot if nombre <= 1 else mot + "s"
