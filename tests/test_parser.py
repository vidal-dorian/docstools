import sqlite3
from pathlib import Path

import pytest

from ingest.parser import load_type, parse_type
from ingest.schema import create_schema

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "System.DateTime.xml"

# Membre isolé qui n'a volontairement pas de <MemberSignature Language="C#">
# (cas réel : membres documentés uniquement pour d'autres langages).
NO_CS_SIGNATURE_XML = """
<Type Name="Widget" FullName="System.Widget">
  <TypeSignature Language="C#" Value="public class Widget" />
  <Docs><summary>A widget.</summary></Docs>
  <Members>
    <Member MemberName="Frobnicate">
      <MemberSignature Language="VB.NET" Value="Sub Frobnicate()" />
      <MemberType>Method</MemberType>
      <Docs><summary>VB-only member.</summary></Docs>
    </Member>
    <Member MemberName="DoThing">
      <MemberSignature Language="C#" Value="public void DoThing ();" />
      <MemberSignature Language="DocId" Value="M:System.Widget.DoThing" />
      <MemberType>Method</MemberType>
      <Docs><summary>Does the thing.</summary></Docs>
    </Member>
  </Members>
</Type>
"""


@pytest.fixture(scope="module")
def datetime_type():
    return parse_type(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def add_months_group(datetime_type):
    matches = [g for g in datetime_type.groups if g.name == "AddMonths" and g.kind == "Method"]
    assert len(matches) == 1
    return matches[0]


def test_type_row_is_correct(datetime_type):
    assert datetime_type.namespace == "System"
    assert datetime_type.name == "DateTime"
    assert datetime_type.full_name == "System.DateTime"
    assert datetime_type.kind == "struct"
    assert "instant in time" in datetime_type.summary


def test_add_months_is_a_single_group_regardless_of_overload_count(add_months_group):
    # Groupé par (MemberName, MemberType) : un seul member_group pour AddMonths,
    # quel que soit le nombre de <Member> qui partagent ce nom dans le XML.
    assert add_months_group.kind == "Method"
    assert len(add_months_group.overloads) >= 1


def test_see_and_paramref_are_flattened_to_readable_text(add_months_group):
    overload = add_months_group.overloads[0]

    assert "<see" not in overload.summary
    assert "<paramref" not in overload.summary
    assert overload.summary == (
        "Returns a new DateTime that adds the specified number of months "
        "to the value of this instance."
    )

    months_doc = next(p.doc for p in overload.params if p.name == "months")
    assert "<paramref" not in months_doc
    assert "months parameter can be negative or positive" in months_doc

    assert "<paramref" not in overload.returns_doc
    assert "months" in overload.returns_doc


def test_member_without_cs_signature_is_ignored_not_crashed():
    parsed = parse_type(NO_CS_SIGNATURE_XML)

    names = {g.name for g in parsed.groups}
    assert "Frobnicate" not in names
    assert "DoThing" in names


def test_load_type_writes_type_member_group_and_overload_rows(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    parsed = parse_type(NO_CS_SIGNATURE_XML)

    conn = sqlite3.connect(db_path)
    try:
        load_type(conn, parsed)

        type_row = conn.execute(
            "SELECT namespace, name, full_name, kind FROM type WHERE full_name = ?",
            ("System.Widget",),
        ).fetchone()
        assert type_row == ("System", "Widget", "System.Widget", "class")

        group_row = conn.execute(
            "SELECT name, kind, overload_count, version_confidence "
            "FROM member_group WHERE name = ?",
            ("DoThing",),
        ).fetchone()
        assert group_row == ("DoThing", "Method", 1, "unknown")

        overload_row = conn.execute(
            "SELECT signature, doc_id FROM overload"
        ).fetchone()
        assert overload_row == ("public void DoThing ();", "M:System.Widget.DoThing")
    finally:
        conn.close()


def test_load_type_is_replayable_for_the_same_type(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    parsed = parse_type(NO_CS_SIGNATURE_XML)

    conn = sqlite3.connect(db_path)
    try:
        load_type(conn, parsed)
        load_type(conn, parsed)

        count = conn.execute(
            "SELECT COUNT(*) FROM type WHERE full_name = ?", ("System.Widget",)
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_add_months_is_available_in_netframework_4x_and_modern_net(add_months_group):
    # dotnet-api-docs n'expose plus, à la date du build, d'AssemblyInfo pour les
    # monikers net-5.0/6.0/7.0 (versions .NET hors support, élaguées en amont) :
    # on vérifie donc la famille "net-N.0 avec N >= 5", pas les monikers exacts.
    monikers = {m for o in add_months_group.overloads for m in o.version.monikers}
    assert "netframework-4.x" in monikers
    net_monikers = {m for m in monikers if m.startswith("net-")}
    assert net_monikers, "aucun moniker net-N.0 résolu pour AddMonths"
    assert all(int(m.removeprefix("net-").split(".")[0]) >= 5 for m in net_monikers)


def test_load_type_writes_overload_version_rows_for_add_months(tmp_path, datetime_type):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        load_type(conn, datetime_type)

        rows = conn.execute(
            """
            SELECT v.moniker FROM overload_version ov
            JOIN overload o ON o.id = ov.overload_id
            JOIN member_group g ON g.id = o.group_id
            JOIN version v ON v.id = ov.version_id
            WHERE g.name = 'AddMonths'
            """
        ).fetchall()
        monikers = {row[0] for row in rows}

        assert "netframework-4.x" in monikers
        assert any(m.startswith("net-") for m in monikers)
    finally:
        conn.close()


def test_every_non_unknown_group_has_at_least_one_overload_version_row(tmp_path, datetime_type):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        load_type(conn, datetime_type)

        groups_without_version_row = conn.execute(
            """
            SELECT g.id FROM member_group g
            WHERE g.version_confidence != 'unknown'
              AND NOT EXISTS (
                SELECT 1 FROM overload o
                JOIN overload_version ov ON ov.overload_id = o.id
                WHERE o.group_id = g.id
              )
            """
        ).fetchall()

        assert groups_without_version_row == []
    finally:
        conn.close()
