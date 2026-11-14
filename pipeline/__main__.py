"""Commande locale : fait le procès d'une demande et affiche le contrat JSON.

    python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"

Appelle vraiment Amazon Bedrock (payant) : il faut « aws login » et un fichier .env.
"""

import json
import sys

from dotenv import load_dotenv

from pipeline.tribunal import juger_decision


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print('Usage : python -m pipeline <id_profil> "<demande>"', file=sys.stderr)
        return 2
    load_dotenv()
    contrat = juger_decision(arguments[0], arguments[1])
    print(json.dumps(contrat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
