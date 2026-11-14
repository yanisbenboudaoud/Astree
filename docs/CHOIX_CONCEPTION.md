# Choix de conception de la pipeline agentique

Ce document explique **comment** la pipeline AlphaForge AI est construite et surtout **pourquoi**. Il sert de base à la documentation technique, à la vidéo et au pitch.

> Les références « diapo X » renvoient à la présentation officielle du datathon. Les numéros `#X` renvoient aux issues GitHub.

---

## Vue d'ensemble

```
Demande de l'utilisateur + persona
              │
              ▼
┌──────────────────────┐
│ 1. Agent Profil      │  LLM : comprendre le texte → contraintes structurées      (#8)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. Outils Python     │  Calculs : rendement, volatilité, pire baisse             (#4, #5, #6)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. Agent Analyse     │  Python : poids  |  LLM : candidats et raisons            (#9)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. Agent Gouvernance │  Python : règles  |  LLM : formulation du message         (#10)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. Agent Explicab.   │  LLM : rédaction  →  Python : vérificateur de chiffres    (#11)
└──────────┬───────────┘
           ▼
     JSON du contrat (+ trace d'exécution dans S3)                                 (#2, #12)
```

Infrastructure AWS : **Bedrock** (LLM), **Lambda** (exécution), **S3** (données et traces), **API Gateway** (accès de l'interface). Voir #7 et #13.

---

## Choix 1 — « Python calcule, le LLM explique »

**Décision.** Tous les chiffres (rendement, volatilité, pire baisse, poids) sont calculés par des fonctions Python testées. Le LLM ne produit jamais un chiffre lui-même.

**Pourquoi.**
- Un LLM peut **inventer un chiffre crédible** (hallucination). Dans un contexte financier, c'est inacceptable.
- L'énoncé demande des explications **fidèles aux données, vérifiables**, qui n'**inventent aucune justification** (énoncé, section 4 ; diapo 11).
- Un calcul Python donne **toujours le même résultat** pour les mêmes données : il est reproductible et testable.

**Alternative écartée.** Laisser le LLM lire les prix et calculer lui-même. C'est plus rapide à coder, mais impossible à vérifier et non reproductible.

---

## Choix 2 — Un orchestrateur à ordre fixe

**Décision.** Les agents s'exécutent toujours dans le même ordre : Profil → Indicateurs → Analyse → Gouvernance → Explicabilité (#12).

**Pourquoi.**
- **Prévisible :** chaque exécution suit le même chemin, donc elle est facile à déboguer en un weekend.
- **Facile à expliquer** au jury et à montrer dans la vidéo.
- La présentation le dit : *une approche simple, focalisée et vérifiable peut être plus forte qu'une architecture spectaculaire mais impossible à expliquer* (diapo 8).

**Alternative écartée.** Un seul agent « autonome » qui décide lui-même quels outils appeler et dans quel ordre. C'est plus impressionnant, mais il peut sauter une étape (par exemple la gouvernance), boucler ou se comporter différemment d'une exécution à l'autre.

**Ce qui reste agentique.** Les agents utilisent des données et des outils, coordonnent des tâches avec des points de contrôle et adaptent l'analyse au persona. Ce sont les 4 dimensions de la diapo 5 : mobiliser, coordonner, adapter, expliquer.

---

## Choix 3 — Un rôle clair par agent

La présentation demande pour chaque agent : *« Pourquoi cet agent existe-t-il et quelle valeur apporte-t-il ? »* (diapo 5).

| Agent | Valeur apportée | Rôle du LLM | Rôle de Python |
|---|---|---|---|
| **Profil** | Transformer une demande en langage naturel en contraintes structurées | Comprendre le texte, extraire les actifs demandés | Valider la sortie, fusionner avec le fichier du persona |
| **Analyse** | Proposer une allocation fictive adaptée au profil | Choisir les candidats, rédiger la raison de chaque choix | Calculer les poids avec une règle documentée |
| **Gouvernance** | Vérifier les contraintes et **contester** une demande incohérente | Formuler le message d'alerte | Appliquer les règles (seuils, exclusions, plafonds) |
| **Explicabilité** | Rendre le résultat compréhensible et vérifiable | Rédiger l'explication | Vérifier chaque chiffre cité |

**Pourquoi.** Un agent sans rôle clair, c'est de la « complexité décorative » (diapo 5). Ici, si on retire un agent, une fonction précise disparaît.

---

## Choix 4 — La gouvernance par règles déterministes

**Décision.** Les vérifications sont des règles Python. Exemple : *si la volatilité de TSLA dépasse la volatilité maximale de Robert, alors l'agent lève une alerte `conflit`*.

**Pourquoi.**
- Une vérification doit être **fiable** : la même situation doit toujours donner la même réponse. Un LLM peut répondre différemment à chaque appel.
- Les règles sont **testables** (ex. : Robert + TSLA → au moins une alerte `conflit`).
- Chaque alerte cite **le chiffre et le seuil**, donc l'utilisateur comprend pourquoi.
- C'est exactement le test de **Robert** : le système doit *remettre en question une demande incohérente avec le profil* au lieu d'*acquiescer automatiquement*.

**Alternative écartée.** Demander au LLM « TSLA convient-il à Robert ? ». La réponse pourrait varier, être influencée par la formulation de la demande, et serait difficile à justifier.

---

## Choix 5 — Le vérificateur de chiffres

**Décision.** Après la rédaction de l'explication, une fonction Python extrait chaque nombre du texte et vérifie qu'il existe dans les indicateurs ou les contraintes. En cas d'erreur, le texte est régénéré une fois. Si l'erreur persiste, la phrase fautive est retirée et une alerte est ajoutée (#11).

**Pourquoi.**
- C'est une **garantie concrète contre les hallucinations**, et pas seulement une consigne donnée au LLM.
- C'est un argument fort pour le pitch : *« notre système ne peut pas citer un chiffre inventé sans qu'on le détecte »*.

---

## Choix 6 — La trace d'exécution

**Décision.** Chaque étape ajoute à la trace ce qu'elle a reçu, ce qu'elle a fait (outil appelé) et ce qu'elle a produit. La trace est incluse dans le JSON et stockée dans S3.

**Pourquoi.**
- L'énoncé demande, dans la documentation technique, *un exemple reliant une conclusion aux données ou aux traces d'exécution observables*.
- Elle permet de **remonter de la conclusion jusqu'aux données** : « TSLA est rejeté » ← alerte de gouvernance ← volatilité calculée ← prix `adj_close` de `prices_daily.csv`.
- Stockée dans S3, elle donne à AWS un **rôle réel** dans l'explicabilité, ce qui compte pour l'admissibilité (diapo 7).

---

## Choix 7 — Les personas en fichiers de configuration

**Décision.** Les contraintes de chaque persona (volatilité max, pire baisse max, horizon, exclusions, préférences) sont dans `personas/<nom>.json`, avec une justification pour chaque seuil (#3).

**Pourquoi.**
- Les seuils sont des **hypothèses**, pas des faits. L'énoncé demande de distinguer *faits, hypothèses et scénarios fictifs*. Un fichier séparé rend ces hypothèses visibles.
- On peut **changer une hypothèse sans toucher au code**. C'est ce qui permet les tests de sensibilité (#15) : *« Changez une hypothèse. Changez un profil. Votre solution reste-t-elle cohérente ? »* (diapo 8).

---

## Choix 8 — Un contrat JSON entre la pipeline et l'interface

**Décision.** La pipeline produit toujours le même format JSON, défini dans `CLAUDE.md` (section 5) et validé par un schéma (#2, #12).

**Pourquoi.**
- La pipeline et l'interface sont développées **en parallèle** : l'interface utilise un faux JSON en attendant la vraie pipeline.
- Le format impose de toujours fournir `hypotheses`, `sources`, `limites` et `avertissement`, donc l'explicabilité est **structurelle** et ne dépend pas de la bonne volonté du LLM.

---

## Choix 9 — Peu de services AWS, chacun justifié

| Service | Rôle | Pourquoi ce service |
|---|---|---|
| **Bedrock** | LLM des agents | Cœur agentique ; rôle d'AWS directement démontrable |
| **Lambda** | Exécute la pipeline | Aucun serveur à gérer, coût à l'usage |
| **S3** | Données et traces | Traces conservées et consultables (explicabilité) |
| **API Gateway** | Point d'accès de l'interface | Renvoie le JSON du contrat |

**Pourquoi peu de services.** La présentation dit : *« Ne multipliez pas les services pour impressionner. Justifiez chaque choix. »* (diapo 7).

**Sécurité.** Aucune clé dans le code ni dans Git, rôle IAM minimal (accès au bucket et `bedrock:InvokeModel` seulement).

---

## Choix 10 — Livrer petit, puis élargir

**Décision.** Version 1 = Robert de bout en bout. Ensuite Amira (V2), puis Mateo (V3) si le temps le permet.

**Pourquoi.**
- Robert est le persona le plus **démonstratif** : il montre que la gouvernance sait dire non.
- Avoir **toujours une version qui fonctionne** protège contre le manque de temps.
- Robert puis Amira donnent les **deux situations contrastées** recommandées pour la vidéo (diapo 4).

---

## Limites connues de cette conception

- **Les seuils des personas sont des hypothèses** choisies par l'équipe. Ils ne sont pas des recommandations réglementaires.
- **Les règles d'allocation sont volontairement simples**, choisies pour être explicables plutôt qu'optimales.
- **Indicateurs historiques :** les performances passées ne prédisent pas les performances futures. La volatilité n'est qu'un indicateur de risque parmi d'autres.
- **Biais du survivant** dans l'univers d'actifs fourni (choisi en 2026).
- **Données ESG** : aucune n'est fournie, elles dépendent de sources externes (V3).
- **Simulation uniquement :** aucune transaction réelle, aucun conseil financier personnalisé.
