"""Assessment point limits, dedupe, and finalize for admin + evaluation."""

from __future__ import annotations

import re
from typing import Any

from .scene_bucket_service import resolve_scene_bucket

ASSESSMENT_POINTS_MAX_PER_SCENE = 6

_SECTION_LINE_RE = re.compile(
    r"^\s*[【\[]?\s*(接警|现场|询问|讯问|信息初核|初查|笔录|intake|onsite|investigation)\s*[】\]]?\s*$",
    re.IGNORECASE,
)


def _normalize_label(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip().lower())
    return text


def dedupe_assessment_points(points: list[dict[str, Any]] | None, *, by: str = "label") -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for point in points or []:
        if not isinstance(point, dict):
            continue
        if by == "id":
            key = str(point.get("id") or "").strip()
        else:
            key = _normalize_label(point.get("label"))
        if not key:
            key = _normalize_label(point.get("content"))
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(dict(point))
    return output


def cap_assessment_points(
    points: list[dict[str, Any]] | None,
    limit: int = ASSESSMENT_POINTS_MAX_PER_SCENE,
) -> tuple[list[dict[str, Any]], bool]:
    items = list(points or [])
    if len(items) <= limit:
        return items, False
    return items[:limit], True


def finalize_assessment_points(
    points: list[dict[str, Any]] | None,
    *,
    case_type: str = "",
    scene_name: str = "",
    stage_name: str = "考察点",
    stage_goal: str = "",
    limit: int = ASSESSMENT_POINTS_MAX_PER_SCENE,
) -> tuple[list[dict[str, Any]], list[str]]:
    from .assessment_point_import_service import apply_template_to_points

    warnings: list[str] = []
    deduped = dedupe_assessment_points(points)
    if len(deduped) < len(points or []):
        warnings.append("已去除重复考察点")
    enriched = apply_template_to_points(
        deduped,
        case_type=case_type,
        scene_name=scene_name,
        stage_name=stage_name,
        stage_goal=stage_goal,
    )
    capped, truncated = cap_assessment_points(enriched, limit=limit)
    if truncated:
        warnings.append(f"考察点已截断为每场景最多 {limit} 条")
    return capped, warnings


def parse_points_for_scene_text(
    text: str,
    *,
    scene_name: str = "",
    scene_index: int = 0,
    scene_count: int = 1,
    case_type: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    from .assessment_point_import_service import (
        _looks_like_assessment_paste,
        parse_text_to_assessment_points,
        parse_text_to_bucketed_points,
    )

    raw = str(text or "").strip()
    warnings: list[str] = []
    if not raw:
        return [], warnings

    bucket = resolve_scene_bucket(scene_name, scene_index=scene_index, scene_count=scene_count)
    points: list[dict[str, Any]] = []

    if _looks_like_assessment_paste(raw) and _SECTION_LINE_RE.search(raw):
        buckets = parse_text_to_bucketed_points(raw)
        points = list(buckets.get(bucket) or [])
        if not points:
            points = parse_text_to_assessment_points(raw)
            warnings.append("文件中未找到与本场景类型匹配的分段，已按全文列表解析")
    else:
        points = parse_text_to_assessment_points(raw)

    finalized, policy_warnings = finalize_assessment_points(points, case_type=case_type, scene_name=scene_name)
    warnings.extend(policy_warnings)
    return finalized, warnings
