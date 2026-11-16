"""Configuration commune des tests : charge le fichier .env local s'il existe.

Garde-fou (#189) : un test non marqué ``bedrock`` ne peut pas créer de client Bedrock.
Un appel oublié derrière un faux (ex. : une nouvelle phase du procès) échoue au lieu
d'être facturé.
"""

import pytest
from dotenv import load_dotenv

from pipeline import llm

# Ne remplace pas les variables déjà définies dans l'environnement.
load_dotenv()


@pytest.fixture(autouse=True)
def aucun_appel_bedrock(request, monkeypatch):
    if request.node.get_closest_marker("bedrock") or request.node.get_closest_marker("client_bedrock"):
        return

    def refuser():
        raise AssertionError("Appel Bedrock réel dans un test non marqué « bedrock » : remplacez-le par un faux")

    monkeypatch.setattr(llm, "_client_bedrock", refuser)
