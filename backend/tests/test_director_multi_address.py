"""Director must schedule all explicitly addressed roles (not only primary interlocutor)."""

from services.multi_role_director import _enforce_cast_plan, _rule_based_director_plan, run_director
from services.multi_role_service import partition_addressed_roles


class _Role:
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name
        self.role_type = "证人"
        self.status = "正常"
        self.init_emotion = 50
        self.init_trust = 30


class _Scene:
    name = "重点询问"


def test_rule_plan_schedules_two_named_roles():
    roles = [_Role(1, "孙桂兰"), _Role(2, "周凯"), _Role(3, "刘军")]
    plan = _rule_based_director_plan("孙桂兰、周凯你们两个说句话", roles, [roles[0], roles[1]], None)
    names = [item["speaker_name"] for item in plan["cast_plan"]]
    assert names == ["孙桂兰", "周凯"]


def test_enforce_cast_plan_replaces_wrong_primary_speaker():
    roles = [_Role(1, "孙桂兰"), _Role(2, "周凯"), _Role(3, "刘军")]
    wrong_plan = {
        "interaction_mode": "address_named",
        "routing_summary": "错误",
        "cast_plan": [
            {
                "speaker_name": "刘军",
                "speaker_role_id": 3,
                "role": roles[2],
                "participation": "primary_respond",
                "utterance_count": 1,
            }
        ],
    }
    fixed = _enforce_cast_plan(
        wrong_plan,
        addressed=[roles[0], roles[1]],
        roles=roles,
        user_text="孙桂兰、周凯你们两个说句话",
    )
    names = [item["speaker_name"] for item in fixed["cast_plan"]]
    assert names == ["孙桂兰", "周凯"]


def test_single_address_zhaoyang_not_primary_witness():
    roles = [_Role(1, "孙桂兰"), _Role(2, "赵阳"), _Role(3, "刘军")]
    plan = run_director(
        scene=_Scene(),
        roles=roles,
        history=[],
        user_text="赵阳，你的伤怎么样",
        current_stage="询问",
        current_stage_goal="核实伤情",
        use_llm=False,
    )
    assert plan["cast_plan"][0]["speaker_name"] == "赵阳"


def test_off_scene_name_routes_witness_not_impersonation():
    scene_roles = [_Role(1, "孙桂兰")]
    case_roles = [_Role(1, "孙桂兰"), _Role(2, "赵阳"), _Role(3, "刘军")]
    on_scene, off_scene = partition_addressed_roles("赵阳，你的伤怎么样", scene_roles, case_roles)
    assert on_scene == []
    assert [role.name for role in off_scene] == ["赵阳"]
    plan = run_director(
        scene=_Scene(),
        roles=scene_roles,
        history=[],
        user_text="赵阳，你的伤怎么样",
        current_stage="询问",
        current_stage_goal="核实伤情",
        case_roles=case_roles,
        use_llm=False,
    )
    assert plan["cast_plan"][0]["speaker_name"] == "孙桂兰"
    assert plan["cast_plan"][0].get("intent") == "witness_account"
    assert "addressing_warning" in plan


def test_run_director_without_llm_for_double_address():
    roles = [_Role(1, "孙桂兰"), _Role(2, "周凯"), _Role(3, "刘军")]
    plan = run_director(
        scene=_Scene(),
        roles=roles,
        history=[],
        user_text="孙桂兰、周凯你们两个说句话",
        current_stage="询问",
        current_stage_goal="固定证言",
        use_llm=False,
    )
    names = [item["speaker_name"] for item in plan["cast_plan"]]
    assert names == ["孙桂兰", "周凯"]
