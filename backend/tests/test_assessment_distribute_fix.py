"""Regression tests for assessment distribute fixes."""

from services.assessment_point_import_service import (
    _looks_like_assessment_paste,
    build_officer_user_prompt,
    distribute_assessment_points_to_scenes,
)


def test_officer_prompt_tolerates_curly_braces_in_case():
    case_info = {"title": "测试", "case_type": "邻里纠纷", "full_narrative": "当事人说：{我不认}"}
    prompt = build_officer_user_prompt(case_info, [{"name": "接警研判"}], source_text="参考{abc}")
    assert "{我不认}" in prompt
    assert "参考{abc}" in prompt


def test_long_narrative_not_treated_as_paste():
    narrative = "这是一段很长的案情描述。\n" * 50
    assert _looks_like_assessment_paste(narrative) is False


def test_builtin_template_points_include_content():
    result = distribute_assessment_points_to_scenes(
        {"title": "纠纷", "case_type": "邻里纠纷"},
        [{"id": 1, "name": "接警研判"}],
        use_llm=False,
    )
    points = result["assignments"][0]["points"]
    assert points
    assert all(str(item.get("content") or "").strip() for item in points)


def test_distribute_without_llm_uses_builtin_templates():
    result = distribute_assessment_points_to_scenes(
        {"title": "纠纷", "case_type": "邻里纠纷"},
        [
            {"id": 1, "name": "接警研判"},
            {"id": 2, "name": "现场处置"},
            {"id": 3, "name": "重点询问"},
        ],
        use_llm=False,
    )
    assert result["total_points"] > 0
    assert len(result["assignments"]) == 3
    assert result["source"] in {"builtin_template", "builtin"}


def test_distribute_empty_llm_payload_falls_back_to_builtin():
    from unittest.mock import patch

    with patch(
        "services.assessment_point_import_service.generate_assessment_points_with_llm",
        return_value=[],
    ):
        result = distribute_assessment_points_to_scenes(
            {"title": "纠纷", "case_type": "邻里纠纷", "full_narrative": "案情"},
            [{"id": 1, "name": "接警研判"}, {"id": 2, "name": "现场处置"}, {"id": 3, "name": "重点询问"}],
            use_llm=True,
        )
    assert result["total_points"] > 0
    assert "builtin" in result["source"]
