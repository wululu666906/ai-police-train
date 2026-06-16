"""Tests for role/scene compact V1 services."""

from services.case_schema_service import canonicalize_person_payload, migrate_structured_data_payload
from services.role_compact_service import (
    expand_role_compact_to_person,
    infer_opening_preset,
    person_to_role_compact_view,
)
from services.scene_compact_service import build_scene_stages_from_compact, infer_training_focus


def test_opening_preset_from_archetype():
    assert infer_opening_preset({"behavior_archetype": "强硬对抗型"}) == "confrontational"


def test_expand_role_compact_derives_police_attitude():
    person = expand_role_compact_to_person(
        {
            "name": "张某",
            "behavior_archetype": "求助配合型",
            "opening_preset": "calm_cooperative",
            "boundary_primary": ["我看见对方先动手"],
            "boundary_secondary": ["其实案发前已经吵过"],
        },
        scene_behavior_mode="核查取证型",
    )
    assert person["police_attitude"] == "主动求助"
    assert person["knows_facts"] == ["我看见对方先动手"]
    assert person["hidden_truths"] == ["其实案发前已经吵过"]
    assert person["init_trust"] >= 50


def test_legacy_person_migrates_to_compact():
    legacy = {
        "name": "李某",
        "behavior_archetype": "谨慎回避型",
        "knows_facts": ["听到争吵"],
        "hidden_truths": ["不想说之前的事"],
        "does_not_know": ["谁先动手"],
    }
    canonical, _ = canonicalize_person_payload(legacy, scene_behavior_mode="核查取证型")
    assert canonical.get("compact_v1") is True
    assert canonical.get("opening_preset")
    view = person_to_role_compact_view(canonical, scene_behavior_mode="核查取证型")
    assert view["boundary_primary"]


def test_build_scene_stages_from_compact():
    stages = build_scene_stages_from_compact(
        {
            "name": "现场处置",
            "training_focus": "onsite",
            "behavior_mode": "核查取证型",
            "difficulty": "中等",
            "assessment_points": [
                {"label": "核实现场人员身份", "content": "学员应核实身份。"},
                {"label": "问清现场经过", "content": "学员应追问经过。"},
            ],
        },
        case_type="邻里/家庭纠纷",
        scene_name="现场处置",
    )
    assert len(stages) == 1
    assert stages[0]["assessment_points"]
    assert stages[0]["stage_name"] == "现场处置"
    assert stages[0]["action_catalog"]
    assert stages[0]["completion_rules"]["min_user_turns"] >= 2


def test_infer_training_focus_from_scene_name():
    assert infer_training_focus("110接警研判") == "intake"
    assert infer_training_focus("现场调解") == "mediation"


def test_build_scene_stages_infer_focus_without_admin_fields():
    stages = build_scene_stages_from_compact(
        {
            "name": "110接警研判",
            "difficulty": "中等",
            "assessment_points": [
                {"label": "核实报警来源", "content": "学员应核实报警人身份与来源。"},
            ],
        },
        case_type="邻里/家庭纠纷",
        scene_name="110接警研判",
    )
    assert len(stages) == 1
    assert stages[0]["stage_name"] == "接警研判"
    assert stages[0]["assessment_points"]
    assert stages[0]["completion_rules"]["required_point_ids"]
    assert infer_training_focus("110接警研判") == "intake"


def test_migrate_structured_data_sets_compact_schema_version():
    payload, _ = migrate_structured_data_payload({"persons": [{"name": "王某", "behavior_archetype": "求助配合型"}]})
    assert payload["schema_version"] == "2026.06.compact-v1"
    assert "compact_person_fields" in payload


def test_new_reaction_archetype_fills_runtime_persona_defaults():
    payload, _ = migrate_structured_data_payload({"persons": [{"name": "赵某", "behavior_archetype": "创伤受害型"}]})
    person = payload["persons"][0]

    assert person["behavior_archetype"] == "创伤受害型"
    assert person["trigger_points"]
    assert person["calming_points"]
    assert person["pressure_response"]
    assert person["init_risk"] >= 50
    assert person["init_expression_clarity"] <= 70
    assert "relationship_pressure" in payload["compact_person_fields"]
    assert "surface_stance" in payload["compact_person_fields"]
    assert "pressure_response" in payload["compact_person_fields"]
