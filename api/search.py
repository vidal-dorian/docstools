"""Requête FTS5 en mode OU sur `group_fts` (US-020).

Voir docs/specification.md, section 5, étage 1 — BM25 (FTS5) :

    requête → tokenisation → "tok1"* OR "tok2"* OR ... → top N groupes

**Le OU est impératif.** FTS5 applique un ET implicite entre les termes
d'une requête `MATCH`, ce qui renvoie zéro résultat dès qu'un mot de la
question est absent de la documentation (`cut end of string` → 0 résultat
en ET, ~691 candidats en OU sur le corpus complet). La tokenisation et
l'assemblage en OU se font donc côté application, pas en confiant la
chaîne brute de l'utilisateur à FTS5.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

DEFAULT_LIMIT = 150

# bm25(group_fts, ...) : nom ≫ nom du type > résumé > paramètres (spec §5).
# L'ordre des poids suit celui des colonnes de group_fts (name, type_name,
# summary, params) déclarées dans ingest/schema.sql.
BM25_WEIGHTS = (8.0, 3.0, 1.0, 0.5)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(query: str) -> list[str]:
    """Découpe une requête utilisateur en tokens de recherche, en minuscules."""
    return _TOKEN_RE.findall(query.lower())


def build_match_query(query: str) -> str:
    """Assemble les tokens en requête FTS5 `"tok1"* OR "tok2"* OR ...`.

    Chaque token est un préfixe (`*`) plutôt qu'une correspondance exacte,
    pour tolérer les formes fléchies (`add` retrouve aussi `adds`, `added`).
    Chaîne vide si la requête ne contient aucun token exploitable.
    """
    tokens = tokenize(query)
    if not tokens:
        return ""
    # tokenize() ne produit que des caractères \w : jamais de guillemet à
    # échapper dans la chaîne FTS5 résultante.
    return " OR ".join(f'"{token}"*' for token in tokens)


@dataclass
class SearchHit:
    group_id: int
    score: float  # bm25() — plus petit (plus négatif) = plus pertinent


def search_groups(
    conn: sqlite3.Connection, query: str, limit: int = DEFAULT_LIMIT
) -> list[SearchHit]:
    """Recherche BM25 en mode OU sur `group_fts`. Résultats triés du plus au
    moins pertinent (`bm25()` croissant : les valeurs sont négatives)."""
    match_query = build_match_query(query)
    if not match_query:
        return []

    rows = conn.execute(
        f"""
        SELECT group_fts.rowid, bm25(group_fts, {", ".join(map(str, BM25_WEIGHTS))})
        FROM group_fts
        WHERE group_fts MATCH ?
        ORDER BY 2
        LIMIT ?
        """,
        (match_query, limit),
    ).fetchall()
    return [SearchHit(group_id=row[0], score=row[1]) for row in rows]
