import sqlite3
from pathlib import Path

import pytest

from api.search import build_match_query, search_groups, tokenize
from ingest.parser import load_type, parse_type
from ingest.schema import create_schema

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Même échantillon que tests/test_examples.py (5 types cœur du BCL).
SAMPLE_FIXTURES = [
    "System.DateTime.xml",
    "System.String.xml",
    "System.Math.xml",
    "System.Collections.Generic.List`1.xml",
    "System.Linq.Enumerable.xml",
]


def test_tokenize_lowercases_and_splits_on_non_word_characters():
    assert tokenize("Add Months, Date!") == ["add", "months", "date"]


def test_tokenize_empty_query_returns_no_tokens():
    assert tokenize("   ") == []


def test_build_match_query_joins_tokens_with_explicit_or():
    assert build_match_query("add months date") == '"add"* OR "months"* OR "date"*'


def test_build_match_query_never_lets_a_quote_reach_the_fts5_string():
    # tokenize() ne garde que des caractères \w : un guillemet dans la saisie
    # ne peut donc jamais casser la syntaxe `"tok"*` générée.
    assert build_match_query('foo"bar') == '"foo"* OR "bar"*'


def test_build_match_query_empty_for_empty_input():
    assert build_match_query("   ") == ""


@pytest.fixture(scope="module")
def sample_db_path(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("search") / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        for name in SAMPLE_FIXTURES:
            xml_text = (FIXTURES_DIR / name).read_text(encoding="utf-8")
            load_type(conn, parse_type(xml_text))
    finally:
        conn.close()
    return db_path


@pytest.fixture
def sample_conn(sample_db_path):
    conn = sqlite3.connect(sample_db_path)
    yield conn
    conn.close()


def _group_name(conn: sqlite3.Connection, group_id: int) -> str:
    return conn.execute(
        "SELECT name FROM member_group WHERE id = ?", (group_id,)
    ).fetchone()[0]


def test_add_months_date_ranks_add_months_first(sample_conn):
    hits = search_groups(sample_conn, "add months date")

    assert hits, "aucun résultat pour 'add months date'"
    assert _group_name(sample_conn, hits[0].group_id) == "AddMonths"


def test_cut_end_of_string_finds_at_least_one_candidate_via_or_mode(sample_conn):
    # Spec §5 : en ET implicite, 0 résultat ; en OU, des centaines de
    # candidats sur le corpus complet (~691). Ici, échantillon réduit, mais
    # au moins un candidat doit remonter (ex. EndsWith, Substring, Remove).
    hits = search_groups(sample_conn, "cut end of string")

    assert len(hits) >= 1


def test_and_mode_would_return_nothing_for_cut_end_of_string(sample_conn):
    # Démontre que l'ET implicite (requête FTS5 non transformée) échoue là où
    # le OU réussit — justifie pourquoi build_match_query() est nécessaire.
    and_query = "cut end of string"  # FTS5 : ET implicite entre les tokens
    rows = sample_conn.execute(
        "SELECT rowid FROM group_fts WHERE group_fts MATCH ?", (and_query,)
    ).fetchall()

    assert rows == []


def test_search_groups_returns_no_results_for_a_blank_query(sample_conn):
    assert search_groups(sample_conn, "   ") == []


def test_search_groups_respects_limit(sample_conn):
    hits = search_groups(sample_conn, "value", limit=3)
    assert len(hits) <= 3
