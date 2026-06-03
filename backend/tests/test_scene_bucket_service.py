"""Tests for scene bucket naming rules."""

from services.assessment_point_import_service import parse_text_to_bucketed_points
from services.scene_bucket_service import resolve_scene_bucket, suggest_standard_scene_name


def test_resolve_scene_bucket_keywords():
    assert resolve_scene_bucket("接警研判") == "intake"
    assert resolve_scene_bucket("现场处置") == "onsite"
    assert resolve_scene_bucket("重点询问") == "investigation"


def test_resolve_scene_bucket_fallback_by_index():
    assert resolve_scene_bucket("训练场景A", scene_index=0, scene_count=3) == "intake"
    assert resolve_scene_bucket("训练场景B", scene_index=2, scene_count=3) == "investigation"


def test_standard_scene_names():
    assert suggest_standard_scene_name("intake") == "接警研判"
    assert suggest_standard_scene_name("onsite") == "现场处置"


def test_parse_text_with_section_headers():
    text = "【接警】\n核实报警人身份\n确认事发地点\n\n【现场】\n分离双方\n固定证据\n\n【询问】\n核实时间线"
    buckets = parse_text_to_bucketed_points(text)
    assert len(buckets["intake"]) >= 1
    assert len(buckets["onsite"]) >= 1
    assert len(buckets["investigation"]) >= 1
