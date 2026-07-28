from services.case_schema_service import canonicalize_person_payload
from services.workflow_service import workflow_service


def test_explicit_testimony_heading_keeps_full_raw_block_for_role_memory():
    text = (
        "11. 证人张三的证言，证实其于2011年7月18日晚看见李四来到现场。"
        "张三还称双方随后发生争执，直至民警到场才散开。\n"
        "12. 证人王五的证言，证实其只听见争吵声，未看清是谁先动手。"
    )
    people = workflow_service._programmatic_people(text)
    assert {item["name"] for item in people} == {"张三", "王五"}

    reconstruction = workflow_service._build_role_memories_and_case_flow(
        text,
        people,
        workflow_service._programmatic_claim_cards(text),
    )

    zhang_memory = reconstruction["role_memories"]["张三"][0]
    wang_memory = reconstruction["role_memories"]["王五"][0]
    assert zhang_memory["quote"].startswith("11. 证人张三的证言")
    assert "直至民警到场才散开" in zhang_memory["statement"]
    assert "证人王五" not in zhang_memory["statement"]
    assert wang_memory["quote"].startswith("12. 证人王五的证言")
    assert zhang_memory["source_refs"][0]["start"] == text.index("11. 证人张三")


def test_source_memory_schema_migration_preserves_memory_and_ledger():
    source = {
        "name": "张三",
        "role_template_version": "source_memory_v2",
        "role_memories": [{"memory_id": "张三-M1", "statement": "证人张三的证言，证实其在场。"}],
        "knowledge_ledger": [{"knowledge_id": "张三-M1", "content": "证人张三的证言，证实其在场。"}],
        "response_constraints": ["只依据本人原文证言回答。"],
    }

    result, warnings = canonicalize_person_payload(source)
    assert not warnings
    assert result["role_memories"] == source["role_memories"]
    assert result["knowledge_ledger"] == source["knowledge_ledger"]
    assert result["response_constraints"] == source["response_constraints"]


def test_numbered_anonymous_testimony_creates_the_speaker_and_only_their_memory():
    text = (
        "12. 证人韩某的证言，证实2011年7月18日晚上，黎某1、黎某2到牛某处搬床板。"
        "9点左右，黎某2回寨上称黎某1被打伤在山上。"
    )
    people = workflow_service._programmatic_people(text)
    names = {item["name"] for item in people}
    assert {"韩某", "黎某1", "黎某2"}.issubset(names)

    reconstruction = workflow_service._build_role_memories_and_case_flow(
        text,
        people,
        workflow_service._programmatic_claim_cards(text),
    )
    assert reconstruction["role_memories"]["韩某"][0]["statement"] == text
    assert reconstruction["role_memories"]["黎某1"] == []
    assert reconstruction["role_memories"]["黎某2"] == []
