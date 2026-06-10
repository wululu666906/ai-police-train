from services.canonical_facts_service import extract_canonical_facts, format_canonical_facts_block, merge_role_knows_facts
from services.dialogue_sanitize_service import sanitize_spoken_line, sanitize_utterances


def test_sanitize_template_leakage():
    raw = "我最怕的就是担心被报复，你们先听我说行不行？"
    cleaned = sanitize_spoken_line(raw)
    assert "我最怕的就是" not in cleaned
    assert "核心顾虑" not in cleaned


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
