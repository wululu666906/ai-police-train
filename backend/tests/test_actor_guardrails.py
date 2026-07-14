from services.multi_role_actor import (
    _build_role_brain,
    _format_role_brain_block,
    _sanitize_identity_confusion,
    _sanitize_topic_fixation,
    generate_role_dialogue,
)
from services.training_runtime_service import dump_runtime_state, load_runtime_state


def test_general_identity_terms_are_removed_without_anchor_support():
    role = type("Role", (), {"name": "刘军", "role_type": "违法嫌疑人"})()
    cleaned = _sanitize_identity_confusion(
        [{"content": "我是证人，也是他爸爸和同事。", "delivery": "normal"}],
        role=role,
        identity_anchor="- 当前发言人姓名：刘军\n- 当前发言人角色类型：违法嫌疑人",
    )
    text = cleaned[0]["content"]
    assert "证人" not in text
    assert "爸爸" not in text
    assert "同事" not in text


class _FakeRole:
    def __init__(self, role_id: int, name: str, role_type: str = "当事人"):
        self.id = role_id
        self.name = name
        self.role_type = role_type
        self.status = "正常"
        self.init_emotion = 60
        self.init_trust = 25
        self.personality = "急躁"
        self.knows_facts = "[]"
        self.hidden_truths = "[]"
        self.does_not_know = "[]"
        self.persona_meta = "{}"
        self.interaction_style = "对抗型"
        self.speaking_style = "口语化"
        self.weakness = ""


class _FakeScene:
    name = "纠纷调解现场"
    dispatch_brief = "夜市门口有人打架。"
    first_impression = "双方仍在争执。"


class _FakeCase:
    background = "夜市门口因排队发生口角后动手。"
    structured_data = """{
        "persons": [
            {"name": "刘军", "role": "违法嫌疑人"},
            {"name": "赵阳", "role": "被害人"}
        ],
        "timeline": ["21:35 因排队发生争执", "21:40 双方推搡"],
        "evidence_points": ["店内监控"]
    }"""


class _FakeMessage:
    def __init__(self, role: str, content: str, speaker_name: str = ""):
        self.role = role
        self.content = content
        self.speaker_name = speaker_name
        self.inner_thought = ""


def test_topic_fixation_shifts_when_user_asks_new_topic():
    role = _FakeRole(2, "刘军", "违法嫌疑人")
    history = [
        _FakeMessage("assistant", "这事就是他们先动手。", "刘军"),
        _FakeMessage("assistant", "我已经说过了，是他们先动手。", "刘军"),
    ]
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 2, "intent": "defend"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "tense"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=history,
        user_text="那你再说一下地点。",
        current_stage="调解",
        role_snapshot={"emotion": 70, "cooperation": 20, "risk": 64, "clarity": 58},
        use_llm=False,
    )
    text = " ".join(item["content"] for item in output["utterances"])
    assert "地点" in text or "哪里" in text or "位置" in text


def test_topic_fixation_replaces_wrong_old_topic():
    role = _FakeRole(2, "刘军", "违法嫌疑人")
    history = [
        _FakeMessage("assistant", "地点就在门口。", "刘军"),
        _FakeMessage("assistant", "地点我刚说过了。", "刘军"),
    ]
    cleaned = _sanitize_topic_fixation(
        [{"content": "地点是在门口，我是在旁边看到的。", "delivery": "normal"}],
        role=role,
        history=history,
        user_text="你哥哪里在诬赖你？",
        role_brain={"last_topics": ["地点", "地点"]},
    )
    assert "地点是在门口" not in cleaned[0]["content"]


def test_sibling_terms_are_removed_without_identity_support():
    role = _FakeRole(2, "刘军", "违法嫌疑人")
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 2, "intent": "defend"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "tense"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="你和对方是什么关系？",
        current_stage="调解",
        role_snapshot={"emotion": 70, "cooperation": 20, "risk": 64, "clarity": 58},
        use_llm=False,
    )
    text = " ".join(item["content"] for item in output["utterances"])
    assert "哥哥" not in text and "弟弟" not in text


def test_role_brains_bind_each_character_separately():
    witness = _FakeRole(31, "WitnessA", "证人")
    suspect = _FakeRole(32, "SuspectB", "违法嫌疑人")
    witness_brain = _build_role_brain(role=witness, case=_FakeCase(), scene=_FakeScene())
    suspect_brain = _build_role_brain(role=suspect, case=_FakeCase(), scene=_FakeScene())

    assert witness_brain["brain_id"] != suspect_brain["brain_id"]
    assert witness_brain["role_id"] == 31
    assert suspect_brain["role_id"] == 32
    assert witness_brain["role_name"] == "WitnessA"
    assert suspect_brain["role_name"] == "SuspectB"
    assert "证人" in witness_brain["allowed_identity_terms"]
    assert "违法嫌疑人" in suspect_brain["allowed_identity_terms"]
    assert "SuspectB" not in _format_role_brain_block(witness_brain)


def test_role_brain_allowlist_ignores_rule_text_examples():
    role = _FakeRole(33, "MainOffender", "主犯")
    brain = _build_role_brain(role=role, case=_FakeCase(), scene=_FakeScene())

    assert "嫌疑人" in brain["allowed_identity_terms"]
    assert "证人" not in brain["allowed_identity_terms"]
    assert "朋友" not in brain["allowed_identity_terms"]
    assert "同事" not in brain["allowed_identity_terms"]


def test_role_brain_identity_allowlist_blocks_other_body_labels():
    role = _FakeRole(41, "RoleB", "当事人")
    cleaned = _sanitize_identity_confusion(
        [{"content": "我是证人，也是他哥哥和店员。", "delivery": "normal"}],
        role=role,
        identity_anchor="- 当前发言人姓名：RoleB\n- 当前发言人角色类型：当事人",
        role_brain={"role_name": "RoleB", "allowed_identity_terms": ["当事人"]},
    )
    text = cleaned[0]["content"]
    assert "证人" not in text
    assert "哥哥" not in text
    assert "店员" not in text


def test_runtime_state_persists_independent_role_brains():
    state = load_runtime_state({})
    state["role_brains"] = {
        "1": {"role_id": 1, "role_name": "Alpha", "brain_id": "role:1", "last_topics": ["身份"]},
        "2": {"role_id": 2, "role_name": "Beta", "brain_id": "role:2", "last_topics": ["时间"]},
    }
    reloaded = load_runtime_state(dump_runtime_state(state))

    assert reloaded["role_brains"]["1"]["role_name"] == "Alpha"
    assert reloaded["role_brains"]["2"]["role_name"] == "Beta"
    assert reloaded["role_brains"]["1"]["brain_id"] != reloaded["role_brains"]["2"]["brain_id"]
