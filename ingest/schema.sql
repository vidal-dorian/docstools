-- Schéma SQLite de DocsTools — voir docs/specification.md, section 3.
-- Idempotent : les tables existantes sont supprimées avant recréation.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS group_fts;
DROP TABLE IF EXISTS overload_version;
DROP TABLE IF EXISTS overload;
DROP TABLE IF EXISTS member_group;
DROP TABLE IF EXISTS type;
DROP TABLE IF EXISTS version;
DROP TABLE IF EXISTS source;

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
    example_code TEXT,        -- peut être NULL — voir spec §4, risque
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
