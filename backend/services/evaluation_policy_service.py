from __future__ import annotations

from typing import Any

from services.agent_training_service import is_current_evaluation_report

COMMON_DIMENSIONS = [
    ("沟通表达与执法语言", 25),
    ("主动询问与逻辑推进", 25),
    ("关键信息整理能力", 25),
    ("处置闭环意识", 25),
]


def _build_scene_info(scene, scene_type: str, role, case=None) -> str:
    import json

    try:
        metadata = json.loads(getattr(role, "persona_meta", "{}") or "{}")
    except (TypeError, ValueError):
        metadata = {}
    labels = {
        "behavior_archetype": "行为原型",
        "police_attitude": "对警方基本态度",
        "current_goal": "当前诉求",
        "core_concern": "核心顾虑",
        "relationship_pressure": "关系压力",
        "calming_points": "可安抚点",
    }
    lines = [f"场景：{getattr(scene, 'name', '')}", f"角色：{getattr(role, 'name', '')}"]
    for key, label in labels.items():
        value = metadata.get(key)
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def compute_grade_level(total_score: int) -> str:
    score = max(0, min(100, int(total_score or 0)))
    if score >= 90:
        return "卓越"
    if score >= 80:
        return "优秀"
    if score >= 70:
        return "良好"
    if score >= 60:
        return "合格"
    return "需改进"


def enforce_final_score_policy(report: dict[str, Any], *, policy_source: str = "agent") -> dict[str, Any]:
    result = dict(report or {})
    result["total_score"] = max(0, min(100, int(result.get("total_score") or 0)))
    result["grade"] = compute_grade_level(result["total_score"])
    result["score_policy_source"] = policy_source
    return result


def merge_assessment_point_results(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group or []:
            key = str(item.get("id") or item.get("point_id") or item.get("name") or len(merged))
            merged[key] = {**merged.get(key, {}), **item}
    return list(merged.values())
