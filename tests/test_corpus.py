import sqlite3

import pytest

from ingest.corpus import DEFAULT_BATCH_SIZE, iter_type_files, parse_corpus
from ingest.schema import create_schema

_TYPE_XML = """
<Type Name="{name}" FullName="Ns.{name}">
  <TypeSignature Language="C#" Value="public class {name}" />
  <Docs><summary>{name}.</summary></Docs>
  <Members>
    <Member MemberName="M">
      <MemberSignature Language="C#" Value="public void M ();" />
      <MemberType>Method</MemberType>
      <AssemblyInfo>
        <AssemblyName>netstandard</AssemblyName>
        <AssemblyVersion>2.0.0.0</AssemblyVersion>
      </AssemblyInfo>
      <Docs><summary>M.</summary></Docs>
    </Member>
  </Members>
</Type>
"""

_MALFORMED_XML = "<Type Name=\"Broken\"><Unclosed>"

_NS_MANIFEST_XML = '<Namespace Name="Ns"><Docs><summary>Ns.</summary></Docs></Namespace>'


@pytest.fixture
def fake_corpus(tmp_path):
    xml_root = tmp_path / "xml"
    (xml_root / "Ns").mkdir(parents=True)

    (xml_root / "index.xml").write_text("<Types><Type>ignored</Type></Types>", encoding="utf-8")
    (xml_root / "ns-Ns.xml").write_text(_NS_MANIFEST_XML, encoding="utf-8")
    (xml_root / "Ns" / "A.xml").write_text(_TYPE_XML.format(name="A"), encoding="utf-8")
    (xml_root / "Ns" / "B.xml").write_text(_TYPE_XML.format(name="B"), encoding="utf-8")
    (xml_root / "Ns" / "Broken.xml").write_text(_MALFORMED_XML, encoding="utf-8")

    return xml_root


def test_iter_type_files_ignores_index_and_ns_manifests(fake_corpus):
    names = {p.name for p in iter_type_files(fake_corpus)}
    assert names == {"A.xml", "B.xml", "Broken.xml"}


def test_parse_corpus_loads_every_valid_type_and_records_failures(tmp_path, fake_corpus):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        stats = parse_corpus(fake_corpus, conn)

        assert stats.type_count == 2
        assert stats.group_count == 2
        assert stats.overload_count == 2
        assert stats.confidence_counts == {"inferred": 2}
        assert len(stats.failed_files) == 1
        assert stats.failed_files[0].endswith("Broken.xml")

        row_count = conn.execute("SELECT COUNT(*) FROM type").fetchone()[0]
        assert row_count == 2
    finally:
        conn.close()


def test_parse_corpus_does_not_stop_on_a_malformed_file(tmp_path, fake_corpus):
    # Le fichier malformé est trié avant A/B alphabétiquement ("Broken" < "A"
    # n'est pas garanti, donc on vérifie juste que le parcours va au bout).
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        stats = parse_corpus(fake_corpus, conn)
        assert stats.type_count == 2  # A et B chargés malgré Broken.xml
    finally:
        conn.close()


class _CountingConnection(sqlite3.Connection):
    commit_count = 0

    def commit(self):
        self.commit_count += 1
        super().commit()


def test_parse_corpus_commits_in_batches_not_only_at_the_end(tmp_path, fake_corpus):
    db_path = tmp_path / "index.sqlite"
    create_schema(db_path)
    conn = sqlite3.connect(db_path, factory=_CountingConnection)

    try:
        # batch_size=1 : un commit doit survenir après chaque type (au moins),
        # pas uniquement le commit final.
        parse_corpus(fake_corpus, conn, batch_size=1)
        assert conn.commit_count >= 2
    finally:
        conn.close()


def test_default_batch_size_matches_spec():
    # Spec §4 : "commit toutes les ~2000 entrées".
    assert DEFAULT_BATCH_SIZE == 2000
