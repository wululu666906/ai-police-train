"""Tests for contextual recommended question generation.

重构后：硬编码台词表已删除，内容由 LLM 生成。
use_llm=False 时只验证结构与基础过滤能力。
"""

from services.recommended_questions_service import (
    apply_stage_hit_rate_correction,
    build_recommended_question_items,
    build_recommended_questions,
    filter_stale_missing_requirements_for_history,
)


def test_always_returns_at_least_one_item():
    """无 LLM 时仍返回兜底条目。"""
    questions = build_recommended_questions(
        current_stage="现场处置",
        current_stage_goal="评估现场安全",
        case_type="求助",
        role_name="报警人",
        use_llm=False,
    )
    assert questions
    assert len(questions) >= 1


def test_no_meta_instruction_style():
    """输出不含教学腔关键词。"""
    items = build_recommended_question_items(
        current_stage_goal="评估现场安全，呼叫120，初步了解伤者情况，保护",
        use_llm=False,
    )
    for item in items:
        assert "把最关键" not in item["text"]
        assert "先围绕" not in item["text"]
        assert "建议" not in item["text"]


def test_custom_prompts_have_priority():
    items = build_recommended_question_items(
        custom_prompts=["张某，楼道杂物是你放的吗？"],
        current_stage_goal="评估现场安全",
        use_llm=False,
    )
    assert items
    assert items[0]["text"] == "张某，楼道杂物是你放的吗？"
    assert items[0]["category"] == "定制"


def test_dedupe_items():
    """重复条目不出现。"""
    items = build_recommended_question_items(
        custom_prompts=["你能说一下情况吗？", "你能说一下情况吗？"],
        use_llm=False,
    )
    texts = [item["text"] for item in items]
    assert len(texts) == len(set(texts))


def test_history_filter_removes_covered_intake_process_gap():
    missing = filter_stale_missing_requirements_for_history(
        ["什么事/经过", "风险/伤情", "身份/关系"],
        recent_messages=[
            {"role": "assistant", "content": "楼下有人打起来了，我刚报警。", "speaker_name": "报警人"},
        ],
        last_user_message="请说一下具体什么情况，发生什么事了？",
        use_intake_flow=True,
    )
    assert "风险/伤情" in missing
    assert "身份/关系" in missing


def test_stage_hit_correction_returns_items():
    missing = filter_stale_missing_requirements_for_history(
        ["什么事/经过"],
        recent_messages=[
            {"role": "assistant", "content": "楼下有人打起来了，我刚报警。", "speaker_name": "报警人"},
        ],
        last_user_message="请说一下具体什么情况，发生什么事了？",
        use_intake_flow=True,
    )
    items = [{"text": "你现在人安全吗？有没有人受伤？", "category": "安抚", "target_role_name": None}]
    corrected = apply_stage_hit_rate_correction(items, satisfied=["什么事/经过"], missing=missing)
    assert corrected
