from routers import knowledge as knowledge_router


def test_upload_knowledge_indexes_chunks(monkeypatch, client, admin_headers):
    calls = {}

    def fake_ingest_text(text, **kwargs):
        calls["text"] = text
        calls["kwargs"] = kwargs
        return {"source_id": "kb:test", "ids": ["kb:test:chunk:0"], "chunks": 1}

    monkeypatch.setattr(knowledge_router.rag_service, "ingest_text", fake_ingest_text)

    response = client.post(
        "/knowledge/upload",
        json={
            "text": "受害人拒绝配合时，先安抚情绪，再解释调查目的。",
            "title": "询问SOP",
            "category": "SOP处置",
            "library": "sop_library",
            "tags": ["询问"],
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["chunks"] == 1
    assert calls["kwargs"]["library"] == "sop_library"
    assert calls["kwargs"]["tags"] == ["询问"]


def test_search_knowledge_returns_structured_hits(monkeypatch, client, admin_headers):
    monkeypatch.setattr(
        knowledge_router.rag_service,
        "search_items",
        lambda query, limit, libraries: [
            {
                "id": "kb:test:chunk:0",
                "title": "询问SOP",
                "content": "先安抚，再说明调查目的。",
                "library": "sop_library",
                "source": "manual",
                "category": "SOP处置",
                "tags": ["询问"],
            }
        ],
    )

    response = client.post(
        "/knowledge/search",
        json={"query": "受害人拒绝配合怎么办", "limit": 3, "libraries": ["sop_library"]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["hits"][0]["library"] == "sop_library"


def test_knowledge_stats_returns_library_status(monkeypatch, client, admin_headers):
    monkeypatch.setattr(
        knowledge_router.rag_service,
        "get_library_stats",
        lambda: {
            "total_chunks": 2,
            "total_sources": 1,
            "embedding_available": True,
            "embedding_error": None,
            "libraries": {
                "sop_library": {
                    "library": "sop_library",
                    "chunk_count": 2,
                    "source_count": 1,
                    "latest_updated_at": "2026-06-17T00:00:00+00:00",
                    "ingest_status": "ready",
                    "retrieval_status": "available",
                }
            },
        },
    )

    response = client.get("/knowledge/stats", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_chunks"] == 2
    assert payload["libraries"]["sop_library"]["source_count"] == 1


def test_knowledge_sources_filters_by_library(monkeypatch, client, admin_headers):
    calls = {}

    def fake_get_sources(library=None):
        calls["library"] = library
        return [
            {
                "source_id": "kb:test",
                "title": "询问SOP",
                "source": "file_upload",
                "category": "SOP处置",
                "library": "sop_library",
                "tags": ["询问"],
                "chunk_count": 2,
                "status": "ready",
                "chunks": [],
            }
        ]

    monkeypatch.setattr(knowledge_router.rag_service, "get_sources", fake_get_sources)

    response = client.get("/knowledge/sources?library=sop_library", headers=admin_headers)

    assert response.status_code == 200
    assert calls["library"] == "sop_library"
    assert response.json()[0]["source_id"] == "kb:test"


def test_get_knowledge_source_returns_chunks(monkeypatch, client, admin_headers):
    calls = {}

    def fake_get_sources(library=None, source_id=None, include_chunks=False):
        calls["source_id"] = source_id
        calls["include_chunks"] = include_chunks
        return [
            {
                "source_id": source_id,
                "title": "询问SOP",
                "library": "sop_library",
                "chunk_count": 1,
                "chunks": [{"id": "kb:test:chunk:0", "content": "先安抚。"}],
            }
        ]

    monkeypatch.setattr(knowledge_router.rag_service, "get_sources", fake_get_sources)

    response = client.get("/knowledge/sources/kb:test", headers=admin_headers)

    assert response.status_code == 200
    assert calls == {"source_id": "kb:test", "include_chunks": True}
    assert response.json()["chunks"][0]["id"] == "kb:test:chunk:0"


def test_delete_knowledge_source_removes_grouped_chunks(monkeypatch, client, admin_headers):
    calls = {}

    def fake_delete_by_source_id(source_id):
        calls["source_id"] = source_id
        return {
            "source_id": source_id,
            "deleted_ids": ["kb:test:chunk:0", "kb:test:chunk:1"],
            "deleted_count": 2,
        }

    monkeypatch.setattr(knowledge_router.rag_service, "delete_by_source_id", fake_delete_by_source_id)

    response = client.delete("/knowledge/sources/kb:test", headers=admin_headers)

    assert response.status_code == 200
    assert calls["source_id"] == "kb:test"
    assert response.json()["deleted_count"] == 2


def test_delete_knowledge_source_returns_404_for_missing_source(monkeypatch, client, admin_headers):
    monkeypatch.setattr(
        knowledge_router.rag_service,
        "delete_by_source_id",
        lambda source_id: {"source_id": source_id, "deleted_ids": [], "deleted_count": 0},
    )

    response = client.delete("/knowledge/sources/kb:missing", headers=admin_headers)

    assert response.status_code == 404
