# Déploiement

Procédure pour mettre à jour et exposer publiquement le service DocsTools
sur le Raspberry Pi. Voir [`docs/specification.md`](specification.md),
section 8, pour l'architecture générale.

**Explicitement hors périmètre :**
- **Pas de déploiement automatique déclenché depuis GitHub.** Le pipeline
  CI ([`docker-publish.yml`](../.github/workflows/docker-publish.yml))
  construit et publie les images sur GitHub Container Registry à chaque
  merge sur `main`, mais rien ne les déploie automatiquement sur le Pi —
  cette étape reste manuelle, décrite ci-dessous.
- **Le Pi n'est pas exposé en SSH.** Toute opération sur le Pi (mise à
  jour, configuration) se fait en local (clavier/écran, ou accès
  physique/console de confiance), jamais via un accès distant automatisé.

---

## Mise à jour du service

À exécuter directement sur le Pi, dans le dossier du projet.

```bash
docker compose pull
docker compose up -d
```

### Vérification que l'API répond

```bash
curl -sf http://localhost:8000/api/versions >/dev/null && echo OK
```

Un `OK` confirme que le conteneur `api` a démarré et répond. Vérifier
ensuite depuis un navigateur que la recherche fonctionne réellement
(taper une requête, voir des résultats s'afficher).

---

## Exposition publique (nginx + tunnel Cloudflare mutualisés)

Le reverse proxy nginx et le tunnel Cloudflare **ne sont pas propres à
DocsTools** : ils sont mutualisés sur le Pi, dans `/home/pi/infra/`
(hors de ce dépôt), et servent déjà d'autres sites (même principe que
`toolbox-prod`, `HikeWorld`, etc.). DocsTools ne fait que s'y brancher :

```
/home/pi/infra/
├── docker-compose.yml       # nginx (reverse-proxy) + cloudflared, réseau proxy-net
└── nginx/conf.d/
    ├── toolbox-prod.conf
    └── docstools.conf       # ← à ajouter, voir ci-dessous

/home/pi/docstools/           # ce dépôt, cloné sur le Pi
└── docker-compose.yml        # services api + web, web rejoint proxy-net
```

`web` ([`docker-compose.yml`](../docker-compose.yml)) rejoint le réseau
externe `proxy-net` (créé par `infra/docker-compose.yml`, déjà en cours
d'exécution) sous le nom `docstools_web`, exactement comme
`toolbox_prod_web` pour `toolbox-prod`. Aucun port n'est publié sur
l'hôte : le nginx partagé atteint `web` directement par son nom de
conteneur sur ce réseau.

### Configuration initiale (une seule fois)

1. Copier [`docker/infra-nginx-docstools.conf.example`](../docker/infra-nginx-docstools.conf.example)
   vers `/home/pi/infra/nginx/conf.d/docstools.conf` (ajuster le
   sous-domaine si besoin — `docstools.dorianvidal.com` par défaut).
2. Recharger le nginx partagé :
   ```bash
   cd /home/pi/infra && docker compose exec nginx nginx -s reload
   ```
3. Dans le [dashboard Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
   → **Networks → Tunnels**, ouvrir le tunnel déjà utilisé par les autres
   sites → onglet **Public Hostname** → ajouter un hostname
   `docstools.dorianvidal.com`, type `HTTP`, service
   `http://reverse-proxy:80` (même cible que les routes existantes — c'est
   nginx, pas chaque site, que le tunnel connaît ; nginx route ensuite par
   `server_name`).
4. `docker compose up -d` dans `/home/pi/docstools/` (démarre `api` et
   `web`, les rattache à `proxy-net`).

### Vérification (US-053)

Depuis un réseau **différent** du réseau local (4G, VPN externe, etc.),
ouvrir `https://docstools.dorianvidal.com` (ou le sous-domaine choisi) et
confirmer qu'une recherche renvoie des résultats.

---

## Procédure de retour arrière

Voir [`specification.md` §4](specification.md#4-pipeline-dingestion),
« Mise en service ».

L'index précédent est conservé sous `index.YYYY.sqlite` à chaque build. En
cas de problème avec l'index en service :

```bash
docker compose stop api
mv index.sqlite index.broken.sqlite   # à titre de conservation, optionnel
cp index.YYYY.sqlite index.sqlite     # remplacer YYYY par l'année voulue
docker compose start api
```

Pas de rechargement à chaud ni de swap atomique : quelques secondes
d'indisponibilité de `api` pendant l'opération, sans conséquence pour un
service mono-utilisateur rebuild ~1×/an (spec §4).
