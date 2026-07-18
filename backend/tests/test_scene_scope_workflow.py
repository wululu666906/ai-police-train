from services.training_compiler_service import build_training_tasks
from services.workflow_service import workflow_service


def test_scene_blueprints_partition_case_facts_and_roles_by_scope():
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
            "training_goal": "Control the scene",
            "roles": ["Alpha", "Bravo", "Charlie"],
            "fact_ids": ["F1", "F2", "F3", "F4"],
            "stages": [{"stage_name": "Control", "stage_goal": "Control the scene"}],
        },
        {
            "scene_name": "Witness check",
            "training_goal": "Verify testimony",
            "roles": ["Alpha", "Bravo", "Charlie"],
            "fact_ids": ["F1", "F2", "F3", "F4"],
            "stages": [{"stage_name": "Verify", "stage_goal": "Verify testimony"}],
        },
    ]

    scoped = workflow_service._scope_scene_blueprints(blueprints, {"persons": persons}, story_world)

    assert len(scoped) == 2
    assert set(scoped[0]["fact_ids"]).isdisjoint(scoped[1]["fact_ids"])
    assert set(scoped[0]["fact_ids"] + scoped[1]["fact_ids"]) == {"F1", "F2", "F3", "F4"}
    assert scoped[0]["roles"] != ["Alpha", "Bravo", "Charlie"]


def test_training_tasks_fall_back_to_own_scene_facts_not_case_facts():
    tasks = build_training_tasks(
        {"case_intelligence": {"claims": [{"claim_id": "F1"}, {"claim_id": "F2"}]}},
        [{"fact_ids": ["F9"], "stages": [{"stage_name": "Verify", "stage_goal": "Verify testimony"}]}],
    )

    assert tasks[0]["source_claim_ids"] == ["F9"]
