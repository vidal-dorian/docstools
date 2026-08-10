# Spécification — DocsTools

## Objectif

DocsTools est un outil de recherche rapide dans la documentation .NET. Il permet de :

- **Parser** la documentation ECMAXML (issue du dépôt `dotnet-api-docs/`) et de la convertir en base **SQLite**.
- **Rechercher** dans cette base via une recherche textuelle **BM25**.
- **Reranker** les résultats à l'aide d'un modèle vectoriel (rerank sémantique).

## Structure du dépôt

| Dossier | Rôle |
|---|---|
| `ingest/` | Scripts et outils d'ingestion : parsing ECMAXML → SQLite |
| `api/` | API de recherche (BM25 + rerank vectoriel) |
| `web/` | Interface web de consultation/recherche |
| `docs/` | Documentation du projet (ce fichier, specs, notes) |

## Étapes du projet

Le projet est découpé en User Stories (US), regroupées par epics (voir les issues du dépôt). Ce document sera complété au fur et à mesure de l'avancement.
