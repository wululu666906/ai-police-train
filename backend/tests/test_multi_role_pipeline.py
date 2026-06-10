"""Unit tests for director / actor / scene engine pipeline."""

from services.multi_role_director import run_director
from services.multi_role_actor import generate_role_dialogue
from services.scene_conversation_engine import consolidate_scene_conversation


class _FakeRole:
    def __init__(self, role_id: int, name: str, role_type: str = "当事人"):
        self.id = role_id
        self.name = name
        self.role_type = role_type
        self.status = "激动"
        self.init_emotion = 60
        self.init_trust = 25
        self.personality = "急躁"
        self.knows_facts = "[]"
        self.hidden_truths = "[]"
        self.does_not_know = "[]"


class _FakeScene:
    name = "纠纷调解现场"
    dispatch_brief = "建设路夜市烧烤店门口有人打架，现场人员较多，请立即处置。"
    first_impression = "赵阳捂着眉弓站在店门口，刘军坐在路边椅子上，语速快且带酒气。"
    description = "接警后到达烧烤店门口。"


class _FakeCase:
    background = "烧烤店门口因结账插队发生口角，刘军饮酒后推搡并击打赵阳面部。"
    structured_data = """{
        "persons": [
            {"name": "刘军", "role": "违法嫌疑人"},
            {"name": "赵阳", "role": "被害人"},
            {"name": "孙桂兰", "role": "证人"}
        ],
        "timeline": [
            "21:35 因结账插队发生争执",
            "21:40 刘军击打赵阳面部",
            "21:42 群众报警"
        ],
        "evidence_points": ["店内监控", "赵阳伤情照片", "孙桂兰证言"]
    }"""


def test_director_rule_plan_limits_two_speakers():
    roles = [_FakeRole(1, "张某"), _FakeRole(2, "李某")]
    plan = run_director(
        scene=_FakeScene(),
        roles=roles,
        history=[],
        user_text="你们俩都冷静一下，分别说经过",
        current_stage="现场控制",
        current_stage_goal="分离双方",
        use_llm=False,
    )
    assert plan is not None
    assert len(plan["cast_plan"]) <= 2
    assert plan["cast_plan"][0]["utterance_count"] >= 1


def test_actor_respects_utterance_count_cap():
    role = _FakeRole(1, "张某")
    cast_entry = {
        "participation": "primary_respond",
        "utterance_count": 3,
        "intent": "explain",
        "trigger_reason": "被问经过",
    }
    director_plan = {"interaction_mode": "address_named"}
    output = generate_role_dialogue(
        role=role,
        cast_entry=cast_entry,
        director_plan=director_plan,
        scene=_FakeScene(),
        case=None,
        history=[],
        user_text="说一下怎么回事",
        current_stage="询问",
        role_snapshot={"emotion": 60, "cooperation": 30, "risk": 50, "clarity": 50},
        use_llm=False,
    )
    assert 1 <= len(output["utterances"]) <= 3


def test_actor_rule_fallback_uses_case_facts_for_common_questions():
    victim = _FakeRole(1, "赵阳", "被害人")
    victim_output = generate_role_dialogue(
        role=victim,
        cast_entry={"participation": "primary_respond", "utterance_count": 2},
        director_plan={"interaction_mode": "address_named"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="赵阳，请先说明你的身份。",
        current_stage="询问",
        role_snapshot={"emotion": 60, "cooperation": 30, "risk": 50, "clarity": 50},
        use_llm=False,
    )
    victim_text = " ".join(item["content"] for item in victim_output["utterances"])
    assert "赵阳" in victim_text
    assert "被害人" in victim_text
    assert "……你问的这些" not in victim_text
    assert "反正我说的都是实话" not in victim_text

    suspect = _FakeRole(2, "刘军", "违法嫌疑人")
    suspect_output = generate_role_dialogue(
        role=suspect,
        cast_entry={"participation": "primary_respond", "utterance_count": 2},
        director_plan={"interaction_mode": "address_named"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="刘军，具体是几点发生的？",
        current_stage="询问",
        role_snapshot={"emotion": 60, "cooperation": 30, "risk": 50, "clarity": 50},
        use_llm=False,
    )
    suspect_text = " ".join(item["content"] for item in suspect_output["utterances"])
    assert "21:35" in suspect_text or "21:40" in suspect_text
    assert len(suspect_output["utterances"]) == 1
    assert "反正我说的都是实话" not in suspect_text


def test_scene_engine_merges_multiple_utterances():
    role = _FakeRole(1, "张某")
    actor_outputs = [
        {
            "speaker_name": "张某",
            "speaker_role_id": 1,
            "role": role,
            "participation": "primary_respond",
            "utterances": [{"content": "第一句"}, {"content": "第二句"}],
            "inner_thought": "紧张",
            "state_delta": {"emotion": -2, "cooperation": 2, "risk": 0, "clarity": 1},
            "new_fact_revealed": None,
            "updated_snapshot": {"emotion": 58, "cooperation": 32, "risk": 50, "clarity": 51},
        }
    ]
    director_plan = {"interaction_mode": "address_named", "routing_summary": "测试", "cast_plan": []}
    snapshots = {"1": {"emotion": 60, "cooperation": 30, "risk": 50, "clarity": 50}}
    merged = consolidate_scene_conversation(
        director_plan=director_plan,
        actor_outputs=actor_outputs,
        role_snapshots=snapshots,
        previous_primary_role=role,
    )
    assert len(merged["reply_turns"]) == 2
    assert merged["reply_turns"][0]["speaker_name"] == "张某"
    assert snapshots["1"]["cooperation"] == 32
