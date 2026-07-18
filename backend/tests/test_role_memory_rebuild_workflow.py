import json

from models import Case, Role
from services.workflow_service import workflow_service


def test_legacy_case_rebuild_writes_source_memory_to_case_and_role(client, admin_headers, db_session, monkeypatch):
    case = db_session.query(Case).first()
    case.original_content = "证人韩某的证言，证实其在现场看见争执。"
    db_session.commit()

    memory = {
        "memory_id": "韩某-M1",
        "memory_type": "direct_statement",
        "statement": "证人韩某的证言，证实其在现场看见争执。",
        "quote": "证人韩某的证言，证实其在现场看见争执。",
        "certainty": "source_supported",
        "source_refs": [{"document_id": "source-1", "start": 0, "end": 18}],
    }
    monkeypatch.setattr(workflow_service, "parse_case_text_with_rule_fallback", lambda text, source_mode: {
        "persons": [{"name": "韩某", "role": "证人", "role_type": "证人", "role_memories": [memory], "knowledge_ledger": [], "response_constraints": ["只陈述原文证言"]}],
        "parse_engine": "rule_text_first",
        "generation_mode": "ai_role_checkpoint_then_story_assembly",
    })

    response = client.post(f"/cases/{case.id}/rebuild-role-memories", json={"replace_legacy_roles": True}, headers=admin_headers)
    assert response.status_code == 200, response.text

    stored = db_session.query(Case).filter(Case.id == case.id).one()
    persons = json.loads(stored.structured_data)["persons"]
    assert persons[0]["name"] == "韩某"
    assert persons[0]["role_memories"][0]["quote"] == memory["quote"]
    role = db_session.query(Role).filter(Role.case_id == case.id, Role.name == "韩某").one()
    assert json.loads(role.persona_meta)["role_memories"][0]["quote"] == memory["quote"]
