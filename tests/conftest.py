"""Configuration commune des tests : charge le fichier .env local s'il existe."""

from dotenv import load_dotenv

# Ne remplace pas les variables déjà définies dans l'environnement.
load_dotenv()
