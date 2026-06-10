"""Regression tests for recommended question generation."""

from services.recommended_questions_service import build_recommended_question_items


def test_missing_first_correction_does_not_wrap_bool_in_any():
    items = build_recommended_question_items(
        current_stage="安抚止损",
        current_stage_goal="核实时间、地点和人物",
        missing_requirements=["时间"],
        use_llm=False,
    )

    assert items
    assert isinstance(items[0]["text"], str)
