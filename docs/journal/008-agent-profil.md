# #8 — Agent Profil : demande → décision structurée

- **Issue** : #8 · **PR** : #29, #34 · **Statut** : terminée (les réallocations passent à #16)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/agent_profil.py`** : la phase 1 du Tribunal.
  - `lancer_agent_profil(demande, identifiant_profil, id_piece_pacte)` : **point d'entrée de l'orchestrateur** (#12). Il charge et valide le profil avec `charger_pacte` (#3), **avant** tout appel au LLM, puis structure la demande. Il renvoie un `ResultatAgentProfil`.
  - `ResultatAgentProfil` : `decision` (format du contrat, ou `None`), `controles` (`a_verifier`), `hypotheses`, `trace`, et depuis la 2e PR : `profil` (profil validé), `pacte` (champ `pacte` du contrat) et `piece_pacte` (pièce « Pacte »).
  - `structurer_decision(demande, profil, univers)` : appel au LLM, puis vérification par Python. Le modèle repère le titre, la taille et le financement, avec une sortie JSON imposée ; des listes de valeurs permises l'empêchent de répondre par un ticker hors de l'univers ou un financement hors du portefeuille.
  - `interpreter_extraction` : la partie Python. Elle vérifie chaque champ, **convertit un montant en part** du capital fictif (« 50 000 $ » → 7,7 %) et formate le libellé.
  - `chemin_profil(identifiant)` et `ProfilInconnu` : un identifiant qui ne correspond à aucun fichier `personas/<id>.json` est refusé.
- **`pipeline/univers.py`** (#29) : `charger_univers()` lit `assets_universe.csv` en liste de dictionnaires.
- **Contrat** (#29) : nouveau contrôle système `interpretation_demande`, toujours `a_verifier`, pour une demande incomplète ou ambiguë (`REFERENCE_DU_PROJET.md` section 5, `contrat/valider.py`).

## Comment l'utiliser
```python
from pipeline.agent_profil import lancer_agent_profil

resultat = lancer_agent_profil("Je veux mettre 30 % de mon portefeuille en Tesla", "robert", "P3")
resultat.decision     # {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel", "libelle": "30 % en TSLA"}
resultat.pacte        # champ « pacte » du contrat
resultat.piece_pacte  # pièce P3 « Pacte »
resultat.trace        # charger_pacte → bedrock → valider_decision (étapes « agent_profil »)
```
Si `resultat.decision` vaut `None`, le procès ne peut pas commencer : l'interface affiche les `controles` et demande à l'utilisateur de préciser.

## Comment vérifier
```bash
pytest tests/test_agent_profil.py              # sans réseau : le LLM est remplacé par une extraction écrite à la main
pytest -m bedrock tests/test_agent_profil.py   # 9 vrais appels Bedrock
```
- Le pacte et la pièce produits pour le profil prudent sont **identiques** à ceux de `docs/exemples/contrat_robert.json`.
- Les 3 profils de test et un profil inventé se chargent sans changer le code.
- Un identifiant inconnu (`"../personas/robert"`, `"Robert"`, `"schema_pacte"`…) ou un Pacte invalide sont refusés **sans appel au LLM**.
- Vrais appels (Sonnet 5.5) : les demandes de démo des profils prudent et ESG donnent exactement leur `decision_demo` ; celle du profil audacieux ne donne aucune décision et des contrôles `a_verifier` (attendu, voir plus bas). Les formulations variées passent : « un tiers », « 50 000 $ CAD », « en vendant mes obligations ultra court terme » → `depuis_ZST.TO`, et un titre hors univers ou une taille absente sont signalés.

## Choix faits en cours de route
- **Le LLM comprend, Python décide** : le modèle n'écrit que des champs extraits du texte ; toute conversion (montant → part) et toute validation sont faites en Python.
- **Pas de devinette** : aucune décision si le titre est hors univers, si la taille est absente ou hors de 0 à 100 %, si le montant est en USD, si la demande donne à la fois une part et un montant, ou si c'est une réallocation.
- **Le profil est chargé par identifiant**, pas par chemin : l'identifiant viendra de l'interface, donc il doit respecter le format des `id` de profil (`^[a-z][a-z0-9_]*$`), ce qui l'empêche aussi de désigner un fichier hors de `personas/`.
- **Le numéro de la pièce « Pacte » est un paramètre** : c'est l'orchestrateur qui numérote les pièces (même choix que `piece_pacte`, fiche 003).

## Limites et suite
- **Réallocations (#16)** : la phrase de démo du profil audacieux ne décrit pas le panier (BTC 30 %, ETH 20 %…) ; aucun LLM ne peut le retrouver à partir de ce texte. Le panier devra probablement venir de l'interface (titres et poids choisis), pas du texte libre.
- **Deux fonctions `charger_univers`** : celle de `pipeline/univers.py` (liste de dictionnaires, pour les prompts) et celle de `pipeline/donnees.py` (DataFrame pandas). À regrouper si cela prête à confusion.
- Un montant en USD n'est pas converti : l'utilisateur doit donner une part ou un montant en CAD.
