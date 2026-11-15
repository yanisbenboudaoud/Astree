# AlphaForge AI : le Tribunal des décisions d'investissement

*Datathon PolyFinances 2026. Simulation éducative : aucune transaction réelle, aucun conseil financier personnalisé.*

**Le problème.** Un investisseur prend souvent une décision sur un coup de cœur (« je mets 30 % en Tesla »), sans la confronter aux règles qu'il s'était fixées à tête reposée. Les outils existants lui disent quoi acheter, ou lui donnent des chiffres sans dire d'où ils viennent. Et un assistant IA classique a tendance à acquiescer, ou à inventer un chiffre plausible.

**Notre solution : le Tribunal.** L'utilisateur arrive avec **sa propre décision**. Le système ne recommande rien : il en fait le **procès**.
1. Le **Pacte** : les règles de l'investisseur, écrites à l'avance (pire baisse acceptée, plafonds, exclusions, critères ESG). Il vient d'un questionnaire, ou d'un « Pacte vécu » où l'on revit de vrais jours de baisse.
2. Un **orchestrateur** (IA sur Amazon Bedrock) choisit lui-même les preuves à rassembler. Chaque preuve est calculée par Python sur les données et devient une **pièce numérotée**.
3. Un **Procureur** argumente contre la décision, un **Avocat** pour, en citant uniquement les pièces.
4. Le **Greffier**, un programme sans IA, vérifie le Pacte, vérifie que **chaque chiffre cité existe dans une pièce**, et refuse tout conseil ou promesse.
5. **L'utilisateur rend le verdict** : maintenir, modifier sa décision ou ajuster son Pacte. Le système ne bloque jamais.

**Ce qui est original.**
- **Un procès plutôt qu'une recommandation** : la personne reste maître de sa décision, et le système reste du côté de l'aide à la décision.
- **Python calcule, l'IA explique** : l'IA n'écrit jamais un chiffre qu'un calcul n'a pas produit.
- **« Qu'est-ce qui changerait la réponse ? »** : pour chaque règle dépassée, la taille ou le seuil qui la rendrait conforme.
- **N'importe quel investisseur** : un nouveau profil, c'est un fichier JSON, sans une ligne de code. La même décision reçoit des verdicts différents selon le Pacte.

**Les données.** Cinq ans de prix quotidiens (Yahoo Finance, 2021-11-12 au 2026-11-12), taux de change et données macroéconomiques de la Banque du Canada, tout converti en dollars canadiens. L'équipe y a ajouté des documents ESG publics, les frais et la composition des FNB, relevés chez les émetteurs, chacun avec sa source, sa date et ses limites.

**L'explicabilité, vérifiable.** Chaque argument remonte à sa pièce, chaque pièce à l'outil et au fichier de données, chaque appel d'outil à la raison donnée par l'orchestrateur. Tout est archivé et peut être relu. Mesures publiées dans le dépôt ([`evaluation_chiffres.md`](validation/evaluation_chiffres.md)) : le Greffier a détecté **66 chiffres inventés sur 66** et accepté **80 arguments valides sur 80** ; sa limite connue y est mesurée aussi.

**AWS au cœur.** Amazon Bedrock fait raisonner les agents, AWS Lambda exécute le pipeline et le Greffier, Amazon S3 garde les données et la trace de chaque procès, Amazon CloudFront sert l'interface.

**Les bénéfices.**
- **Pour l'investisseur** : une décision confrontée à ses propres règles, avec les preuves des deux côtés et ce qui changerait la réponse.
- **Pour un conseiller ou une institution** : un dossier de décision imprimable, traçable et auditable, où chaque chiffre a une source.
- **Pour la confiance dans l'IA** : un agent qui peut contredire l'utilisateur, mais jamais inventer.

*Pour aller plus loin : [`DOCUMENTATION_TECHNIQUE.md`](DOCUMENTATION_TECHNIQUE.md) · Interface : https://d15khh2djw55mh.cloudfront.net*
