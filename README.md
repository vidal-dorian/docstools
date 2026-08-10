# docstools
DocsTools — outil de recherche rapide dans la documntation .NET, avec parsing ECMAXML vers SQLite, rechrche BM25 et rerank vectoriel.

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
