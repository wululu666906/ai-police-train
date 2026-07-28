from services.canonical_facts_service import extract_canonical_facts, format_canonical_facts_block, merge_role_knows_facts
from services.dialogue_sanitize_service import (
    repair_learner_echoed_spoken_line,
    repair_repetitive_spoken_line,
    sanitize_spoken_line,
    sanitize_utterances,
)


def test_sanitize_template_leakage():
    raw = "我最怕的就是担心被报复，你们先听我说行不行？"
    cleaned = sanitize_spoken_line(raw)
    assert "我最怕的就是" not in cleaned
    assert "核心顾虑" not in cleaned


def test_sanitize_information_boundary_template_leakage_as_a_whole_line():
    cleaned = sanitize_spoken_line("我的信息边界是只能回答亲眼看到的，当前诉求是尽快离开。")

    assert "信息边界" not in cleaned
    assert "当前诉求" not in cleaned
    assert "只能说自己" in cleaned or "不乱讲" in cleaned


def test_repetition_repair_never_coaches_the_learner_how_to_ask():
    repaired, changed = repair_repetitive_spoken_line(
        "我刚才已经说过了。",
        ["我刚才已经说过了。"],
        "现在意识清楚吗？说一下你看到的情况。",
    )

    assert changed is True
    assert "你再问" not in repaired
    assert "拆开" not in repaired
    assert "换个问法" not in repaired


def test_visible_role_line_removes_coaching_and_turn_management_variants():
    variants = [
        "这件事我先换个角度说，别一直绕在同一个点上。",
        "你还没问，我就先换个说法，省得你误会我。",
        "你问具体点，是想问谁先动的手，还是问我拿没拿东西？",
        "你先把问题拆开，我能答清楚。",
    ]

    for raw in variants:
        cleaned = sanitize_spoken_line(raw)
        for forbidden in ("换个角度", "换个说法", "绕在同一个点", "你问具体点", "你先把问题", "拆开"):
            assert forbidden not in cleaned


def test_role_reply_does_not_parrot_the_learner_instruction():
    learner = "报不清怎么赔嘛，你也不想他们赔少了吧，先算是。"
    repaired = repair_learner_echoed_spoken_line(learner, learner)

    assert repaired != learner
    assert "具体数我一时算不清" in repaired


def test_fallback_opening_no_meta_phrase():
    from services.opening_turn_service import _fallback_opening_utterances

    utterances = _fallback_opening_utterances(
        {
            "role_name": "陈建国",
            "incident_hints": "肇事逃逸",
            "core_concern": "担心被报复",
        }
    )
    joined = " ".join(item["content"] for item in utterances)
    assert "我最怕的就是" not in joined


def test_canonical_facts_block_uses_fact_sheet():
    class Case:
        structured_data = '{"fact_sheet": {"case_time": "昨晚22:10", "case_location": "建设路与新华街交叉口"}}'

    facts = extract_canonical_facts(Case())
    assert facts["case_time"] == "昨晚22:10"
    assert facts["case_location"] == "建设路与新华街交叉口"
    block = format_canonical_facts_block(Case())
    assert "建设路与新华街交叉口" in block


def test_merge_role_knows_facts_injects_time_location():
    class Role:
        role_type = "报警人"
        knows_facts = '["看到黑色轿车逃逸"]'

    class Case:
        structured_data = '{"fact_sheet": {"case_time": "昨晚22:10", "case_location": "建设路与新华街交叉口"}}'

    merged = merge_role_knows_facts(Role(), Case())
    assert "建设路与新华街交叉口" in merged
    assert "昨晚22:10" in merged
