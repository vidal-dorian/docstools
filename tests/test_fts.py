import sqlite3

from ingest.parser import load_type, optimize_fts, parse_type
from ingest.schema import create_schema

_TYPE_XML = """
<Type Name="Widget" FullName="Ns.Widget">
  <TypeSignature Language="C#" Value="public class Widget" />
  <Docs><summary>A widget.</summary></Docs>
  <Members>
    <Member MemberName="Resize">
      <MemberSignature Language="C#" Value="public void Resize (int width, int height);" />
      <MemberType>Method</MemberType>
      <Parameters>
        <Parameter Name="width" Type="System.Int32" />
        <Parameter Name="height" Type="System.Int32" />
      </Parameters>
      <Docs>
        <param name="width">The new width.</param>
        <param name="height">The new height.</param>
        <summary>Resizes the widget.</summary>
      </Docs>
    </Member>
    <Member MemberName="Resize">
      <MemberSignature Language="C#" Value="public void Resize (int size);" />
      <MemberType>Method</MemberType>
      <Parameters>
        <Parameter Name="size" Type="System.Int32" />
      </Parameters>
      <Docs>
        <param name="size">The new size, applied to width and height.</param>
        <summary>Resizes the widget uniformly.</summary>
      </Docs>
    </Member>
  </Members>
</Type>
"""


def _load(conn):
    load_type(conn, parse_type(_TYPE_XML))


def test_group_fts_rowid_matches_member_group_id(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _load(conn)

        group_id = conn.execute(
            "SELECT id FROM member_group WHERE name = 'Resize'"
        ).fetchone()[0]
        fts_rowid = conn.execute(
            "SELECT rowid FROM group_fts WHERE rowid = ?", (group_id,)
        ).fetchone()

        assert fts_rowid == (group_id,)
    finally:
        conn.close()


def test_group_fts_columns_contain_name_type_summary_and_params(tmp_path):
    # group_fts est contentless (content='') : le texte original n'est pas
    # relisible par SELECT, seule une recherche MATCH par colonne le prouve.
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _load(conn)

        group_id = conn.execute(
            "SELECT id FROM member_group WHERE name = 'Resize'"
        ).fetchone()[0]

        def matches(column: str, term: str) -> bool:
            rows = conn.execute(
                f"SELECT rowid FROM group_fts WHERE {column} MATCH ?", (term,)
            ).fetchall()
            return (group_id,) in rows

        assert matches("name", "Resize")
        assert matches("type_name", "Widget")
        assert matches("summary", "widget")
        # Deux surcharges, params dédupliqués : width, height, size.
        assert matches("params", "width")
        assert matches("params", "height")
        assert matches("params", "size")
    finally:
        conn.close()


def test_group_fts_is_searchable_by_param_name(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _load(conn)

        rows = conn.execute(
            "SELECT rowid FROM group_fts WHERE group_fts MATCH 'height'"
        ).fetchall()
        assert len(rows) == 1

        group_id = conn.execute(
            "SELECT id FROM member_group WHERE name = 'Resize'"
        ).fetchone()[0]
        assert rows[0][0] == group_id
    finally:
        conn.close()


def test_reloading_the_same_type_does_not_duplicate_or_orphan_fts_rows(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _load(conn)
        _load(conn)

        fts_count = conn.execute("SELECT COUNT(*) FROM group_fts").fetchone()[0]
        group_count = conn.execute("SELECT COUNT(*) FROM member_group").fetchone()[0]
        assert fts_count == group_count == 1
    finally:
        conn.close()


def test_optimize_fts_runs_and_index_stays_queryable(tmp_path):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        _load(conn)
        optimize_fts(conn)

        rows = conn.execute(
            "SELECT rowid FROM group_fts WHERE group_fts MATCH 'widget'"
        ).fetchall()
        assert len(rows) == 1
    finally:
        conn.close()
