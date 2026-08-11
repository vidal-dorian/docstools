# DocsTools — Spécification technique

Document de conception destiné à servir de base d'implémentation.
Statut : conception validée, implémentation non commencée.

---

## 1. Objectif

Moteur de recherche d'API par **intention**, pas par navigation.

L'utilisateur sait ce qu'il veut faire (« ajouter un mois à une date »), pas
comment ça s'appelle. Les documentations officielles supposent l'inverse :
elles sont organisées par arborescence de types, ce qui impose de connaître
la réponse pour trouver la question.

DocsTools inverse ce rapport : on tape une intention, on obtient une méthode.

### Différenciateur

Un LLM répond déjà bien à ce genre de question. Ce que DocsTools apporte en
plus, et qui justifie de le construire :

**La garantie de version.** Un LLM hallucine des API .NET 8 quand on est bloqué
en Framework 4.x en entreprise. Un index construit à partir de la documentation
officielle indique de façon vérifiable si une méthode existe dans la version
ciblée.

C'est le cœur du produit. Tout le reste est secondaire.

### Non-objectifs

Explicitement hors périmètre — à ne pas implémenter :

- Génération de code, explication, assistant conversationnel
- Mode hors-ligne, index téléchargé côté client
- Historique de recherche, favoris, comptes utilisateurs
- Ajout de sources de documentation depuis l'interface
- Multi-utilisateurs, authentification

### Périmètre v1

**C# / .NET uniquement.**

Java, HTML, CSS, JS viendront plus tard. Chaque source demande un parser
dédié écrit à la main : il n'existe aucun format pivot commun entre la
documentation .NET (XML ECMA), MDN (Markdown) et la Javadoc (HTML généré).
Tenter les cinq d'un coup garantit un projet abandonné à 40 %.

L'architecture doit rester **multi-source dès le départ** (table `source`,
parsers isolés), mais un seul parser est écrit en v1.

---

## 2. Architecture

Tout tourne sur le Raspberry Pi 5 (8 Go). Deux modes d'exécution nettement
séparés, qui ne tournent jamais en même temps.

```
┌─────────────────────── Raspberry Pi 5 ────────────────────────┐
│                                                                │
│  MODE BUILD (manuel, ~1×/AN, la nuit)                          │
│    git clone dotnet-api-docs                                   │
│      → parse ECMAXML                                           │
│      → calcul des embeddings (onnxruntime, int8)               │
│      → index.new.sqlite  →  validation  →  remplacement à froid│
│                                                                │
│  MODE SERVICE (permanent)                                      │
│    Docker : FastAPI (lecture seule sur index.sqlite)           │
│    nginx  → cloudflared                                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              ↕
                     Navigateur (transformers.js)
                     embedding de la requête uniquement
```

### Contraintes matérielles

| Contrainte | Exigence |
|---|---|
| Cadence de rebuild | **~1 fois par an.** Les documentations d'API n'évoluent pas assez vite pour justifier davantage. |
| Stockage | Le stockage local du Pi suffit, **carte SD comprise**. Une indexation complète écrit quelques Go ; à raison d'un build annuel, l'usure est négligeable. Un SSD accélérerait le build, mais n'est pas requis. |
| Build | Tâche de fond, `nice -n 19`, lancée via `tmux` ou `nohup` — plusieurs heures. Jamais pendant les heures d'usage. |
| RAM | 8 Go suffisent. Le build doit committer par lots pour ne pas tout garder en mémoire. |
| Architecture | `aarch64` — vérifié. Condition nécessaire aux wheels onnxruntime. |
| Stockage réseau | **Interdit pour l'index en service.** L'index vit toujours sur le stockage local de la machine qui sert. Motifs : SQLite est déconseillé sur montage NFS/SMB (verrouillage peu fiable), et la charge FTS5 + lecture de BLOBs est de l'I/O aléatoire, où un HDD est plus lent qu'une carte SD. |

### Répartition des calculs

| Opération | Où | Justification |
|---|---|---|
| Parsing XML | Pi (build) | Calcul global, fait une fois |
| Embeddings du corpus | Pi (build) | Idem — jamais côté client, ce serait refait à chaque navigateur |
| Embedding de la requête | **Navigateur** | ~10 tokens, intrinsèquement par-utilisateur |
| BM25 + rerank | Pi (service) | Les vecteurs du corpus restent serveur |

Le client envoie le vecteur de requête (384 floats) au serveur. Aucun vecteur
de corpus ne transite sur le réseau.

**Compromis assumé :** le navigateur doit charger le modèle ONNX quantifié
(~30 Mo) au premier accès, mis en cache ensuite. Premier chargement lent,
pénible en 4G. L'alternative (embedding serveur) aurait évité ça au prix
d'une dépendance ML dans le conteneur. Choix retenu : client.

**Risque connu :** transformers.js pose régulièrement des problèmes de
configuration TS/ESM. Prévoir du temps dessus, et un repli propre si le modèle
ne charge pas (voir §6, mode dégradé).

---

## 3. Modèle de données

### Décision structurante : groupe vs surcharge

L'interface demande **une ligne par méthode**, les surcharges apparaissant
seulement au clic. L'unité de recherche est donc le **groupe** (`DateTime.AddMonths`),
pas la surcharge (`AddMonths(int)`).

Conséquence directe : **on embedde au niveau du groupe, pas de la surcharge.**
Les surcharges partagent le même résumé — les vectoriser séparément multiplierait
le coût de build pour produire des vecteurs quasi identiques et polluerait le
classement avec des doublons.

```
source            dotnet
 └─ version       net-8.0, netframework-4.x, ...
 └─ type          System.DateTime
     └─ member_group   AddMonths          ← unité de RECHERCHE (FTS5 + vecteur)
         └─ overload   AddMonths(int)     ← unité d'AFFICHAGE détaillé
```

### Schéma

```sql
CREATE TABLE source (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE,          -- 'dotnet'
    label TEXT,
    repo TEXT,
    built_at TEXT
);

CREATE TABLE version (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES source(id),
    moniker TEXT,             -- 'net-8.0', 'netframework-4.x'
    label TEXT,               -- '.NET 8'
    family TEXT,              -- netframework | netcore | netstandard
    sort_order INTEGER,
    UNIQUE (source_id, moniker)
);

CREATE TABLE type (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES source(id),
    namespace TEXT,
    name TEXT,                -- 'DateTime'
    full_name TEXT,           -- 'System.DateTime'
    kind TEXT,                -- class | struct | enum | interface | delegate
    summary TEXT,
    doc_url TEXT,
    UNIQUE (source_id, full_name)
);

-- Unité de recherche
CREATE TABLE member_group (
    id INTEGER PRIMARY KEY,
    type_id INTEGER REFERENCES type(id),
    name TEXT,                -- 'AddMonths'
    kind TEXT,                -- Method | Property | Field | Constructor | Event
    summary TEXT,             -- résumé de la 1re surcharge documentée
    is_static INTEGER,
    overload_count INTEGER,
    doc_url TEXT,
    embedding BLOB,           -- 384 × int8 + scale float32
    version_confidence TEXT,  -- explicit | inferred | unknown
    UNIQUE (type_id, name, kind)
);

-- Unité d'affichage
CREATE TABLE overload (
    id INTEGER PRIMARY KEY,
    group_id INTEGER REFERENCES member_group(id),
    signature TEXT,           -- 'public DateTime AddMonths (int months);'
    doc_id TEXT,              -- 'M:System.DateTime.AddMonths(System.Int32)'
    summary TEXT,
    returns_doc TEXT,
    return_type TEXT,
    params_json TEXT,         -- [{name, type, doc}]
    exceptions_json TEXT,     -- [{type, doc}]
    remarks_md TEXT,          -- peut être NULL
    example_code TEXT,        -- peut être NULL — voir §4, risque
    doc_url TEXT,
    ordinal INTEGER
);

-- Couverture de version, portée par la surcharge (deux surcharges d'une
-- même méthode peuvent avoir des disponibilités différentes)
CREATE TABLE overload_version (
    overload_id INTEGER REFERENCES overload(id),
    version_id INTEGER REFERENCES version(id),
    status TEXT DEFAULT 'present',   -- present | deprecated
    PRIMARY KEY (overload_id, version_id)
) WITHOUT ROWID;

-- Index plein texte, mode contentless : rowid == member_group.id
CREATE VIRTUAL TABLE group_fts USING fts5(
    name, type_name, summary, params,
    content='',
    tokenize = 'porter unicode61 remove_diacritics 2'
);
```

`params_json` reste en JSON plutôt qu'en table normalisée : les paramètres
sont affichés, jamais requêtés indépendamment. Les normaliser coûterait une
jointure pour aucun bénéfice.

---

## 4. Pipeline d'ingestion

Source : [`dotnet/dotnet-api-docs`](https://github.com/dotnet/dotnet-api-docs)
Format : ECMAXML — [guide](https://github.com/dotnet/docs/blob/main/styleguide/ecmaxml-guide.md)

### Étapes

1. `git clone --depth 1` du dépôt
2. Parcours de `xml/<Namespace>/<Type>.xml` (ignorer `index.xml`, `ns-*.xml`)
3. Parse `<Type>` → table `type`
4. Parse chaque `<Member>` → `overload`, regroupés par `MemberName` + `MemberType`
5. Résolution des versions (voir ci-dessous)
6. Alimentation de `group_fts`
7. Embeddings par lots → `member_group.embedding`
8. `optimize` FTS5, puis `VACUUM`
9. Validation, puis mise en service (voir ci-dessous)

Le clone du dépôt est du stockage froid : il peut être supprimé après le build
et refait l'année suivante.

### Extraction

Éléments à récupérer par membre :

- `<MemberSignature Language="C#">` → signature. Ignorer les membres sans
  signature C#.
- `<MemberSignature Language="DocId">` → identifiant canonique, sert à
  construire l'URL learn.microsoft.
- `<MemberType>` → kind
- `<Parameters>/<Parameter>` croisé avec `<Docs>/<param>` → `params_json`
- `<Docs>/<summary>`, `<returns>`, `<exception>`
- `<Docs>/<remarks>/<format type="text/markdown">` → `remarks_md`

Le texte des `<summary>` contient des balises `<see cref="T:System.DateTime"/>`
et `<paramref name="x"/>`. Elles doivent être **aplaties vers leur cible**
(`DateTime`, `x`) et non supprimées : ce texte alimente FTS5 et les embeddings,
il doit rester dense en mots utiles.

### ✅ Risque mesuré (US-014) : les exemples de code

Les blocs `remarks` en Markdown référencent souvent des exemples via une
syntaxe d'inclusion — l'actuelle `:::code language="csharp"
source="~/snippets/...":::` (DocFX), ou l'ancienne `[!code-csharp[...](~/samples/...)]`
— pointant vers des fichiers **absents du dépôt de documentation**.

**Mesuré** sur l'échantillon de 793 membres (DateTime, String, Math, List\<T\>,
Enumerable — voir §11) : **0 % des sections « Examples » contiennent du code
réellement inline.** 49,8 % pointent uniquement vers une inclusion externe
non résolue, 50,2 % n'ont pas de section « Examples » du tout.

**Décision actée :** l'interface n'affiche jamais de section « exemple »
embarquée — `example_code` reste `NULL` en base. Un lien vers la page
learn.microsoft.com correspondante est affiché à la place (US-033).

### Résolution des versions

**Constat mesuré** sur 793 membres (DateTime, String, Math, List\<T\>, Enumerable) :
l'attribut `FrameworkAlternate` n'est présent que sur **2 membres**. Il ne peut
pas servir de mécanisme principal.

Le signal exploitable est `<AssemblyInfo>` : `AssemblyName` + liste
d'`AssemblyVersion`. Mapping à établir :

| AssemblyName | AssemblyVersion | Moniker |
|---|---|---|
| mscorlib | 1.0.5000.0 | netframework-1.1 |
| mscorlib | 2.0.x | netframework-2.0 |
| mscorlib | 4.0.0.0 | netframework-4.x |
| netstandard | 2.0 / 2.1 | netstandard-2.0 / 2.1 |
| System.Runtime | 4.x | netcore-legacy |
| System.Runtime | ≥ 5.0 | net-5.0 … net-11.0 |

`version_confidence` :

- `explicit` — `FrameworkAlternate` présent (rare)
- `inferred` — déduit des `AssemblyInfo` (cas très majoritaire)
- `unknown` — aucun signal → **badge d'avertissement dans l'UI**

**Limite assumée :** `mscorlib 4.0.0.0` couvre .NET Framework 4.0 à 4.8 sans
distinction. La granularité maximale côté Framework est donc `4.x`. Une API
ajoutée en 4.6.1 ne sera pas détectée comme telle. Suffisant pour l'usage visé
(Framework vs .NET moderne), mais à documenter dans l'interface.

**Règle de repli :** un membre sans information de version exploitable est
marqué présent sur **toutes** les versions, avec `confidence = unknown`.
Mieux vaut un résultat annoté « non vérifié » qu'un résultat manquant.

### Embeddings

- Modèle : `Xenova/multilingual-e5-small` — 384 dimensions
- Le modèle e5 exige des préfixes : `passage: ` à l'indexation,
  `query: ` à la recherche. **Les omettre dégrade nettement la qualité.**
- Texte embeddé : `{Type}.{Nom} — {summary}` (niveau groupe)
- Quantification int8 + facteur d'échelle stocké avec le vecteur
- Traitement par lots, `nice -n 19`

### Mise en service

Le build écrit `index.new.sqlite`, à côté de l'index en service qui reste
intact pendant toute l'opération.

**Validation obligatoire avant remplacement** — ne pas la sacrifier, c'est
elle qui empêche de mettre en service un index cassé par une régression du
parser :

- nombre de types et de groupes non nul et cohérent avec le build précédent
- requête témoin : `add months date` doit remonter `DateTime.AddMonths`
- taux de `version_confidence = 'unknown'` dans une fourchette attendue

Puis, simplement : **arrêt du conteneur, remplacement du fichier, redémarrage.**

Pas de rechargement à chaud, pas de swap atomique, pas de signal à l'API.
Ce mécanisme se justifiait pour un rebuild fréquent ; à raison d'un build par
an sur un service mono-utilisateur, trente secondes d'indisponibilité sont
sans conséquence et la complexité ne se paie pas.

L'index précédent est conservé sous `index.YYYY.sqlite` : le retour arrière
consiste à remettre l'ancien fichier en place et redémarrer.

---

## 5. Algorithme de recherche

Recherche hybride en deux étages.

### Étage 1 — BM25 (FTS5)

```
requête → tokenisation → "tok1"* OR "tok2"* OR ... → top 150 groupes
```

**Le OU est impératif.** FTS5 applique un ET implicite entre les termes, ce qui
renvoie zéro résultat dès qu'un mot de la question est absent de la
documentation. Comportement mesuré :

| Requête | ET implicite | OU |
|---|---|---|
| `add months date` | AddMonths ✅ | AddMonths ✅ |
| `cut end of string` | 0 résultat ❌ | 691 candidats |

Pondération `bm25()` : nom ≫ nom du type > résumé > paramètres.
Point de départ suggéré : `bm25(group_fts, 8.0, 3.0, 1.0, 0.5)`, à ajuster.

### Étage 2 — Rerank vectoriel

Sur les 150 candidats **uniquement**.

**Conséquence importante : aucun index vectoriel n'est nécessaire.** Ni
sqlite-vec, ni FAISS, ni Qdrant. On lit 150 BLOBs et on fait un produit
scalaire numpy. Ne pas ajouter de dépendance ici.

Fusion des deux scores par **Reciprocal Rank Fusion**, plus robuste qu'une
somme pondérée car elle ne demande pas de normaliser deux échelles hétérogènes :

```
score = 1/(60 + rang_bm25) + 1/(60 + rang_vecteur)
```

### Ce que le rerank doit corriger

Cas mesuré, `"cut end of string"` : BM25 seul classe `EndsWith` en tête alors
que la réponse attendue est `Substring` ou `Remove`. Aucun mot commun avec la
documentation — c'est exactement le périmètre du vectoriel.

### Filtre de version

Appliqué **après** le rerank, par jointure sur `overload_version`.
Un groupe est retenu si au moins une de ses surcharges existe dans la version
sélectionnée, ou si `version_confidence = 'unknown'`.

Appliquer le filtre avant le rerank fausserait le classement en réduisant le
vivier de candidats.

### Mode dégradé

Si le client n'envoie pas de vecteur (modèle non chargé, échec réseau),
l'API répond avec le classement BM25 seul et signale `"reranked": false`.
**La recherche ne doit jamais échouer à cause du modèle.**

---

## 6. API

`GET /api/versions` → liste des versions disponibles, pour le sélecteur.

`POST /api/search`

```jsonc
// requête
{
  "q": "add months to a date",
  "vector": [0.12, -0.04, ...],   // 384 floats, optionnel
  "version": "netframework-4.x",  // optionnel
  "limit": 20
}

// réponse
{
  "reranked": true,
  "results": [{
    "group_id": 4821,
    "name": "AddMonths",
    "type": "DateTime",
    "namespace": "System",
    "kind": "Method",
    "is_static": false,
    "summary": "Returns a new DateTime that adds the specified number of months...",
    "overload_count": 1,
    "signature_preview": "public DateTime AddMonths (int months);",
    "version_confidence": "inferred",
    "available_in_selected": true
  }]
}
```

`GET /api/group/{id}` → détail complet : toutes les surcharges avec signature,
paramètres typés et documentés, valeur de retour, exceptions, remarks, exemple
si disponible, couverture de version par surcharge, lien learn.microsoft.

Cette séparation liste/détail est délibérée : la liste doit rester légère,
le détail n'est chargé qu'au clic.

---

## 7. Interface

Deux panneaux.

**Gauche — résultats**
Barre de recherche, sélecteur de version persistant, liste des méthodes.
Une ligne = un groupe : `DateTime.AddMonths`, kind, résumé tronqué, badge
version si `unknown`, indicateur du nombre de surcharges.

**Droite — détail**
Signature complète par surcharge, paramètres (nom, type, description),
valeur de retour, exceptions, remarks, exemple de code si disponible,
tableau de disponibilité par version, lien vers la documentation officielle.

### Persistance

Le filtre de version est un **réglage persistant** (`localStorage`), pas un
filtre par requête. On ne change pas de contexte dix fois par jour : on est
au bureau ou à la maison.

### Badges

- `version_confidence = 'unknown'` → badge d'avertissement explicite,
  invitant à vérifier manuellement sur learn.microsoft.com
- Méthode absente de la version sélectionnée → grisée, non masquée

### Modèle côté client

transformers.js, ONNX quantifié, en **Web Worker** — sinon l'inférence bloque
l'interface. Indicateur de chargement au premier accès. Si le chargement échoue,
bascule silencieuse en mode dégradé BM25.

---

## 8. Déploiement

Aligné sur l'infrastructure existante : Docker, nginx en reverse proxy,
Cloudflare Tunnel.

```
docker compose
  ├── api      FastAPI + uvicorn, monte index.sqlite en lecture seule
  └── web      statique, servi par nginx

Build : script hors compose, lancé manuellement en SSH (~1×/an)
```

L'API ouvre SQLite en lecture seule (`file:...?mode=ro`) avec
`PRAGMA query_only=1`. Le service ne doit structurellement pas pouvoir
corrompre l'index.

Pas de base en écriture : ni historique, ni favoris, ni comptes.

**Tout reste sur le Pi 5.** Aucun stockage réseau n'intervient, ni pour le
build, ni pour le service, ni pour l'archive. Le volume Docker de l'index est
un chemin local.

---

## 9. Ordre d'implémentation

1. Parser ECMAXML → SQLite, sans embeddings. Validation sur `System.DateTime`.
2. FTS5 + BM25 + API `/search` en mode dégradé. **À ce stade, c'est déjà utilisable.**
3. Interface deux panneaux.
4. Embeddings au build + rerank.
5. Modèle côté client.
6. Docker, nginx, tunnel.

Les étapes 1 à 3 donnent un outil fonctionnel. Ne pas commencer par le
vectoriel : c'est la partie la plus fragile, et la moins utile tant que le
reste ne tourne pas.

**Recommandation :** utiliser l'outil pendant deux semaines après l'étape 3 en
consignant les requêtes qui échouent. Ce corpus devient le jeu de test de
l'étape 4 — sans lui, impossible de savoir si le rerank améliore réellement
quelque chose.

La cadence annuelle rend cet ordre encore plus confortable : entre l'étape 3
et l'étape 4, l'index reste valide, il n'y a rien à régénérer.

---

## 10. Risques

| Risque | Impact | Traitement |
|---|---|---|
| Exemples de code non résolus | Section détail vide | Vérifier tôt, dégrader vers un lien |
| Mapping assembly → moniker incomplet | Versions fausses | Valider sur corpus complet, pas 5 types |
| transformers.js / ESM | Rerank client inopérant | Mode dégradé obligatoire dès le départ |
| Durée du build sur Pi | Plusieurs heures | Acceptable à raison d'1×/an. Lancer via `tmux`/`nohup`, la nuit. L'index en service reste intact pendant le build. |
| Index de remplacement cassé | Service dégradé | Validation avant remplacement + conservation de `index.YYYY.sqlite` pour retour arrière |
| Taille de l'index | RAM / disque | À mesurer après le premier build complet |
| Qualité des embeddings | Rerank inutile | Les résumés Microsoft ne ressemblent pas à une question formulée par un humain. Si l'écart est trop grand, envisager en v2 la génération de phrases d'intention par LLM, limitée aux types les plus courants. |

---

## 11. Chiffres à mesurer

Aucune décision ne doit être prise sur ces points avant mesure :

- Nombre de types et de groupes après build complet
- Répartition `explicit` / `inferred` / `unknown`
- Taille de l'index avec et sans vecteurs
- Durée du build sur le Pi 5
- ~~Proportion de surcharges avec exemple de code inline~~ — **mesuré (US-014) :
  0 % sur 793 membres échantillonnés (DateTime, String, Math, List\<T\>,
  Enumerable) ; 49,8 % inclusion externe non résolue, 50,2 % sans section
  Examples. Voir §4, décision actée.**
- Latence de l'embedding client au premier chargement et ensuite

---

## Sources

- [dotnet/dotnet-api-docs](https://github.com/dotnet/dotnet-api-docs)
- [Guide ECMAXML](https://github.com/dotnet/docs/blob/main/styleguide/ecmaxml-guide.md)
- [SQLite FTS5](https://sqlite.org/fts5.html) — `content=''`, `bm25()`
- [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) — préfixes `query:` / `passage:`
- [transformers.js](https://huggingface.co/docs/transformers.js)
