from services.rag_service import (
    CASE_LIBRARY,
    LAW_LIBRARY,
    ROLE_LIBRARY,
    SOP_LIBRARY,
    RAGService,
)


def test_split_text_uses_overlap_and_stable_chunk_metadata():
    text = "第一段。" * 120

    chunks = RAGService.split_text(text, chunk_size=220, overlap=40)

    assert len(chunks) > 1
    assert chunks[0].index == 0
    assert chunks[1].start < chunks[0].end
    assert all(chunk.content for chunk in chunks)


def test_normalize_library_detects_case_role_law_and_sop():
    assert RAGService.normalize_library("case_library", source="case_library", doc_type="case_info") == CASE_LIBRARY
    assert RAGService.normalize_library("", source="case_library", doc_type="role_script") == ROLE_LIBRARY
    assert RAGService.normalize_library("", category="法律法规") == LAW_LIBRARY
    assert RAGService.normalize_library("", category="接警流程") == SOP_LIBRARY


def test_ingest_text_builds_chunk_ids_and_normalized_metadata(monkeypatch):
    service = object.__new__(RAGService)
    captured = {}

    def fake_upsert(ids, texts, metadatas):
        captured["ids"] = ids
        captured["texts"] = texts
        captured["metadatas"] = metadatas
        return ids

    monkeypatch.setattr(service, "upsert_documents", fake_upsert)

    result = service.ingest_text(
        "受害人拒绝配合时，应先安抚情绪，再说明调查目的。" * 20,
        title="询问流程",
        source="manual",
        category="SOP处置",
        tags=["询问", "安抚"],
        chunk_size=240,
        overlap=30,
    )

    assert result["chunks"] == len(captured["ids"])
    assert all(item_id.startswith(result["source_id"]) for item_id in captured["ids"])
    assert captured["metadatas"][0]["library"] == SOP_LIBRARY
    assert captured["metadatas"][0]["tags"] == "询问,安抚"


def test_build_context_block_downgrades_to_empty_on_search_error(monkeypatch):
    service = object.__new__(RAGService)

    def fail_search(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "search_items", fail_search)

    result = service.build_context_block("受害人拒绝配合")

    assert result["hits"] == []
    assert result["context_block"] == ""
    assert "boom" in result["error"]


def test_rows_from_chroma_results_supports_metadata_only_listing():
    service = object.__new__(RAGService)

    rows = service._rows_from_chroma_results(
        {
            "ids": ["source-a:chunk:0", "source-b:chunk:0"],
            "metadatas": [
                {"title": "A", "source": "manual", "library": LAW_LIBRARY},
                {"title": "B", "source": "file_upload", "library": SOP_LIBRARY},
            ],
        }
    )

    assert [row["id"] for row in rows] == ["source-a:chunk:0", "source-b:chunk:0"]
    assert rows[0]["content"] == ""
    assert rows[1]["library"] == SOP_LIBRARY
