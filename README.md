# docstools
DocsTools — outil de recherche rapide dans la documntation .NET, avec parsing ECMAXML vers SQLite, rechrche BM25 et rerank vectoriel.

## Stratégie de branches

Le projet suit un Git Flow simplifié :

| Branche | Rôle |
|---|---|
| `main` | Branche de production : toujours stable et déployable. Protégée (voir ci-dessous). |
| `dev` | Branche d'intégration continue des fonctionnalités avant leur passage en production. |
| `feature/nom-de-la-fonctionnalite` | Développement d'une nouvelle fonctionnalité, partant de `dev` et fusionnée dans `dev`. |
| `fix/nom-du-correctif` | Correction de bug non urgente, partant de `dev` et fusionnée dans `dev`. |
| `hotfix/nom-du-correctif` | Correction urgente en production, partant de `main` et fusionnée dans `main` (puis répercutée dans `dev`). |
| `release/x.y.z` | Préparation d'une release depuis `dev` avant fusion dans `main` (généralement gérée automatiquement par `release-please`, voir plus bas). |

Toutes les branches de travail (`feature/*`, `fix/*`, `hotfix/*`, `release/*`) sont
fusionnées via **pull request**, jamais poussées directement sur `main`.

### Protection de la branche `main`

La branche `main` est protégée sur GitHub :
- Push direct interdit (toute modification passe par une pull request)
- Au moins 1 revue/approbation requise avant fusion
- Les checks de CI doivent être au vert avant fusion
- Suppression de la branche interdite
- Force-push interdit
