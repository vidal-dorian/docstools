import sqlite3

from ingest.schema import create_schema

EXPECTED_TABLES = {
    "source",
    "version",
    "type",
    "member_group",
    "overload",
    "overload_version",
    "group_fts",
}


def test_create_schema_creates_all_expected_tables(tmp_path):
    db_path = tmp_path / "index.sqlite"

    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table')"
        ).fetchall()
    finally:
        conn.close()

    table_names = {row[0] for row in rows}
    assert EXPECTED_TABLES <= table_names


def test_create_schema_produces_an_empty_database(tmp_path):
    db_path = tmp_path / "index.sqlite"

    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        for table in ("source", "version", "type", "member_group", "overload"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0
    finally:
        conn.close()


def test_create_schema_is_idempotent(tmp_path):
    db_path = tmp_path / "index.sqlite"

    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO source (key, label) VALUES ('dotnet', '.NET')"
    )
    conn.commit()
    conn.close()

    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM source").fetchone()[0]
    finally:
        conn.close()
    assert count == 0
