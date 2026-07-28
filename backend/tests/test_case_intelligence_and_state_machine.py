from services.case_intelligence_service import (
    assess_source_quality,
    build_role_knowledge_view,
    format_role_knowledge_view,
    normalize_case_intelligence,
    validate_supporting_knowledge_ids,
)
from services.hybrid_state_machine import derive_hybrid_state
from services.training_compiler_service import build_observable_scoring_rules, build_training_tasks, compile_state_machine
from services.case_schema_service import migrate_structured_data_payload


def test_legacy_facts_migrate_to_unverified_claims():
    intelligence = normalize_case_intelligence(
        {"story_world": {"fact_cards": [{"id": "F1", "content": "张某称自己没有动手"}]}}
    )
    assert intelligence["schema_version"] == 2
    assert intelligence["claims"][0]["statement"] == "张某称自己没有动手"
    assert intelligence["claims"][0]["verification_status"] == "unverified"


def test_role_view_does_not_inherit_global_case_claims():
    structured = {
        "case_intelligence": {
            "claims": [{"claim_id": "C1", "statement": "监控显示李某先动手"}],
        },
        "persons": [
            {
                "name": "王某",
                "knows_facts": ["看见两人在门口争吵"],
                "does_not_know": ["谁先动手"],
            }
        ],
    }
    view = build_role_knowledge_view(structured, role_name="王某")
    assert view["known"] == ["看见两人在门口争吵"]
    assert "监控显示李某先动手" not in format_role_knowledge_view(view)
    assert view["quality_policy"]["may_use_global_case_facts"] is False


def test_hybrid_state_uses_axes_events_and_objective_blockers():
    state = derive_hybrid_state(
        {"emotion": 82, "cooperation": 25, "risk": 81, "clarity": 48},
        phase="现场控制",
        recognized_actions=[{"label": "出示监控证据"}],
        missing_objectives=["隔离冲突双方"],
    )
    assert state["interaction_mode"] == "crisis"
    assert "evidence_presented" in state["events"]
    assert state["transition_allowed"] is False
    assert "风险尚未受控" in state["transition_blockers"]


def test_hybrid_state_hysteresis_prevents_boundary_flicker():
    previous = {"interaction_mode": "resistant"}
    state = derive_hybrid_state(
        {"emotion": 50, "cooperation": 34, "risk": 45, "clarity": 55},
        phase="询问",
        previous=previous,
    )
    assert state["interaction_mode"] == "resistant"


def test_training_compiler_keeps_stage_objectives_observable():
    tasks = build_training_tasks(
        {"case_intelligence": {"claims": [{"claim_id": "C1"}]}},
        [{"stages": [{"stage_name": "风险控制", "stage_goal": "隔离双方并确认伤情", "fact_ids": ["C1"]}]}],
    )
    machine = compile_state_machine(tasks)
    assert tasks[0]["source_claim_ids"] == ["C1"]
    assert tasks[0]["critical"] is True
    assert machine["states"][0]["on_events"]["risk_control"] == "decrease_risk"
    assert build_observable_scoring_rules(tasks)[0]["critical"] is True


def test_low_quality_source_requires_specific_uncertainty():
    quality = assess_source_quality("有人说不清楚，可能在附近。")
    assert quality["grade"] == "low"
    assert quality["policy"] == "specific_uncertainty_only"


def test_role_grounding_rejects_unknown_knowledge_ids():
    view = build_role_knowledge_view({"persons": [{"name": "王某", "knows_facts": ["看见争吵"]}]}, role_name="王某")
    assert validate_supporting_knowledge_ids(view, ["K1"])["valid"] is True
    assert validate_supporting_knowledge_ids(view, ["C999"])["invalid"] == ["C999"]


def test_role_knowledge_is_linked_to_matching_claim_source():
    view = build_role_knowledge_view({
        "case_intelligence": {"claims": [{"claim_id": "C7", "statement": "王某看见两人在门口争吵", "certainty": "source_supported", "source_refs": [{"document_id": "D1"}]}]},
        "persons": [{"name": "王某", "knows_facts": ["看见两人在门口争吵"]}],
    }, role_name="王某")
    item = view["ledger"][0]
    assert item["claim_id"] == "C7"
    assert item["source_refs"] == [{"document_id": "D1"}]


def test_legacy_case_gets_a_primary_narrative_document():
    migrated, _ = migrate_structured_data_payload({"full_narrative": "这是旧案例的连贯案情。"})
    assert migrated["narrative_document"]["content"] == "这是旧案例的连贯案情。"
    assert migrated["narrative_document"]["policy"] == "human_readable_not_canonical_fact_source"


def test_programmatic_extraction_handles_common_chinese_case_sentence():
    text = "报警人张三称其在东风路看见李四搬走电脑，现场监控录像正在调取，具体是否授权尚不确定。"
    people = workflow_people = __import__("services.workflow_service", fromlist=["workflow_service"]).workflow_service._programmatic_people(text)
    cards = __import__("services.workflow_service", fromlist=["workflow_service"]).workflow_service._programmatic_claim_cards(text)
    assert {item["name"] for item in people} == {"张三", "李四"}
    assert any(item["fact_type"] == "证据" for item in cards)
