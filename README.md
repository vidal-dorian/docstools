# docstools
DocsTools — outil de recherche rapide dans la documntation .NET, avec parsing ECMAXML vers SQLite, rechrche BM25 et rerank vectoriel.

## Contribuer

Les messages de commit suivent la convention [Conventional Commits](https://www.conventionalcommits.org/).
Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le détail et la mise en place du hook local.
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

## Licence

Ce projet est distribué sous licence [MIT](LICENSE).
