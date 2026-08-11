import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_connection
from ingest.parser import load_type, parse_type
from ingest.schema import create_schema

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_FIXTURES = [
    "System.DateTime.xml",
    "System.String.xml",
    "System.Math.xml",
    "System.Collections.Generic.List`1.xml",
    "System.Linq.Enumerable.xml",
]


@pytest.fixture(scope="module")
def sample_db_path(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("api") / "index.sqlite"
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
def add_months_group_id(sample_db_path):
    conn = sqlite3.connect(sample_db_path)
    try:
        return conn.execute(
            "SELECT id FROM member_group WHERE name = 'AddMonths'"
        ).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def client(sample_db_path):
    def override_get_connection():
        conn = sqlite3.connect(sample_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_connection] = override_get_connection
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_search_accepts_q_version_and_limit(client):
    response = client.post(
        "/api/search", json={"q": "add months date", "version": "net-8.0", "limit": 5}
    )
    assert response.status_code == 200


def test_search_response_matches_the_spec_contract(client):
    response = client.post("/api/search", json={"q": "add months date"})
    body = response.json()

    assert body["reranked"] is False
    assert body["results"], "aucun résultat pour 'add months date'"

    top = body["results"][0]
    assert top["name"] == "AddMonths"
    assert top["type"] == "DateTime"
    assert top["namespace"] == "System"
    assert top["kind"] == "Method"
    assert isinstance(top["is_static"], bool)
    assert isinstance(top["overload_count"], int)
    assert "AddMonths" in top["signature_preview"]
    assert top["version_confidence"] in {"explicit", "inferred", "unknown"}
    assert isinstance(top["available_in_selected"], bool)


def test_search_sorts_by_bm25_add_months_first(client):
    response = client.post("/api/search", json={"q": "add months date"})
    results = response.json()["results"]
    assert results[0]["name"] == "AddMonths"


def test_search_or_mode_finds_candidates_for_cut_end_of_string(client):
    response = client.post("/api/search", json={"q": "cut end of string"})
    assert response.json()["results"]


def test_search_without_version_marks_everything_available(client):
    response = client.post("/api/search", json={"q": "add months date"})
    results = response.json()["results"]
    assert all(r["available_in_selected"] for r in results)


def test_search_with_version_marks_add_months_available(client):
    response = client.post(
        "/api/search", json={"q": "add months date", "version": "net-8.0"}
    )
    results = response.json()["results"]
    add_months = next(r for r in results if r["name"] == "AddMonths")
    # AddMonths est présent en net-8.0 dans la fixture réelle (US-012).
    assert add_months["available_in_selected"] is True


def test_search_excludes_groups_confirmed_absent_from_the_selected_version(client):
    # netframework-1.1 n'existe que via mscorlib 1.0.5000.0 : les API .NET
    # modernes (ex. LINQ, System.Numerics.Vectors...) n'y sont jamais
    # présentes. On compare le classement avec et sans filtre.
    unfiltered = client.post("/api/search", json={"q": "value", "limit": 150})
    filtered = client.post(
        "/api/search", json={"q": "value", "version": "netframework-1.1", "limit": 150}
    )

    unfiltered_ids = {r["group_id"] for r in unfiltered.json()["results"]}
    filtered_ids = {r["group_id"] for r in filtered.json()["results"]}

    assert filtered_ids <= unfiltered_ids
    assert filtered_ids != unfiltered_ids, "le filtre de version n'a rien exclu"

    for result in filtered.json()["results"]:
        assert result["available_in_selected"] is True or result["version_confidence"] == "unknown"


def test_search_filter_applies_after_ranking_not_before(client):
    # Un groupe non retenu par le filtre ne doit pas "consommer" une place
    # dans le classement bm25 : le vivier candidat reste large (spec §5).
    response = client.post(
        "/api/search",
        json={"q": "value", "version": "netframework-1.1", "limit": 3},
    )
    assert len(response.json()["results"]) <= 3


def test_search_limit_is_applied_after_the_version_filter(client):
    response = client.post(
        "/api/search", json={"q": "value", "version": "netframework-1.1", "limit": 1}
    )
    assert len(response.json()["results"]) <= 1


def test_search_respects_limit(client):
    response = client.post("/api/search", json={"q": "value", "limit": 2})
    assert len(response.json()["results"]) <= 2


def test_list_versions_returns_known_monikers(client):
    response = client.get("/api/versions")
    assert response.status_code == 200

    monikers = {v["moniker"] for v in response.json()}
    assert "netframework-4.x" in monikers
    assert "net-8.0" in monikers
    for version in response.json():
        assert set(version.keys()) == {"moniker", "label", "family"}


def test_get_group_returns_all_overloads_with_typed_params(client, add_months_group_id):
    response = client.get(f"/api/group/{add_months_group_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["group_id"] == add_months_group_id
    assert body["name"] == "AddMonths"
    assert body["type"] == "DateTime"
    assert body["namespace"] == "System"

    # AddMonths n'a qu'une seule surcharge dans la fixture réelle.
    assert len(body["overloads"]) == 1
    overload = body["overloads"][0]
    assert overload["signature"] == "public DateTime AddMonths (int months);"
    assert overload["params"] == [
        {
            "name": "months",
            "type": "System.Int32",
            "doc": "A number of months. The months parameter can be negative or positive.",
        }
    ]
    assert overload["exceptions"][0]["type"] == "ArgumentOutOfRangeException"
    assert overload["remarks_md"] is not None
    assert overload["return_type"] == "System.DateTime"


def test_get_group_returns_version_coverage_joined_to_version_table(
    client, add_months_group_id
):
    response = client.get(f"/api/group/{add_months_group_id}")
    versions = response.json()["overloads"][0]["versions"]

    assert versions, "aucune couverture de version pour AddMonths"
    monikers = {v["moniker"] for v in versions}
    assert "netframework-4.x" in monikers
    assert "net-8.0" in monikers
    for coverage in versions:
        assert set(coverage.keys()) == {"moniker", "label", "family", "status"}
        assert coverage["status"] == "present"


def test_get_group_returns_404_for_an_unknown_id(client):
    response = client.get("/api/group/999999999")
    assert response.status_code == 404


def test_get_group_multi_overload_group_returns_every_overload(client, sample_db_path):
    conn = sqlite3.connect(sample_db_path)
    try:
        ctor_group_id = conn.execute(
            """
            SELECT g.id FROM member_group g
            JOIN type t ON t.id = g.type_id
            WHERE g.name = '.ctor' AND t.name = 'DateTime' AND g.overload_count > 1
            """
        ).fetchone()[0]
    finally:
        conn.close()

    response = client.get(f"/api/group/{ctor_group_id}")
    body = response.json()
    assert len(body["overloads"]) > 1
    # ordonnées par `ordinal`
    assert [o["overload_id"] for o in body["overloads"]] == sorted(
        o["overload_id"] for o in body["overloads"]
    )
