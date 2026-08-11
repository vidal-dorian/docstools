"""API DocsTools : `POST /api/search`, `GET /api/versions` (US-021),
`GET /api/group/{id}` (US-022), filtre de version (US-023).

Voir docs/specification.md, section 6. Le rerank vectoriel (US-042)
n'existe pas encore : le tri repose uniquement sur `bm25()` (US-020) et la
réponse porte toujours `"reranked": false`.

Le filtre de version (spec §5) s'applique après le classement bm25, jamais
avant — sur les résultats déjà triés, pas sur le vivier de candidats FTS5.
Un groupe est retenu si au moins une de ses surcharges est `present` dans
la version sélectionnée, ou si `version_confidence = 'unknown'` (mieux vaut
un résultat non vérifié qu'un résultat manquant, spec §4).
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from api.search import DEFAULT_LIMIT, search_groups

DB_PATH_ENV_VAR = "DOCSTOOLS_DB_PATH"
DEFAULT_DB_PATH = "index.sqlite"

app = FastAPI(title="DocsTools API")


def get_db_path() -> str:
    return os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH)


def get_connection(db_path: str = Depends(get_db_path)) -> Iterator[sqlite3.Connection]:
    # check_same_thread=False : FastAPI exécute l'entrée et la sortie de cette
    # dépendance générateur via anyio.to_thread.run_sync, sans garantir le
    # même thread pour les deux appels — sqlite3 lève sinon une
    # ProgrammingError sur conn.close() (une seule connexion par requête,
    # jamais partagée entre threads concurrents, donc sans risque ici).
    #
    # mode=ro + PRAGMA query_only (spec §8) : l'API ne doit structurellement
    # pas pouvoir corrompre l'index — la connexion refuse toute écriture même
    # en cas de bug applicatif.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = 1")
    try:
        yield conn
    finally:
        conn.close()


class SearchRequest(BaseModel):
    q: str
    vector: list[float] | None = None  # ignoré tant que le rerank (US-042) n'existe pas
    version: str | None = None
    limit: int = DEFAULT_LIMIT


class SearchResult(BaseModel):
    group_id: int
    name: str
    type: str
    namespace: str
    kind: str
    is_static: bool
    summary: str
    overload_count: int
    signature_preview: str
    version_confidence: str
    available_in_selected: bool


class SearchResponse(BaseModel):
    reranked: bool
    results: list[SearchResult]


class VersionOut(BaseModel):
    moniker: str
    label: str
    family: str


def _resolve_version_id(conn: sqlite3.Connection, moniker: str) -> int | None:
    row = conn.execute("SELECT id FROM version WHERE moniker = ?", (moniker,)).fetchone()
    return row[0] if row is not None else None


def _is_available_in_version(conn: sqlite3.Connection, group_id: int, version_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM overload o
        JOIN overload_version ov ON ov.overload_id = o.id
        WHERE o.group_id = ? AND ov.version_id = ?
        LIMIT 1
        """,
        (group_id, version_id),
    ).fetchone()
    return row is not None


def _signature_preview(conn: sqlite3.Connection, group_id: int) -> str:
    row = conn.execute(
        "SELECT signature FROM overload WHERE group_id = ? ORDER BY ordinal LIMIT 1",
        (group_id,),
    ).fetchone()
    return row[0] if row is not None else ""


@app.post("/api/search", response_model=SearchResponse)
def search(
    request: SearchRequest, conn: sqlite3.Connection = Depends(get_connection)
) -> SearchResponse:
    # Le classement bm25 porte sur un vivier large (spec §5 : top 150), pas
    # sur `limit` — sinon le filtre de version réduirait un vivier déjà
    # tronqué au lieu de filtrer un classement complet.
    hits = search_groups(conn, request.q, limit=DEFAULT_LIMIT)
    version_id = _resolve_version_id(conn, request.version) if request.version else None

    results = []
    for hit in hits:
        row = conn.execute(
            """
            SELECT g.id, g.name, t.name, t.namespace, g.kind, g.is_static,
                   g.summary, g.overload_count, g.version_confidence
            FROM member_group g
            JOIN type t ON t.id = g.type_id
            WHERE g.id = ?
            """,
            (hit.group_id,),
        ).fetchone()
        if row is None:
            continue
        (
            group_id,
            name,
            type_name,
            namespace,
            kind,
            is_static,
            summary,
            overload_count,
            version_confidence,
        ) = row

        if version_id is None:
            available_in_selected = True
        else:
            available_in_selected = _is_available_in_version(conn, group_id, version_id)
            if not available_in_selected and version_confidence != "unknown":
                # Absent, de façon confirmée, de la version sélectionnée —
                # exclu du classement (spec §5), pas seulement marqué indisponible.
                continue

        results.append(
            SearchResult(
                group_id=group_id,
                name=name,
                type=type_name,
                namespace=namespace or "",
                kind=kind,
                is_static=bool(is_static),
                summary=summary or "",
                overload_count=overload_count,
                signature_preview=_signature_preview(conn, group_id),
                version_confidence=version_confidence,
                available_in_selected=available_in_selected,
            )
        )

    return SearchResponse(reranked=False, results=results[: request.limit])


@app.get("/api/versions", response_model=list[VersionOut])
def list_versions(conn: sqlite3.Connection = Depends(get_connection)) -> list[VersionOut]:
    rows = conn.execute(
        "SELECT moniker, label, family FROM version ORDER BY sort_order"
    ).fetchall()
    return [VersionOut(moniker=m, label=lbl, family=fam) for m, lbl, fam in rows]


class ParamOut(BaseModel):
    name: str
    type: str
    doc: str


class ExceptionOut(BaseModel):
    type: str
    doc: str


class VersionCoverageOut(BaseModel):
    moniker: str
    label: str
    family: str
    status: str  # present | deprecated (overload_version.status)


class OverloadOut(BaseModel):
    overload_id: int
    signature: str
    doc_id: str
    summary: str
    returns_doc: str | None
    return_type: str | None
    params: list[ParamOut]
    exceptions: list[ExceptionOut]
    remarks_md: str | None
    example_code: str | None
    doc_url: str
    versions: list[VersionCoverageOut]


class GroupDetailOut(BaseModel):
    group_id: int
    name: str
    type: str
    namespace: str
    kind: str
    is_static: bool
    version_confidence: str
    doc_url: str
    overloads: list[OverloadOut]


def _overload_versions(conn: sqlite3.Connection, overload_id: int) -> list[VersionCoverageOut]:
    rows = conn.execute(
        """
        SELECT v.moniker, v.label, v.family, ov.status
        FROM overload_version ov
        JOIN version v ON v.id = ov.version_id
        WHERE ov.overload_id = ?
        ORDER BY v.sort_order
        """,
        (overload_id,),
    ).fetchall()
    return [
        VersionCoverageOut(moniker=m, label=lbl, family=fam, status=status)
        for m, lbl, fam, status in rows
    ]


@app.get("/api/group/{group_id}", response_model=GroupDetailOut)
def get_group(
    group_id: int, conn: sqlite3.Connection = Depends(get_connection)
) -> GroupDetailOut:
    group_row = conn.execute(
        """
        SELECT g.id, g.name, t.name, t.namespace, g.kind, g.is_static,
               g.version_confidence, g.doc_url
        FROM member_group g
        JOIN type t ON t.id = g.type_id
        WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()
    if group_row is None:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")

    (
        gid,
        name,
        type_name,
        namespace,
        kind,
        is_static,
        version_confidence,
        doc_url,
    ) = group_row

    overload_rows = conn.execute(
        """
        SELECT id, signature, doc_id, summary, returns_doc, return_type,
               params_json, exceptions_json, remarks_md, example_code, doc_url
        FROM overload
        WHERE group_id = ?
        ORDER BY ordinal
        """,
        (group_id,),
    ).fetchall()

    overloads = [
        OverloadOut(
            overload_id=row[0],
            signature=row[1],
            doc_id=row[2],
            summary=row[3],
            returns_doc=row[4],
            return_type=row[5],
            params=[ParamOut(**p) for p in json.loads(row[6])],
            exceptions=[ExceptionOut(**e) for e in json.loads(row[7])],
            remarks_md=row[8],
            example_code=row[9],
            doc_url=row[10],
            versions=_overload_versions(conn, row[0]),
        )
        for row in overload_rows
    ]

    return GroupDetailOut(
        group_id=gid,
        name=name,
        type=type_name,
        namespace=namespace or "",
        kind=kind,
        is_static=bool(is_static),
        version_confidence=version_confidence,
        doc_url=doc_url,
        overloads=overloads,
    )
