# Image de service pour le front statique DocsTools (US-050).
# nginx sert web/ tel quel et reverse-proxie /api/ vers le service `api`
# (spec §8) — même origine, pas de CORS à gérer côté navigateur.

FROM nginx:alpine

COPY web/index.html web/app.js web/style.css web/markdown.js /usr/share/nginx/html/
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
