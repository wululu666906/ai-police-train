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


class _FakeMessage:
    def __init__(self, role: str, content: str, speaker_name: str = ""):
        self.role = role
        self.content = content
        self.speaker_name = speaker_name
        self.inner_thought = ""


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


def test_actor_reacts_to_peer_utterance_like_argument():
    suspect = _FakeRole(2, "刘军", "违法嫌疑人")
    output = generate_role_dialogue(
        role=suspect,
        cast_entry={"participation": "interrupt", "utterance_count": 2, "intent": "defend"},
        director_plan={"interaction_mode": "interrupt_chain", "scene_mood": "tense"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="你们双方都说一下怎么回事",
        current_stage="调解",
        role_snapshot={"emotion": 85, "cooperation": 18, "risk": 78, "clarity": 62},
        peer_utterances=[
            {
                "speaker_name": "赵阳",
                "utterances": [{"content": "就是刘军先动手打我的。"}],
            }
        ],
        use_llm=False,
    )
    text = " ".join(item["content"] for item in output["utterances"])
    assert output["reaction_type"] in {"argumentative_dispute", "provocative_challenge"}
    assert "不是" in text or "认定" in text or "责任" in text
    assert output["updated_snapshot"]["risk"] >= 78


def test_actor_low_cooperation_witness_uses_avoidant_reaction():
    witness = _FakeRole(3, "孙桂兰", "证人")
    output = generate_role_dialogue(
        role=witness,
        cast_entry={"participation": "primary_respond", "utterance_count": 2, "intent": "witness_account"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "deadlock"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="孙桂兰，你看到什么就说什么",
        current_stage="询问",
        role_snapshot={"emotion": 45, "cooperation": 18, "risk": 45, "clarity": 70},
        use_llm=False,
    )
    text = " ".join(item["content"] for item in output["utterances"])
    assert output["reaction_type"] == "avoidant_silence"
    assert "不敢" in text or "确定" in text or "掺和" in text


def test_actor_can_have_multiple_reactions_in_one_turn():
    suspect = _FakeRole(2, "刘军", "违法嫌疑人")
    suspect.hidden_truths = '["先动手击打赵阳面部"]'
    output = generate_role_dialogue(
        role=suspect,
        cast_entry={"participation": "primary_respond", "utterance_count": 3, "intent": "defend"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "deadlock"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="监控和伤情都在，你还想私了赔偿吗？这事会不会影响你家属？",
        current_stage="询问",
        role_snapshot={"emotion": 72, "cooperation": 18, "risk": 76, "clarity": 58},
        use_llm=False,
    )
    reaction_types = output.get("reaction_types") or []
    assert len(reaction_types) >= 2
    assert "defensive_denial" in reaction_types
    assert "topic_shift_bargain" in reaction_types
    assert output["reaction_type"] == reaction_types[0]


def test_actor_extreme_loss_control_does_not_repeat_previous_line():
    role = _FakeRole(2, "刘军", "违法嫌疑人")
    repeated = "你先别靠太近……我听见了，你一句一句说，别一上来就围着我。"
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 1, "intent": "respond"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "edge_loss_control"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[_FakeMessage("assistant", repeated, "刘军")],
        user_text="你先冷静，别激动，我在听你说。",
        current_stage="现场控制",
        role_snapshot={"emotion": 100, "cooperation": 0, "risk": 96, "clarity": 0},
        use_llm=False,
    )
    contents = [item["content"] for item in output["utterances"]]
    assert contents
    assert repeated not in contents
    assert any("脑子" in item or "缓" in item or "别吼我" in item for item in contents)
