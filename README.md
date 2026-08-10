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
=======
## Documentation

La spécification complète du projet se trouve dans [`docs/specification.md`](docs/specification.md).

## Structure du dépôt

- `ingest/` — parsing ECMAXML → SQLite
- `api/` — API de recherche (BM25 + rerank vectoriel)
- `web/` — interface web
- `docs/` — documentation du projet

## Convention de branches

Chaque fonctionnalité est développée sur une branche dédiée, nommée selon le format :

```
feat/nom-de-la-fonctionnalite
```

## Releases

Les releases (version, changelog, tag GitHub) sont générées automatiquement par
[release-please](https://github.com/googleapis/release-please) à partir des
commits [Conventional Commits](https://www.conventionalcommits.org/) fusionnés
sur `main`.

À chaque push sur `main`, le workflow [`release-please.yml`](.github/workflows/release-please.yml)
crée ou met à jour une « Release PR » qui accumule le changelog et le bump de
version (semver, basé sur `feat` → minor, `fix` → patch, `BREAKING CHANGE` → major).
Merger cette PR déclenche la création du tag et de la release GitHub.

## Licence

Ce projet est distribué sous licence [MIT](LICENSE).
