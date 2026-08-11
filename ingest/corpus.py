"""Parcours complet du corpus `dotnet-api-docs` → base DocsTools (US-015).

Voir docs/specification.md, section 4 « Pipeline d'ingestion » : parcours
récursif de `xml/`, en ignorant `index.xml` et `ns-*.xml` (des manifestes,
pas des fichiers `<Type>`). Traitement par lots pour ne pas tout garder en
mémoire pendant un build de plusieurs heures.

Exécutable directement :
`python -m ingest.corpus <xml_root> [db_path] [--batch-size N]`
"""

from __future__ import annotations

import argparse
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ingest.parser import load_type, parse_type
from ingest.schema import DEFAULT_DB_PATH, create_schema

DEFAULT_BATCH_SIZE = 2000


def iter_type_files(xml_root: Path):
    """Fichiers `<Type>` sous `xml_root`, en ignorant `index.xml` et `ns-*.xml`."""
    for path in sorted(xml_root.rglob("*.xml")):
        if path.name == "index.xml" or path.name.startswith("ns-"):
            continue
        yield path


@dataclass
class CorpusStats:
    type_count: int = 0
    group_count: int = 0
    overload_count: int = 0
    confidence_counts: Counter = field(default_factory=Counter)
    failed_files: list[str] = field(default_factory=list)


def parse_corpus(
    xml_root: Path,
    conn: sqlite3.Connection,
    source_key: str = "dotnet",
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> CorpusStats:
    """Parse tous les fichiers `<Type>` sous `xml_root` dans `conn`, par lots.

    Un fichier XML malformé est consigné dans `failed_files` et ignoré : il
    n'interrompt pas le parcours du reste du corpus (spec §11 — le script
    doit tourner jusqu'au bout sans erreur fatale).
    """
    stats = CorpusStats()
    pending_entries = 0

    for path in iter_type_files(xml_root):
        try:
            parsed = parse_type(path.read_text(encoding="utf-8"))
        except ET.ParseError:
            stats.failed_files.append(str(path))
            continue

        load_type(conn, parsed, source_key=source_key, commit=False)

        stats.type_count += 1
        entries = 1  # la ligne `type`
        for group in parsed.groups:
            stats.group_count += 1
            stats.confidence_counts[group.version_confidence] += 1
            stats.overload_count += len(group.overloads)
            entries += 1 + len(group.overloads)  # la ligne `member_group` + ses `overload`

        pending_entries += entries
        if pending_entries >= batch_size:
            conn.commit()
            pending_entries = 0

    conn.commit()
    return stats


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Parse le corpus dotnet-api-docs complet vers la base DocsTools."
    )
    arg_parser.add_argument("xml_root", help="Dossier xml/ du dépôt dotnet-api-docs cloné")
    arg_parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH)
    arg_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = arg_parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        stats = parse_corpus(Path(args.xml_root), conn, batch_size=args.batch_size)
    finally:
        conn.close()

    print(
        f"{stats.type_count} types, {stats.group_count} groupes, "
        f"{stats.overload_count} surcharges"
    )
    total_confidence = sum(stats.confidence_counts.values())
    for label in ("explicit", "inferred", "unknown"):
        n = stats.confidence_counts.get(label, 0)
        pct = 100 * n / total_confidence if total_confidence else 0
        print(f"  {label:9s} {n:6d} ({pct:.1f}%)")
    if stats.failed_files:
        print(f"{len(stats.failed_files)} fichier(s) en échec :")
        for f in stats.failed_files:
            print(f"  {f}")


if __name__ == "__main__":
    main()
