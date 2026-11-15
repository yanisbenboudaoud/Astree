"""Commande locale : fait le procès d'une demande et affiche le contrat JSON.

    python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"
    python -m pipeline robert "…" --calibrage-demo   # avec les réponses préenregistrées du Pacte vécu (#68)
    python -m pipeline sofia "…" --poche=retraite    # profil à poches : la poche jugée (#115)

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
OPTION_POCHE = "--poche="


def main(arguments: list[str]) -> int:
    avec_calibrage = OPTION_CALIBRAGE in arguments
    poche = next((a.removeprefix(OPTION_POCHE) for a in arguments if a.startswith(OPTION_POCHE)), None)
    arguments = [a for a in arguments if a != OPTION_CALIBRAGE and not a.startswith(OPTION_POCHE)]
    if len(arguments) != 2:
        print(f'Usage : python -m pipeline <id_profil> "<demande>" [{OPTION_CALIBRAGE}] [{OPTION_POCHE}<id>]',
              file=sys.stderr)
        return 2
    load_dotenv()
    calibrage = None
    if avec_calibrage:
        reponses, date = reponses_demo(charger_pacte(chemin_profil(arguments[0])))
        calibrage = {"reponses": reponses, "date": date, "etiquette": "fictif"}
    contrat = juger_decision(arguments[0], arguments[1], calibrage=calibrage, poche=poche)
    print(json.dumps(contrat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
