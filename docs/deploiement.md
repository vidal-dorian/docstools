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

## Configuration initiale du tunnel Cloudflare (une seule fois)

Le `web` (nginx, reverse proxy devant `api` — voir
[`docker/nginx.conf`](../docker/nginx.conf)) n'est pas exposé directement :
aucun port n'est publié sur l'hôte pour `api` ni pour `web`
([`docker-compose.yml`](../docker-compose.yml)). Le seul point d'entrée
public est le conteneur `cloudflared`, qui établit un tunnel sortant vers
Cloudflare — pas besoin d'ouvrir de port sur la box.

1. Dans le [dashboard Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
   → **Networks → Tunnels → Create a tunnel** (type *Cloudflared*).
2. Nommer le tunnel (ex. `docstools`), choisir **Docker** comme méthode
   d'installation : Cloudflare affiche une commande contenant un token —
   copier uniquement la valeur du token (après `--token`).
3. Créer un fichier `.env` à la racine du projet sur le Pi (jamais commité,
   voir `.env.example`) :
   ```
   CLOUDFLARE_TUNNEL_TOKEN=<le token copié à l'étape 2>
   ```
4. Toujours dans le dashboard, onglet **Public Hostname** du tunnel :
   ajouter un hostname sur un sous-domaine de `dorianvidal.com`
   (ex. `docstools.dorianvidal.com`), type `HTTP`, service pointant vers
   `web:80` (nom du service Docker Compose, résolu sur le réseau interne
   `docstools_default`).
5. `docker compose up -d` (relit `.env`, démarre `cloudflared`).

### Vérification (US-053)

Depuis un réseau **différent** du réseau local (4G, VPN externe, etc.),
ouvrir `https://<sous-domaine choisi>.dorianvidal.com` et confirmer qu'une
recherche renvoie des résultats.

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
