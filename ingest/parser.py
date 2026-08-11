"""Parsing ECMAXML → tables `type` / `member_group` / `overload` (US-011)
et résolution des versions → `overload_version` (US-012).

Un seul fichier `xml/<Namespace>/<Type>.xml` à la fois — voir
docs/specification.md, section 4. Le parcours du corpus complet (US-015)
est hors périmètre.

Exécutable directement : `python -m ingest.parser <xml_path> [db_path]`
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ingest.schema import DEFAULT_DB_PATH, create_schema
from ingest.versions import (
    VersionResolution,
    get_or_create_version,
    group_confidence,
    resolve_member_versions,
)

_KIND_KEYWORDS = ("class", "struct", "interface", "enum", "delegate")
_CREF_PREFIX_RE = re.compile(r"^[A-Za-z]+:")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class ParsedParam:
    name: str
    type: str
    doc: str


@dataclass
class ParsedException:
    type: str
    doc: str


@dataclass
class ParsedOverload:
    signature: str
    doc_id: str
    summary: str
    returns_doc: str | None
    return_type: str | None
    params: list[ParsedParam]
    exceptions: list[ParsedException]
    remarks_md: str | None
    version: VersionResolution


@dataclass
class ParsedGroup:
    name: str
    kind: str
    overloads: list[ParsedOverload] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return self.overloads[0].summary if self.overloads else ""

    @property
    def is_static(self) -> bool:
        return any(_is_static_signature(o.signature) for o in self.overloads)

    @property
    def version_confidence(self) -> str:
        return group_confidence([o.version for o in self.overloads])


@dataclass
class ParsedType:
    namespace: str
    name: str
    full_name: str
    kind: str
    summary: str
    groups: list[ParsedGroup]


def parse_type(xml_text: str) -> ParsedType:
    """Parse le contenu d'un fichier ECMAXML `<Type>` en `ParsedType`."""
    root = ET.fromstring(xml_text)

    full_name = root.get("FullName", "")
    name = root.get("Name", "")
    suffix = f".{name}"
    namespace = full_name[: -len(suffix)] if full_name.endswith(suffix) else ""

    type_docs = root.find("Docs")
    summary = _flatten_text(type_docs.find("summary")) if type_docs is not None else ""

    groups: dict[tuple[str, str], ParsedGroup] = {}
    order: list[tuple[str, str]] = []
    members_elem = root.find("Members")
    if members_elem is not None:
        for member in members_elem.findall("Member"):
            cs_signature_elem = _member_signature_element(member, "C#")
            if cs_signature_elem is None:
                # Membre sans signature C# — ignoré, pas planté.
                continue

            key = (member.get("MemberName", ""), member.findtext("MemberType", default=""))
            if key not in groups:
                groups[key] = ParsedGroup(name=key[0], kind=key[1])
                order.append(key)
            groups[key].overloads.append(_parse_overload(member, cs_signature_elem))

    return ParsedType(
        namespace=namespace,
        name=name,
        full_name=full_name,
        kind=_type_kind(root),
        summary=summary,
        groups=[groups[key] for key in order],
    )


def _parse_overload(member: ET.Element, cs_signature_elem: ET.Element) -> ParsedOverload:
    docs = member.find("Docs")
    return ParsedOverload(
        signature=cs_signature_elem.get("Value", ""),
        doc_id=_member_signature(member, "DocId") or "",
        summary=_flatten_text(docs.find("summary")) if docs is not None else "",
        returns_doc=_flatten_optional(docs, "returns") if docs is not None else None,
        return_type=_return_type(member),
        params=_parse_params(member, docs),
        exceptions=_parse_exceptions(docs),
        remarks_md=_remarks_md(docs),
        version=resolve_member_versions(member, cs_signature_elem),
    )


def _member_signature(member: ET.Element, language: str) -> str | None:
    elem = _member_signature_element(member, language)
    return elem.get("Value") if elem is not None else None


def _member_signature_element(member: ET.Element, language: str) -> ET.Element | None:
    for sig in member.findall("MemberSignature"):
        if sig.get("Language") == language:
            return sig
    return None


def _is_static_signature(signature: str) -> bool:
    return "static" in signature.split("(")[0].split()


def _type_kind(type_elem: ET.Element) -> str:
    for sig in type_elem.findall("TypeSignature"):
        if sig.get("Language") == "C#":
            tokens = re.split(r"[\s:<]+", sig.get("Value", ""))
            for keyword in _KIND_KEYWORDS:
                if keyword in tokens:
                    return keyword
    return "unknown"


def _return_type(member: ET.Element) -> str | None:
    return_value = member.find("ReturnValue")
    if return_value is None:
        return None
    return_type = return_value.findtext("ReturnType")
    return return_type.strip() if return_type else None


def _parse_params(member: ET.Element, docs: ET.Element | None) -> list[ParsedParam]:
    param_docs: dict[str, str] = {}
    if docs is not None:
        for param_doc in docs.findall("param"):
            param_docs[param_doc.get("name", "")] = _flatten_text(param_doc)

    params = []
    parameters_elem = member.find("Parameters")
    if parameters_elem is not None:
        for parameter in parameters_elem.findall("Parameter"):
            param_name = parameter.get("Name", "")
            params.append(
                ParsedParam(
                    name=param_name,
                    type=parameter.get("Type", ""),
                    doc=param_docs.get(param_name, ""),
                )
            )
    return params


def _parse_exceptions(docs: ET.Element | None) -> list[ParsedException]:
    if docs is None:
        return []
    return [
        ParsedException(type=_strip_cref(exc.get("cref", "")), doc=_flatten_text(exc))
        for exc in docs.findall("exception")
    ]


def _remarks_md(docs: ET.Element | None) -> str | None:
    if docs is None:
        return None
    remarks = docs.find("remarks")
    if remarks is None:
        return None
    format_elem = remarks.find("format")
    if format_elem is None or format_elem.get("type") != "text/markdown":
        return None
    text = (format_elem.text or "").strip()
    return text or None


def _flatten_optional(docs: ET.Element, tag: str) -> str | None:
    elem = docs.find(tag)
    if elem is None:
        return None
    text = _flatten_text(elem)
    return text or None


def _flatten_text(elem: ET.Element) -> str:
    """Aplatit le texte d'un élément Docs, en résolvant `<see>` et `<paramref>`
    vers leur cible plutôt que de laisser la balise XML brute (spec §4)."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_flatten_child(child))
        if child.tail:
            parts.append(child.tail)
    return _WHITESPACE_RE.sub(" ", "".join(parts)).strip()


def _flatten_child(child: ET.Element) -> str:
    if child.tag == "paramref":
        return child.get("name", "")
    if child.tag == "see":
        text = (child.text or "").strip()
        return text if text else _strip_cref(child.get("cref", ""))
    # Balise inline inconnue (ex. <c>...</c>) : on garde son texte aplati.
    return _flatten_text(child)


def _strip_cref(cref: str) -> str:
    """`T:System.DateTime` → `DateTime`, `M:System.DateTime.AddMonths(...)` → `AddMonths`."""
    target = _CREF_PREFIX_RE.sub("", cref).split("(")[0]
    return target.rsplit(".", 1)[-1]


def _delete_existing_type(conn: sqlite3.Connection, source_id: int, full_name: str) -> None:
    # group_fts est contentless (content='') : impossible d'y faire un DELETE
    # classique, il faut repasser par la commande spéciale 'delete' avec les
    # valeurs déjà stockées pour que FTS5 retire correctement l'entrée.
    fts_rows = conn.execute(
        """
        SELECT f.rowid, f.name, f.type_name, f.summary, f.params
        FROM group_fts f
        JOIN member_group g ON g.id = f.rowid
        JOIN type t ON t.id = g.type_id
        WHERE t.source_id = ? AND t.full_name = ?
        """,
        (source_id, full_name),
    ).fetchall()
    for row in fts_rows:
        conn.execute(
            "INSERT INTO group_fts (group_fts, rowid, name, type_name, summary, params) "
            "VALUES ('delete', ?, ?, ?, ?, ?)",
            row,
        )

    conn.execute(
        """
        DELETE FROM overload_version WHERE overload_id IN (
            SELECT overload.id FROM overload
            JOIN member_group ON member_group.id = overload.group_id
            JOIN type ON type.id = member_group.type_id
            WHERE type.source_id = ? AND type.full_name = ?
        )
        """,
        (source_id, full_name),
    )
    conn.execute(
        """
        DELETE FROM overload WHERE group_id IN (
            SELECT member_group.id FROM member_group
            JOIN type ON type.id = member_group.type_id
            WHERE type.source_id = ? AND type.full_name = ?
        )
        """,
        (source_id, full_name),
    )
    conn.execute(
        """
        DELETE FROM member_group WHERE type_id IN (
            SELECT id FROM type WHERE source_id = ? AND full_name = ?
        )
        """,
        (source_id, full_name),
    )
    conn.execute("DELETE FROM type WHERE source_id = ? AND full_name = ?", (source_id, full_name))


def _fts_params(group: ParsedGroup) -> str:
    """Noms de paramètres de toutes les surcharges du groupe, dédupliqués et
    concaténés — alimente la colonne `params` de `group_fts` (US-016)."""
    names = dict.fromkeys(
        param.name for overload in group.overloads for param in overload.params if param.name
    )
    return " ".join(names)


def optimize_fts(conn: sqlite3.Connection) -> None:
    """Fusionne les segments FTS5 de `group_fts` (spec §4, étape 8).

    À appeler une fois l'insertion terminée — pas après chaque type, ce
    serait aussi coûteux qu'inutile sur un import de plusieurs milliers
    d'entrées.
    """
    conn.execute("INSERT INTO group_fts (group_fts) VALUES ('optimize')")
    conn.commit()


def _get_or_create_source(conn: sqlite3.Connection, key: str) -> int:
    row = conn.execute("SELECT id FROM source WHERE key = ?", (key,)).fetchone()
    if row is not None:
        return row[0]
    cursor = conn.execute("INSERT INTO source (key, label) VALUES (?, ?)", (key, key))
    return cursor.lastrowid


def load_type(
    conn: sqlite3.Connection,
    parsed: ParsedType,
    source_key: str = "dotnet",
    commit: bool = True,
) -> int:
    """Insère un `ParsedType` dans la base ouverte `conn`. Retourne l'id du type.

    `commit=False` laisse la transaction ouverte — utilisé par le parcours du
    corpus complet (US-015) pour committer par lots plutôt qu'à chaque type.
    """
    source_id = _get_or_create_source(conn, source_key)

    # Remplace un import précédent du même type plutôt que d'échouer sur les
    # contraintes UNIQUE — pratique pour rejouer le parsing pendant le dev.
    _delete_existing_type(conn, source_id, parsed.full_name)

    type_doc_url = _doc_url(parsed.full_name)
    type_row = (
        source_id,
        parsed.namespace,
        parsed.name,
        parsed.full_name,
        parsed.kind,
        parsed.summary,
        type_doc_url,
    )
    type_id = conn.execute(
        """
        INSERT INTO type (source_id, namespace, name, full_name, kind, summary, doc_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        type_row,
    ).lastrowid

    for group in parsed.groups:
        group_doc_url = _doc_url(f"{parsed.full_name}.{group.name}")
        group_row = (
            type_id,
            group.name,
            group.kind,
            group.summary,
            int(group.is_static),
            len(group.overloads),
            group_doc_url,
            group.version_confidence,
        )
        group_id = conn.execute(
            """
            INSERT INTO member_group
                (type_id, name, kind, summary, is_static,
                 overload_count, doc_url, version_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            group_row,
        ).lastrowid

        conn.execute(
            "INSERT INTO group_fts (rowid, name, type_name, summary, params) "
            "VALUES (?, ?, ?, ?, ?)",
            (group_id, group.name, parsed.full_name, group.summary, _fts_params(group)),
        )

        for ordinal, overload in enumerate(group.overloads):
            overload_id = conn.execute(
                """
                INSERT INTO overload
                    (group_id, signature, doc_id, summary, returns_doc, return_type,
                     params_json, exceptions_json, remarks_md, example_code, doc_url, ordinal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    group_id,
                    overload.signature,
                    overload.doc_id,
                    overload.summary,
                    overload.returns_doc,
                    overload.return_type,
                    json.dumps([p.__dict__ for p in overload.params], ensure_ascii=False),
                    json.dumps([e.__dict__ for e in overload.exceptions], ensure_ascii=False),
                    overload.remarks_md,
                    group_doc_url,
                    ordinal,
                ),
            ).lastrowid

            for moniker in overload.version.monikers:
                version_id = get_or_create_version(conn, source_id, moniker)
                conn.execute(
                    "INSERT OR IGNORE INTO overload_version (overload_id, version_id) "
                    "VALUES (?, ?)",
                    (overload_id, version_id),
                )

    if commit:
        conn.commit()
    return type_id


def _doc_url(dotted_name: str) -> str:
    return f"https://learn.microsoft.com/dotnet/api/{dotted_name.lower()}"


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Parse un fichier ECMAXML unique vers la base DocsTools."
    )
    arg_parser.add_argument("xml_path", help="Chemin du fichier xml/<Namespace>/<Type>.xml")
    arg_parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH)
    args = arg_parser.parse_args()

    xml_text = Path(args.xml_path).read_text(encoding="utf-8")
    parsed = parse_type(xml_text)

    db_path = Path(args.db_path)
    if not db_path.exists():
        create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        load_type(conn, parsed)
    finally:
        conn.close()

    overload_count = sum(len(g.overloads) for g in parsed.groups)
    print(
        f"{parsed.full_name}: {len(parsed.groups)} groupes, "
        f"{overload_count} surcharges → {db_path}"
    )


if __name__ == "__main__":
    main()
