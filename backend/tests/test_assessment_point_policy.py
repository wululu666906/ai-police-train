"""Tests for assessment point policy (dedupe, cap, per-scene parse)."""

from services.assessment_point_policy import (
    ASSESSMENT_POINTS_MAX_PER_SCENE,
    cap_assessment_points,
    dedupe_assessment_points,
    finalize_assessment_points,
    parse_points_for_scene_text,
)


def test_dedupe_by_label():
    points = [
        {"label": "核实身份", "content": "a"},
        {"label": "核实身份", "content": "b"},
        {"label": "确认地点", "content": "c"},
    ]
    assert len(dedupe_assessment_points(points)) == 2


def test_cap_assessment_points():
    points = [{"label": f"p{i}", "content": "x"} for i in range(8)]
    capped, truncated = cap_assessment_points(points, limit=6)
    assert len(capped) == 6
    assert truncated is True


def test_finalize_caps_at_max():
    raw = [{"label": f"考察点{i}", "content": f"内容{i}"} for i in range(10)]
    finalized, warnings = finalize_assessment_points(raw, case_type="邻里纠纷", scene_name="现场处置")
    assert len(finalized) <= ASSESSMENT_POINTS_MAX_PER_SCENE
    assert any("截断" in item for item in warnings)


def test_parse_points_for_scene_bucket_section():
    text = "【接警】\n1. 核实报警来源\n2. 确认地址\n【现场】\n1. 表明身份\n2. 控制现场"
    intake_points, _ = parse_points_for_scene_text(text, scene_name="110接警研判", scene_index=0, scene_count=2)
    onsite_points, _ = parse_points_for_scene_text(text, scene_name="现场处置", scene_index=1, scene_count=2)
    assert 1 <= len(intake_points) <= ASSESSMENT_POINTS_MAX_PER_SCENE
    assert 1 <= len(onsite_points) <= ASSESSMENT_POINTS_MAX_PER_SCENE
