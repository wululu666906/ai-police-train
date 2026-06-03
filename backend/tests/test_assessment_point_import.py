"""Tests for assessment point import service."""

from services.assessment_point_import_service import (
    list_builtin_templates,
    parse_text_to_assessment_points,
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


def test_builtin_templates_not_empty():
    templates = list_builtin_templates()
    assert len(templates) >= 3
    assert all(item.get("point_count", 0) > 0 for item in templates)
