"""Tests for assessment point import service."""

from services.assessment_point_import_service import (
    _normalize_raw_point,
    list_builtin_templates,
    parse_text_to_assessment_points,
)
from services.stage_config_service import (
    infer_assessment_point_content,
    is_shallow_assessment_content,
    resolve_assessment_point_content,
)


def test_parse_numbered_lines():
    text = """1. 核实身份与关系
2. 确认事发地点
3. 评估现场风险：是否仍有冲突"""
    points = parse_text_to_assessment_points(text)
    assert len(points) >= 3
    assert points[0]["label"]
    assert points[0].get("weight", 0) >= 1


def test_parse_label_content_format():
    text = "建立关系：先安抚并确认报警人身份\n核实地点：问清具体位置与门牌"
    points = parse_text_to_assessment_points(text)
    assert len(points) == 2
    assert "建立关系" in points[0]["label"] or "建立关系" in points[0]["content"]


def test_shallow_content_is_expanded():
    assert is_shallow_assessment_content("问清现场经过", "学员应完成：问清现场经过。")
    point = _normalize_raw_point({"label": "问清现场经过", "content": "学员应完成：问清现场经过。"}, 1)
    assert len(point["content"]) >= 60
    assert "达标" in point["content"] or "学员应完成" in point["content"]


def test_infer_content_not_echo_label():
    content = infer_assessment_point_content("压实时间线矛盾")
    assert "压实时间线矛盾" in content
    assert content != "学员应完成：压实时间线矛盾。"
    assert "怎样算完成" in content
    assert "对话关键词" not in content
    assert len(content) >= 80


def test_resolve_rewrites_identity_relation_jargon():
    legacy = "学员在训练对话或现场处置中应做到：确认身份或报警人关系，结果可被对话关键词或执法动作核查。"
    content = resolve_assessment_point_content("确认身份或报警人关系", legacy)
    assert "怎样算完成" in content
    assert "对话关键词" not in content
    point = _normalize_raw_point({"label": "确认身份或报警人关系", "content": legacy}, 1)
    assert "怎样算完成" in point["content"]


def test_infer_content_rewrites_legacy_jargon_tail():
    legacy = "学员在训练对话或现场处置中应做到：核实时间线，结果可被对话关键词或执法动作核查。"
    content = infer_assessment_point_content(legacy)
    assert "怎样算完成" in content
    assert "对话关键词" not in content


def test_builtin_templates_not_empty():
    templates = list_builtin_templates()
    assert len(templates) >= 3
    assert all(item.get("point_count", 0) > 0 for item in templates)
