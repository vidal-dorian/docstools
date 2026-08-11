# Déploiement

Procédure, pas à pas, pour construire l'index, mettre à jour et exposer
publiquement le service DocsTools sur le Raspberry Pi. Chaque bloc de
commandes indique de quel dossier il part — s'y placer avant de le lancer.
Voir [`docs/specification.md`](specification.md), section 8, pour
l'architecture générale.

**Explicitement hors périmètre :**
- **Aucun accès entrant vers le Pi déclenché depuis GitHub, aucun secret
  SSH côté GitHub.** Le pipeline CI
  ([`docker-publish.yml`](../.github/workflows/docker-publish.yml))
  construit et publie les images sur GitHub Container Registry à chaque
  merge sur `main`. Le déploiement effectif est **automatique mais
  pull-based** : c'est `watchtower`, sur le Pi, qui va chercher les
  nouvelles images (voir plus bas) — GitHub ne pousse jamais rien vers le
  Pi et n'a besoin d'aucun identifiant pour y accéder.
- **Le Pi n'est pas exposé en SSH.** Toute opération manuelle sur le Pi
  (configuration initiale, dépannage) se fait en local (clavier/écran, ou
  accès physique/console de confiance), jamais via un accès distant
  automatisé.

---

## 1. Cloner le dépôt DocsTools

Contrairement à `toolbox-prod` (dont le `docker-compose.yml` vit dans
`infra/` et pointe vers un `repo/` cloné à part), le `docker-compose.yml`
de DocsTools fait partie du dépôt lui-même : le clone **est** le dossier
de déploiement, pas de sous-dossier `repo/`.

Départ : `/home/pi` (ou l'équivalent de ton choix — tout le reste de cette
page suppose `/home/pi/docstools`, adapter si besoin).

```bash
cd /home/pi
git clone https://github.com/vidal-dorian/docstools.git
```

Résultat : le dossier `/home/pi/docstools/` existe, avec
`docker-compose.yml` directement à sa racine.

---

## 2. Construire l'index (`index.sqlite`)

Tâche de fond, une fois par an environ (spec §4) — plusieurs heures sur un
Pi 5, à lancer la nuit via `tmux` ou `nohup`. `ingest/` n'a aucune
dépendance externe : uniquement la bibliothèque standard Python (3.12+),
rien à installer avec `pip`.

Départ : `/home/pi`.

```bash
# Cloner le dépôt de documentation source (dépôt froid, supprimable
# après le build) — clone superficiel, plusieurs Go quand même.
cd /home/pi
git clone --depth 1 https://github.com/dotnet/dotnet-api-docs.git
```

Puis, depuis `/home/pi/docstools` (pour que `python3 -m ingest.corpus`
trouve le package `ingest/`), lancer le build en tâche de fond. Deux
façons équivalentes — `tmux` s'il est installé, sinon `nohup` (toujours
disponible, sans rien à installer) :

**Avec `tmux`** (permet de se détacher puis se rattacher pour suivre la
progression) :

```bash
# Si tmux n'est pas installé : sudo apt-get update && sudo apt-get install -y tmux
cd /home/pi/docstools
tmux new -s docstools-build
nice -n 19 python3 -m ingest.corpus \
  /home/pi/dotnet-api-docs/xml \
  /home/pi/docstools/index.sqlite
# Ctrl+B puis D pour détacher tmux ; `tmux attach -t docstools-build`
# pour revenir suivre la progression.
```

**Avec `nohup`** (pas d'installation requise) :

```bash
cd /home/pi/docstools
nohup nice -n 19 python3 -m ingest.corpus \
  /home/pi/dotnet-api-docs/xml \
  /home/pi/docstools/index.sqlite \
  > build.log 2>&1 &
# `tail -f build.log` depuis /home/pi/docstools pour suivre la progression.
```

À la fin, la commande affiche le nombre de types/groupes/surcharges et la
répartition `explicit`/`inferred`/`unknown` (voir
[`specification.md` §11](specification.md#11-chiffres-à-mesurer)).

Résultat : le fichier `/home/pi/docstools/index.sqlite` existe — c'est lui
que `docker-compose.yml` monte en lecture seule dans le conteneur `api`
(volume `./index.sqlite:/data/index.sqlite:ro`, résolu depuis le dossier
où tourne `docker compose`, donc `/home/pi/docstools/`).

**Renouveler l'index plus tard (rebuild annuel) :** avant de relancer les
commandes ci-dessus, conserver l'ancien fichier pour permettre un retour
arrière (étape 6) :

```bash
cd /home/pi/docstools
mv index.sqlite "index.$(date +%Y).sqlite"
```

---

## 3. Premier démarrage

Départ : `/home/pi/docstools` (celui créé à l'étape 1, contenant déjà
`index.sqlite` de l'étape 2).

```bash
cd /home/pi/docstools
docker compose up -d
```

Démarre trois conteneurs : `docstools-api-1` (FastAPI), `docstools_web`
(nginx interne, reverse proxy vers l'API) et `docstools_watchtower` (mises
à jour automatiques, voir étape 5).

### Vérifier que l'API répond

Toujours depuis `/home/pi/docstools` (ou n'importe où, la commande cible
`localhost`) :

```bash
curl -sf http://localhost:8000/api/versions >/dev/null && echo OK
```

Un `OK` confirme que le conteneur `api` a démarré et répond.

---

## 4. Exposition publique (nginx + tunnel Cloudflare mutualisés)

Le reverse proxy nginx et le tunnel Cloudflare **ne sont pas propres à
DocsTools** : ils sont mutualisés sur le Pi, dans `/home/pi/infra/` (un
dossier séparé, hors de ce dépôt), et servent déjà d'autres sites (même
principe que `toolbox-prod`, `HikeWorld`, etc.).

```
/home/pi/infra/                 ← dossier séparé, pas ce dépôt
├── docker-compose.yml          #   nginx (reverse-proxy) + cloudflared
└── nginx/conf.d/
    ├── toolbox-prod.conf
    └── docstools.conf          ← fichier à créer, étape 4.1

/home/pi/docstools/              ← ce dépôt (étape 1)
├── docker-compose.yml
├── index.sqlite                 ← étape 2
└── docker/
    └── infra-nginx-docstools.conf.example   ← source de la copie, étape 4.1
```

`web` ([`docker-compose.yml`](../docker-compose.yml)) rejoint le réseau
Docker externe `proxy-net` (déjà créé par `infra/docker-compose.yml`, qui
doit déjà tourner) sous le nom de conteneur `docstools_web` — exactement
comme `toolbox_prod_web` pour `toolbox-prod`. Aucun port n'est publié sur
l'hôte : le nginx partagé atteint `web` directement par ce nom, sur ce
réseau.

### 4.1. Copier le vhost nginx

Départ : n'importe où (chemins absolus des deux côtés).

```bash
cp /home/pi/docstools/docker/infra-nginx-docstools.conf.example \
   /home/pi/infra/nginx/conf.d/docstools.conf
```

Ouvrir ensuite `/home/pi/infra/nginx/conf.d/docstools.conf` dans un
éditeur si le sous-domaine souhaité n'est pas `docstools.dorianvidal.com`
(ligne `server_name`) — sinon, rien à modifier, passer à l'étape suivante.

### 4.2. Recharger le nginx partagé

Départ : `/home/pi/infra` (le dossier de l'infra mutualisée, pas celui de
DocsTools).

```bash
cd /home/pi/infra
docker compose exec nginx nginx -s reload
```

### 4.3. Ajouter le hostname dans le tunnel Cloudflare

Dans le [dashboard Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
(navigateur, pas de commande sur le Pi) :

1. **Networks → Tunnels**, ouvrir le tunnel déjà utilisé par les autres
   sites du Pi.
2. Onglet **Public Hostname** → **Add a public hostname**.
3. Subdomain `docstools` (ou celui choisi à l'étape 4.1), domain
   `dorianvidal.com`.
4. Service : type `HTTP`, URL `reverse-proxy:80` — **la même cible que les
   routes existantes** des autres sites : c'est le nginx partagé que le
   tunnel connaît, pas chaque site individuellement. C'est nginx
   (`server_name`, étape 4.1) qui route ensuite vers le bon conteneur.
5. Enregistrer.

### 4.4. Vérifier

Depuis un réseau **différent** du réseau local (4G, VPN externe, etc.) —
pas depuis le Pi ni depuis le même Wi-Fi — ouvrir
`https://docstools.dorianvidal.com` (ou le sous-domaine choisi) et
confirmer qu'une recherche renvoie des résultats.

---

## 5. Déploiement automatique (watchtower)

Déjà démarré à l'étape 3 (`docker compose up -d` lance aussi
`watchtower`) — rien à faire de plus pour l'activer. Cette section
explique ce qu'il fait et comment le désactiver si besoin.

`watchtower` surveille les images
`ghcr.io/vidal-dorian/docstools-{api,web}:latest` toutes les 5 minutes et
redéploie `api`/`web` dès qu'une nouvelle version est publiée — donc, en
pratique, quelques minutes après chaque merge sur `main`. Il est scopé aux
seuls conteneurs portant le label
`com.centurylinklabs.watchtower.enable=true` (`api`, `web`) : il ne touche
pas aux autres sites du Pi ni à `infra/` (nginx, cloudflared).

**Visibilité des packages GHCR.** Par défaut, les packages publiés par
`docker-publish.yml` peuvent être privés selon les réglages du dépôt
GitHub. Pour que le Pi puisse les tirer sans gérer d'identifiants, les
rendre publics : sur GitHub, page du package (`docstools-api`, puis
`docstools-web`) → **Package settings** → **Change visibility** → **Public**.
Ces images ne contiennent que du code, aucune donnée (`index.sqlite` est
monté en volume, jamais copié dans l'image) : les rendre publiques
n'expose rien de sensible.

Si tu préfères les garder privées : sur le Pi,
`docker login ghcr.io -u <user>` (jeton `read:packages`), puis monter le
fichier de credentials généré (`~/.docker/config.json`) dans le service
`watchtower` du `docker-compose.yml` — voir la
[doc watchtower sur les registres privés](https://containrrr.dev/watchtower/private-registries/).

**Forcer une mise à jour immédiate** sans attendre le prochain sondage de
watchtower :

```bash
cd /home/pi/docstools
docker compose pull
docker compose up -d
```

---

## 6. Procédure de retour arrière

Voir [`specification.md` §4](specification.md#4-pipeline-dingestion),
« Mise en service ».

Suppose qu'un ancien index a été conservé lors d'un rebuild (étape 2,
`index.YYYY.sqlite`). En cas de problème avec l'index en service :

```bash
cd /home/pi/docstools
docker compose stop api
mv index.sqlite index.broken.sqlite   # à titre de conservation, optionnel
cp index.YYYY.sqlite index.sqlite     # remplacer YYYY par l'année voulue
docker compose start api
```

Pas de rechargement à chaud ni de swap atomique : quelques secondes
d'indisponibilité de `api` pendant l'opération, sans conséquence pour un
service mono-utilisateur rebuild ~1×/an (spec §4).
