# Changelog

## [0.6.0](https://github.com/vidal-dorian/docstools/compare/docstools-v0.5.0...docstools-v0.6.0) (2026-08-11)


### Features

* **deploy:** dockerise l'API et le front (US-050) ([52395d6](https://github.com/vidal-dorian/docstools/commit/52395d6a8b5f6551fc2b48d0c32e99ad5af11847)), closes [#22](https://github.com/vidal-dorian/docstools/issues/22)


### Bug Fixes

* **deploy:** aligne le tunnel/nginx sur l'infra mutualisée réelle du Pi ([0c2e47c](https://github.com/vidal-dorian/docstools/commit/0c2e47c657516a34d606dcf476a7368b9988f482))


### Documentation

* **deploy:** procédure de déploiement et tunnel Cloudflare (US-052, US-053) ([dbfeac5](https://github.com/vidal-dorian/docstools/commit/dbfeac54741f1a97bf1d429866a75953a5fb0e21)), closes [#24](https://github.com/vidal-dorian/docstools/issues/24) [#25](https://github.com/vidal-dorian/docstools/issues/25)

## [0.5.0](https://github.com/vidal-dorian/docstools/compare/docstools-v0.4.0...docstools-v0.5.0) (2026-08-11)


### Features

* **api:** endpoint GET /api/group/{id} (US-022) ([98b2f3c](https://github.com/vidal-dorian/docstools/commit/98b2f3c2fac0d68c977c770058d2e6966b81c7e3)), closes [#12](https://github.com/vidal-dorian/docstools/issues/12)
* **api:** endpoint POST /api/search et GET /api/versions (US-021) ([afb5ad1](https://github.com/vidal-dorian/docstools/commit/afb5ad10ba7175ee656c5e1dadcf2f071419f05c)), closes [#11](https://github.com/vidal-dorian/docstools/issues/11)
* **api:** filtre de version côté /api/search (US-023) ([ac04505](https://github.com/vidal-dorian/docstools/commit/ac04505c94daa8a0f9a6e6be654cc03ea73a6b27)), closes [#13](https://github.com/vidal-dorian/docstools/issues/13)
* **api:** requête FTS5 en mode OU sur group_fts (US-020) ([e5087d0](https://github.com/vidal-dorian/docstools/commit/e5087d0883ae551fe7fbb3af0710cbeb3c2fcc76)), closes [#10](https://github.com/vidal-dorian/docstools/issues/10)
* **web:** panneau de détail au clic sur un résultat (US-032) ([be88957](https://github.com/vidal-dorian/docstools/commit/be88957f1e46046e9bf42c0471bfc877639da377)), closes [#16](https://github.com/vidal-dorian/docstools/issues/16)
* **web:** panneau de résultats avec recherche debouncée (US-030) ([2c12a38](https://github.com/vidal-dorian/docstools/commit/2c12a38564705224a6854cd0dd48abf57a3d43ae)), closes [#14](https://github.com/vidal-dorian/docstools/issues/14)
* **web:** sélecteur de version persistant (US-031) ([73aec73](https://github.com/vidal-dorian/docstools/commit/73aec737c344f9d9dc9dd96b5260a4a2eaf6478a)), closes [#15](https://github.com/vidal-dorian/docstools/issues/15)

## [0.4.0](https://github.com/vidal-dorian/docstools/compare/docstools-v0.3.0...docstools-v0.4.0) (2026-08-11)


### Features

* **ingest:** alimente group_fts et ajoute optimize_fts (US-016) ([b05e92e](https://github.com/vidal-dorian/docstools/commit/b05e92e4dd4061cfa0b92c3789f61f8ede94bde0)), closes [#9](https://github.com/vidal-dorian/docstools/issues/9)
* **ingest:** parse le corpus dotnet-api-docs complet (US-015) ([a9ec550](https://github.com/vidal-dorian/docstools/commit/a9ec55074deb5704d9ca372ea2c6fbe970a43b72)), closes [#8](https://github.com/vidal-dorian/docstools/issues/8)

## [0.3.0](https://github.com/vidal-dorian/docstools/compare/docstools-v0.2.0...docstools-v0.3.0) (2026-08-11)


### Features

* **ingest:** mesure la proportion d'exemples de code réellement inline ([6e4b935](https://github.com/vidal-dorian/docstools/commit/6e4b935bd6ffb8b3a3ad8bba117092174e29143b)), closes [#7](https://github.com/vidal-dorian/docstools/issues/7)
* **ingest:** résolution des versions via AssemblyInfo/FrameworkAlternate ([4e354f5](https://github.com/vidal-dorian/docstools/commit/4e354f554f008e729768d8a5bbb3ec9ee5fcd5e8)), closes [#5](https://github.com/vidal-dorian/docstools/issues/5)

## [0.2.0](https://github.com/vidal-dorian/docstools/compare/docstools-v0.1.0...docstools-v0.2.0) (2026-08-10)


### Features

* **ci:** met en place la convention Conventional Commits ([3881d4e](https://github.com/vidal-dorian/docstools/commit/3881d4e0d53dbf23fe81dc82de19e7d2b84585f2))
* **ci:** met en place la convention Conventional Commits ([2668178](https://github.com/vidal-dorian/docstools/commit/266817858bc889df1947e4220f9525b545dc2b10)), closes [#30](https://github.com/vidal-dorian/docstools/issues/30)
* **ci:** met en place release-please pour l'automatisation des releases ([f3d456e](https://github.com/vidal-dorian/docstools/commit/f3d456e24e8160c09d489795f548286912faa175))
* **ci:** met en place release-please pour l'automatisation des releases ([45dcbf7](https://github.com/vidal-dorian/docstools/commit/45dcbf778c9ad839a0c79acb975289d8d1458bd5)), closes [#28](https://github.com/vidal-dorian/docstools/issues/28)
* **ingest:** crée le schéma SQLite (US-010) ([4fdb010](https://github.com/vidal-dorian/docstools/commit/4fdb0101146d630c252bf5db4cb55abd4ff5d177))
* **ingest:** crée le schéma SQLite (US-010) ([d1b95a8](https://github.com/vidal-dorian/docstools/commit/d1b95a8b80d081efb327d138c4bd8a466cc93519)), closes [#3](https://github.com/vidal-dorian/docstools/issues/3)
* structure le dépôt (US-001) ([e8613a2](https://github.com/vidal-dorian/docstools/commit/e8613a2902cb0a088a99711df01289d0ef12534e))
* structure le dépôt (US-001) ([9f94859](https://github.com/vidal-dorian/docstools/commit/9f948595a59d68f5ce7db7d999c0e50eac862379)), closes [#1](https://github.com/vidal-dorian/docstools/issues/1)


### Bug Fixes

* **test:** ajoute pythonpath pour que pytest trouve le package ingest en CI ([abac710](https://github.com/vidal-dorian/docstools/commit/abac710b82991cad83cb2116ba5f458ef6389534))


### Documentation

* documente la stratégie de branches et la protection de main ([f639429](https://github.com/vidal-dorian/docstools/commit/f63942913b4b14627e8104465fd648f32350bdd8))
* documente la stratégie de branches et la protection de main ([678cb27](https://github.com/vidal-dorian/docstools/commit/678cb274801f5760c137a55212457e0e6f46eca3)), closes [#31](https://github.com/vidal-dorian/docstools/issues/31)

## Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.
Ce changelog est généré automatiquement par [release-please](https://github.com/googleapis/release-please).
