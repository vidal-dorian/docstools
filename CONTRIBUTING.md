# Contribuer à DocsTools

## Convention de commit

Ce projet suit la convention [Conventional Commits](https://www.conventionalcommits.org/).
Elle permet de garder un historique git lisible et sert de base à la génération
automatique du changelog (via `release-please`).

### Format

```
<type>(<scope optionnel>): <description>

<corps optionnel>

<footer optionnel>
```

### Types autorisés

| Type       | Usage                                                          |
|------------|-----------------------------------------------------------------|
| `feat`     | Nouvelle fonctionnalité                                        |
| `fix`      | Correction de bug                                               |
| `docs`     | Documentation uniquement                                        |
| `style`    | Formatage, points-virgules manquants, etc. (pas de logique)     |
| `refactor` | Changement de code qui ne corrige pas un bug ni n'ajoute une fonctionnalité |
| `perf`     | Amélioration de performance                                     |
| `test`     | Ajout ou correction de tests                                     |
| `chore`    | Tâches diverses (dépendances, config, etc.)                      |
| `ci`       | Changements liés à l'intégration continue                        |
| `build`    | Changements liés au système de build ou aux dépendances externes |

### Exemples

```
feat(ingest): ajoute le parsing des fichiers ECMAXML
fix(api): corrige le calcul du score BM25
docs: met à jour le README avec les instructions d'installation
chore: met à jour les dépendances
```

### Vérification locale

Le projet utilise [Commitizen](https://commitizen-tools.github.io/commitizen/) via
[pre-commit](https://pre-commit.com/) pour valider le message de commit avant qu'il
ne soit créé.

Installation (une seule fois par clone) :

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
```

À partir de là, tout commit dont le message ne respecte pas la convention sera
rejeté localement.

### Vérification en CI

Les messages de commit d'une pull request sont également vérifiés automatiquement
par le workflow [`commitlint.yml`](.github/workflows/commitlint.yml). Une pull
request contenant un commit non conforme est bloquée.
