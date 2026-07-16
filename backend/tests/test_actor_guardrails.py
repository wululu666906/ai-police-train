from services.multi_role_actor import (
    _build_role_brain,
    _format_role_brain_block,
    _role_case_evidence,
    _sanitize_identity_confusion,
    _sanitize_meta_dialogue,
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
    assert "夜市门口" in text or "门口" in text or "地点" in text or "哪里" in text or "位置" in text
    assert "先动手" not in text


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


def test_unsupported_kinship_variants_are_removed_from_a_role_claim():
    role = _FakeRole(42, "周德静", "主犯")
    cleaned = _sanitize_identity_confusion(
        [{"content": "他是我亲哥，我怎么会对他有意见。", "delivery": "normal"}],
        role=role,
        identity_anchor="- 当前发言人姓名：周德静\n- 当前发言人角色类型：主犯",
        role_brain={"role_name": "周德静", "allowed_identity_terms": []},
    )

    text = cleaned[0]["content"]
    assert "亲哥" not in text
    assert "哥哥" not in text
    assert "关系我不乱认" in text


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


def test_role_brain_persists_only_its_own_private_turn():
    role = _FakeRole(43, "周德静", "主犯")
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 1, "intent": "respond"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "stable"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="你当时看到了什么？",
        current_stage="询问",
        role_snapshot={"emotion": 50, "cooperation": 30, "risk": 45, "clarity": 60},
        use_llm=False,
    )

    private_turns = output["role_brain"]["private_turns"]
    assert len(private_turns) == 1
    assert private_turns[0]["learner_text"] == "你当时看到了什么？"


def test_role_brain_keeps_other_role_words_as_public_observations_only():
    role = _FakeRole(44, "周德静", "主犯")
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "supplement", "utterance_count": 1, "intent": "respond"},
        director_plan={"interaction_mode": "public_question", "scene_mood": "stable"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="你们分别说一下情况。",
        current_stage="询问",
        role_snapshot={"emotion": 50, "cooperation": 30, "risk": 45, "clarity": 60},
        peer_utterances=[
            {
                "speaker_name": "周德宁",
                "speaker_role_id": 45,
                "utterances": [{"content": "我当时没跟着大家走。"}],
            }
        ],
        use_llm=False,
    )

    brain = output["role_brain"]
    assert brain["public_observations"][-1]["speaker_name"] == "周德宁"
    assert brain["public_observations"][-1]["content"] == "我当时没跟着大家走。"
    assert all("没跟着大家走" not in item for item in brain["last_self_utterances"])


def test_role_brain_keeps_own_fact_bucket_separate_from_shared_case_facts():
    role = _FakeRole(46, "周德静", "主犯")
    role.knows_facts = '["我在村口看见有人集合"]'
    brain = _build_role_brain(role=role, case=_FakeCase(), scene=_FakeScene())

    assert "我在村口看见有人集合" in brain["known_facts"]
    assert "我在村口看见有人集合" not in brain["shared_case_facts"]


def test_role_case_evidence_is_scoped_to_the_current_role_name():
    role = _FakeRole(47, "周德静", "主犯")
    case = type(
        "Case",
        (),
        {
            "background": "周德宁称自己在村后山除草。周德静称现场太乱，没有跟着人群跑。",
            "structured_data": "{}",
        },
    )()

    evidence = _role_case_evidence(role, case)

    assert evidence
    assert all("周德静" in item for item in evidence)
    assert not any("周德宁称自己在村后山除草" in item for item in evidence)


def test_screenshot_safety_question_stays_in_character_and_answers_risk():
    role = _FakeRole(48, "周德俐", "主犯")
    history = [
        _FakeMessage("assistant", "责任不是我一个人的。", "周德俐"),
        _FakeMessage("assistant", "他们不能都怪到我头上。", "周德俐"),
        _FakeMessage("assistant", "我没想推卸责任。", "周德俐"),
    ]
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 1, "intent": "respond"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "tense"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=history,
        user_text="周德俐，现场现在还有危险吗？",
        current_stage="现场控制",
        role_snapshot={"emotion": 65, "cooperation": 25, "risk": 70, "clarity": 58},
        role_brain={"recent_response_topics": ["责任", "责任", "责任"]},
        use_llm=False,
    )

    text = " ".join(item["content"] for item in output["utterances"])
    assert any(token in text for token in ("危险", "人群", "散开", "东西", "动手"))
    for forbidden in ("换个角度", "绕在同一个点", "你问具体点", "你先问", "拆开"):
        assert forbidden not in text


def test_scoreable_guidance_changes_role_state_and_gets_a_small_acknowledgement():
    role = _FakeRole(49, "杨某甲", "被害人")
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 2, "intent": "vent"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "deescalate"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="你别着急，我们慢慢说，我现在就过去帮你处理。",
        current_stage="现场控制",
        role_snapshot={"emotion": 72, "cooperation": 20, "risk": 72, "clarity": 52},
        recognized_actions=[{"label": "安抚并承诺处置"}],
        use_llm=False,
    )

    text = " ".join(item["content"] for item in output["utterances"])
    assert output["updated_snapshot"]["cooperation"] > 20
    assert output["reaction_type"] == "guided_acknowledgement"
    assert output["guidance_recognized"] is True
    assert output["guidance_acknowledged"] is True
    assert "听见" in text or "愿意过去" in text or "说清楚" in text


def test_meta_guardrail_wording_is_never_visible_in_role_speech():
    role = _FakeRole(55, "周德俐", "当事人")
    cleaned = _sanitize_meta_dialogue(
        [
            {"content": "这件事我先换个角度说，别一直绕在同一个点上。", "delivery": "normal"},
            {"content": "你先把问题拆开，我能答清楚。", "delivery": "normal"},
        ],
        role=role,
        user_text="现在意识清楚吗？说一下你看到的情况。",
    )

    text = " ".join(item["content"] for item in cleaned)
    assert "换个角度" not in text
    assert "拆开" not in text
    assert "绕在同一个点" not in text
    assert "看到" in text or "受伤" in text or "现场" in text


def test_extreme_loss_control_uses_character_speech_not_question_coaching():
    role = _FakeRole(56, "周德俐", "当事人")
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 1, "intent": "respond"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "edge_loss_control"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="现在意识清楚吗？说一下你看到的情况。",
        current_stage="现场控制",
        role_snapshot={"emotion": 100, "cooperation": 0, "risk": 96, "clarity": 0},
        use_llm=False,
    )

    text = " ".join(item["content"] for item in output["utterances"])
    for forbidden in ("换个角度", "拆开", "你先问", "别让我重复", "绕在同一个点"):
        assert forbidden not in text


def test_new_learner_topic_overrides_a_role_fixating_on_old_responsibility():
    role = _FakeRole(57, "周德俐", "当事人")
    history = [
        _FakeMessage("assistant", "明明是他先动手，还想把责任推给我。", "周德俐"),
        _FakeMessage("assistant", "我没有栽赃，别把这事都算在我头上。", "周德俐"),
        _FakeMessage("assistant", "责任不是我一个人的，他也动手了。", "周德俐"),
    ]
    cleaned = _sanitize_topic_fixation(
        [{"content": "他先动手，你们别老说是我的责任。", "delivery": "defensive"}],
        role=role,
        history=history,
        user_text="现在意识清楚吗？说一下你看到的情况。",
        role_brain={"recent_response_topics": ["责任", "责任", "责任"]},
    )

    text = cleaned[0]["content"]
    assert "责任" not in text
    assert "受伤" in text or "回应" in text or "头上" in text


def test_rule_actor_does_not_bring_up_compensation_for_a_time_question():
    role = _FakeRole(58, "刘军", "违法嫌疑人")
    role.hidden_truths = '["先动手"]'
    output = generate_role_dialogue(
        role=role,
        cast_entry={"participation": "primary_respond", "utterance_count": 2, "intent": "defend"},
        director_plan={"interaction_mode": "address_named", "scene_mood": "tense"},
        scene=_FakeScene(),
        case=_FakeCase(),
        history=[],
        user_text="事情是几点发生的？",
        current_stage="询问",
        role_snapshot={"emotion": 70, "cooperation": 20, "risk": 65, "clarity": 55},
        use_llm=False,
    )

    text = " ".join(item["content"] for item in output["utterances"])
    assert "赔" not in text
    assert "21:35" in text or "21:40" in text or "时间" in text
