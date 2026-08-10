"""Création du schéma SQLite de DocsTools (voir docs/specification.md, section 3).

Exécutable directement : `python -m ingest.schema [db_path]`
Idempotent : les tables existantes sont supprimées puis recréées.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = "index.sqlite"


def create_schema(db_path: str | Path) -> None:
    """Crée (ou recrée) le schéma DocsTools dans la base SQLite `db_path`."""
    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crée le schéma SQLite de DocsTools (idempotent).")
    parser.add_argument(
        "db_path",
        nargs="?",
        default=DEFAULT_DB_PATH,
        help=f"Chemin du fichier SQLite à créer (par défaut : {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()
    create_schema(args.db_path)
    print(f"Schéma créé dans {args.db_path}")


if __name__ == "__main__":
    main()
