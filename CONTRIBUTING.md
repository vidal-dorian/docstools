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

## Sécurité

Le dépôt s'appuie sur les fonctionnalités GitHub natives pour détecter secrets
et vulnérabilités automatiquement :

- **Secret scanning** — détecte les secrets (clés API, tokens, credentials)
  committés dans l'historique ou dans une pull request.
- **Push protection** — bloque un `git push` contenant un secret détecté,
  avant même qu'il n'atteigne le dépôt.
- **Code scanning (CodeQL)** — analyse statique automatique du code à chaque
  push et pull request vers `main`/`dev`, ainsi qu'une fois par semaine (voir
  [`codeql.yml`](.github/workflows/codeql.yml)).

Secret scanning et push protection sont des réglages du dépôt (Settings →
Code security and analysis) : ils doivent être activés une fois par un·e
mainteneur·se avec les droits d'administration, ils ne se configurent pas via
un fichier versionné.

### En cas d'alerte

Les alertes des deux fonctionnalités apparaissent dans l'onglet
[**Security**](../../security) du dépôt.

- **Alerte de secret scanning** : considérer le secret comme compromis dès sa
  détection. Le révoquer/régénérer immédiatement auprès du service concerné,
  puis marquer l'alerte comme résolue une fois le secret invalidé. Ne pas se
  contenter de le retirer du code : un secret déjà poussé reste visible dans
  l'historique git tant qu'il n'est pas révoqué côté fournisseur.
- **Alerte de code scanning (CodeQL)** : évaluer la sévérité indiquée, corriger
  dans une pull request dédiée référençant l'alerte, puis vérifier que
  l'alerte se ferme automatiquement une fois le correctif mergé. Si l'alerte
  est un faux positif, la fermer directement depuis l'onglet Security en
  justifiant la raison.
