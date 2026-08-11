"""Détection des exemples de code inline vs inclusion externe non résolue (US-014).

Voir docs/specification.md, section 4, risque « les exemples de code » :
les blocs remarks référencent souvent un exemple via une syntaxe
d'inclusion — `:::code language="csharp" source="~/snippets/...":::`
(DocFX actuel) ou l'ancienne syntaxe `[!code-csharp[titre](chemin)]` —
pointant vers des fichiers absents du dépôt `dotnet-api-docs`. Ce module
classe la section « ## Examples » de chaque surcharge documentée selon
qu'elle contient du code réellement inline, ou seulement une inclusion
externe non résolue.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from ingest.parser import ParsedType, parse_type

_EXAMPLES_HEADING_RE = re.compile(r"^##\s*Examples\s*$", re.IGNORECASE | re.MULTILINE)
_INCLUSION_RE = re.compile(
    r":::code\b.*?:::" r"|" r"\[!code-[a-zA-Z]+\[.*?\]\(.*?\)\]", re.DOTALL
)
_FENCED_CODE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def classify_example(remarks_md: str | None) -> str:
    """`'inline' | 'external' | 'none'` pour la section Examples d'une surcharge.

    - `'none'` : pas de section `## Examples` dans les remarks.
    - `'external'` : la section contient une syntaxe d'inclusion (le code
      lui-même n'est pas présent dans ce fichier ECMAXML).
    - `'inline'` : la section contient un bloc de code Markdown complet,
      sans inclusion externe.
    """
    if not remarks_md:
        return "none"

    heading = _EXAMPLES_HEADING_RE.search(remarks_md)
    if heading is None:
        return "none"
    section = remarks_md[heading.end() :]

    if _INCLUSION_RE.search(section):
        return "external"
    if any(block.strip() for block in _FENCED_CODE_RE.findall(section)):
        return "inline"
    return "none"


def measure_inline_examples(parsed_types: list[ParsedType]) -> Counter[str]:
    """Compte `inline` / `external` / `none` sur toutes les surcharges des types donnés."""
    counts: Counter[str] = Counter()
    for parsed in parsed_types:
        for group in parsed.groups:
            for overload in group.overloads:
                counts[classify_example(overload.remarks_md)] += 1
    return counts


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Mesure la proportion d'exemples de code réellement inline (US-014)."
    )
    arg_parser.add_argument("xml_paths", nargs="+", help="Fichiers xml/<Namespace>/<Type>.xml")
    args = arg_parser.parse_args()

    parsed_types = [
        parse_type(Path(p).read_text(encoding="utf-8")) for p in args.xml_paths
    ]
    counts = measure_inline_examples(parsed_types)
    total = sum(counts.values())
    total_overloads = sum(len(g.overloads) for t in parsed_types for g in t.groups)

    print(f"{total_overloads} surcharges sur {len(parsed_types)} types")
    for label in ("inline", "external", "none"):
        n = counts[label]
        pct = 100 * n / total if total else 0
        print(f"  {label:10s} {n:4d} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
