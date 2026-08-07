from services.training_compiler_service import build_training_tasks
from services.workflow_service import workflow_service


def test_scene_blueprints_preserve_dimension_specific_facts_and_roles():
    persons = [
        {"name": "Alpha", "status": "normal", "role_memories": []},
        {"name": "Bravo", "status": "normal", "role_memories": []},
        {"name": "Charlie", "status": "normal", "role_memories": []},
    ]
    story_world = {
        "fact_cards": [
            {"id": "F1", "content": "Alpha reports at the scene", "source_refs": [{"start": 10}]},
            {"id": "F2", "content": "Bravo argues with Alpha", "source_refs": [{"start": 20}]},
            {"id": "F3", "content": "Charlie gives a witness statement", "source_refs": [{"start": 30}]},
            {"id": "F4", "content": "Bravo accepts follow-up questioning", "source_refs": [{"start": 40}]},
        ],
        "person_cards": [],
    }
    blueprints = [
        {
            "scene_name": "Scene response",
            "portfolio_role": "primary",
            "training_entry_phase": "post_incident_onsite",
            "training_goal": "Control the scene",
            "roles": ["Alpha", "Bravo"],
            "fact_ids": ["F1", "F2"],
            "stages": [{"stage_name": "Control", "stage_goal": "Control the scene"}],
        },
        {
            "scene_name": "Witness check",
            "portfolio_role": "investigation",
            "training_entry_phase": "post_incident_inquiry",
            "training_goal": "Verify testimony",
            "roles": ["Bravo", "Charlie"],
            "fact_ids": ["F3", "F4"],
            "stages": [{"stage_name": "Verify", "stage_goal": "Verify testimony"}],
        },
    ]

    scoped = workflow_service._scope_scene_blueprints(blueprints, {"persons": persons}, story_world)

    assert len(scoped) == 2
    assert set(scoped[0]["fact_ids"]).isdisjoint(scoped[1]["fact_ids"])
    assert set(scoped[0]["fact_ids"] + scoped[1]["fact_ids"]) == {"F1", "F2", "F3", "F4"}
    assert scoped[0]["roles"] == ["Alpha", "Bravo"]
    assert scoped[1]["roles"] == ["Bravo", "Charlie"]


def test_training_tasks_fall_back_to_own_scene_facts_not_case_facts():
    tasks = build_training_tasks(
        {"case_intelligence": {"claims": [{"claim_id": "F1"}, {"claim_id": "F2"}]}},
        [{"fact_ids": ["F9"], "stages": [{"stage_name": "Verify", "stage_goal": "Verify testimony"}]}],
    )

    assert tasks[0]["source_claim_ids"] == ["F9"]


def test_story_binding_removes_all_case_roster_from_every_scene():
    persons = [
        {"name": "甲某", "status": "正常", "role_memories": []},
        {"name": "乙某", "status": "正常", "role_memories": []},
        {"name": "丙某", "status": "正常", "role_memories": []},
    ]
    story_world = {
        "fact_cards": [
            {"id": "F1", "content": "甲某报警称现场发生争执", "source_refs": [{"start": 10}]},
            {"id": "F2", "content": "乙某称其没有参与争执", "source_refs": [{"start": 20}]},
            {"id": "F3", "content": "证人丙某陈述其目击经过", "source_refs": [{"start": 30}]},
        ],
    }
    all_roles = ["甲某", "乙某", "丙某"]
    scenes = [
        {"scene_name": "现场先期处置", "roles": all_roles, "fact_ids": ["F1", "F2", "F3"], "stages": [{"stage_name": "处置", "stage_goal": "控制现场"}]},
        {"scene_name": "关键证人询问", "roles": all_roles, "fact_ids": ["F1", "F2", "F3"], "stages": [{"stage_name": "询问", "stage_goal": "核查证言"}]},
        {"scene_name": "嫌疑人讯问", "roles": all_roles, "fact_ids": ["F1", "F2", "F3"], "stages": [{"stage_name": "讯问", "stage_goal": "核实供述"}]},
    ]

    bound = workflow_service._bind_scene_people_to_story({"persons": persons}, scenes, story_world)

    assert all(scene["roles"] != all_roles for scene in bound)
    assert set(bound[0]["fact_ids"]).isdisjoint(bound[1]["fact_ids"])
    assert set(bound[1]["fact_ids"]).isdisjoint(bound[2]["fact_ids"])
