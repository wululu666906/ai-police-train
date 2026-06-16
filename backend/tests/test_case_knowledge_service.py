import json
from types import SimpleNamespace

from services import case_knowledge_service as service


def _case_fixture():
    role = SimpleNamespace(
        id=7,
        name="Reporter",
        role_type="报警人",
        interaction_style="配合型",
        personality="anxious but cooperative",
        speaking_style="fast",
        init_emotion=75,
        init_trust=35,
        status="nervous",
        knows_facts=json.dumps(["saw the suspect leave", "called police at 09:30"], ensure_ascii=False),
        does_not_know=json.dumps(["weapon source"], ensure_ascii=False),
        hidden_truths=json.dumps(["argued with the suspect earlier"], ensure_ascii=False),
        weakness="family safety",
        persona_meta=json.dumps(
            {
                "answer_logic": "answer direct questions first",
                "behavior_tendency": "asks for police protection",
                "core_concern": "retaliation",
                "trigger_points": ["suspect mentioned"],
                "calming_points": ["clear protection plan"],
            },
            ensure_ascii=False,
        ),
    )
    scene = SimpleNamespace(
        id=3,
        name="Initial call",
        description="The officer receives a call from the reporter.",
        dispatch_brief="Potential assault dispute.",
        first_impression="Reporter sounds scared.",
    )
    case = SimpleNamespace(
        id=42,
        title="Warehouse assault",
        case_type="assault",
        background="A dispute escalated near a warehouse.",
        original_content="Original incident text.",
        structured_data=json.dumps(
            {
                "fact_sheet": {
                    "case_time": "09:20",
                    "case_location": "East warehouse",
                    "report_time": "09:30",
                },
                "full_narrative": "The reporter saw the suspect leave after an argument.",
                "evidence_points": ["CCTV", "injury photos"],
                "key_clues": ["red jacket"],
                "risk_points": ["suspect may return"],
            },
            ensure_ascii=False,
        ),
        scenes=[scene],
        roles=[role],
    )
    return case, role


def test_build_case_knowledge_documents_contains_case_and_role_script():
    case, _role = _case_fixture()

    docs = service.build_case_knowledge_documents(case)

    assert [doc["id"] for doc in docs] == ["case:42:info", "case:42:role:7:script"]
    assert docs[0]["metadata"]["doc_type"] == "case_info"
    assert docs[1]["metadata"]["doc_type"] == "role_script"
    assert "Warehouse assault" in docs[0]["content"]
    assert "East warehouse" in docs[0]["content"]
    assert "Reporter" in docs[1]["content"]
    assert "answer direct questions first" in docs[1]["content"]


def test_load_case_knowledge_bundle_falls_back_to_database_snapshot(monkeypatch):
    case, role = _case_fixture()

    monkeypatch.setattr(service.rag_service, "get_documents_by_ids", lambda ids: [])

    bundle = service.load_case_knowledge_bundle(case, role)

    assert bundle["documents"]
    assert "Warehouse assault" in bundle["knowledge_block"]
    assert "Reporter" in bundle["knowledge_block"]
    assert "argued with the suspect earlier" in bundle["knowledge_block"]


def test_sync_case_to_knowledge_uses_stable_ids_and_deletes_stale_docs(monkeypatch):
    case, _role = _case_fixture()
    calls = {}

    monkeypatch.setattr(
        service.rag_service,
        "get_documents_by_metadata",
        lambda where: [{"id": "case:42:role:999:script"}],
    )
    monkeypatch.setattr(service.rag_service, "delete_by_ids", lambda ids: calls.setdefault("deleted", ids))
    monkeypatch.setattr(
        service.rag_service,
        "upsert_documents",
        lambda ids, texts, metadatas: calls.setdefault("upserted", ids),
    )

    result = service.sync_case_to_knowledge(case)

    assert calls["deleted"] == ["case:42:role:999:script"]
    assert calls["upserted"] == ["case:42:info", "case:42:role:7:script"]
    assert result["synced_ids"] == calls["upserted"]
    assert result["sync_status"] == "ok"
    assert result["ok"] is True
