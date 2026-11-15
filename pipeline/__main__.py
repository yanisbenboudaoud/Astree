"""Commande locale : fait le procès d'une demande et affiche le contrat JSON.

    python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"
    python -m pipeline robert "…" --calibrage-demo   # avec les réponses préenregistrées du Pacte vécu (#68)

Appelle vraiment Amazon Bedrock (payant) : il faut « aws login » et un fichier .env.
"""

import json
import sys

from dotenv import load_dotenv

from pipeline.agent_profil import chemin_profil
from pipeline.calibrage import reponses_demo
from pipeline.pacte import charger_pacte
from pipeline.tribunal import juger_decision

OPTION_CALIBRAGE = "--calibrage-demo"


def main(arguments: list[str]) -> int:
    avec_calibrage = OPTION_CALIBRAGE in arguments
    arguments = [a for a in arguments if a != OPTION_CALIBRAGE]
    if len(arguments) != 2:
        print(f'Usage : python -m pipeline <id_profil> "<demande>" [{OPTION_CALIBRAGE}]', file=sys.stderr)
        return 2
    load_dotenv()
    calibrage = None
    if avec_calibrage:
        reponses, date = reponses_demo(charger_pacte(chemin_profil(arguments[0])))
        calibrage = {"reponses": reponses, "date": date, "etiquette": "fictif"}
    contrat = juger_decision(arguments[0], arguments[1], calibrage=calibrage)
    print(json.dumps(contrat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
