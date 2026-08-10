# docstools
DocsTools — outil de recherche rapide dans la documntation .NET, avec parsing ECMAXML vers SQLite, rechrche BM25 et rerank vectoriel.

## Releases

Les releases (version, changelog, tag GitHub) sont générées automatiquement par
[release-please](https://github.com/googleapis/release-please) à partir des
commits [Conventional Commits](https://www.conventionalcommits.org/) fusionnés
sur `main`.

À chaque push sur `main`, le workflow [`release-please.yml`](.github/workflows/release-please.yml)
crée ou met à jour une « Release PR » qui accumule le changelog et le bump de
version (semver, basé sur `feat` → minor, `fix` → patch, `BREAKING CHANGE` → major).
Merger cette PR déclenche la création du tag et de la release GitHub.
