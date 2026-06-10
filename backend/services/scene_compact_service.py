"""Scene compact V1: training_focus + assessment cards → full stage JSON."""

from __future__ import annotations

import copy
import re
from typing import Any

from .assessment_point_policy import finalize_assessment_points
from .stage_config_service import (
    _build_stage_template,
    infer_scene_behavior_mode,
    normalize_stage,
    resolve_assessment_point_content,
)

TRAINING_FOCUS_OPTIONS: dict[str, dict[str, str]] = {
    "intake": {
        "label": "接警研判",
        "behavior_mode": "核查取证型",
        "stage_name": "接警研判",
        "stage_goal": "核实报警来源、基本事实与现场风险，明确下一步处置方向。",
        "scene_kind": "intake",
    },
    "onsite": {
        "label": "现场处置",
        "behavior_mode": "核查取证型",
        "stage_name": "现场处置",
        "stage_goal": "控制现场秩序，核实在场人员身份与关键经过，识别风险与证据。",
        "scene_kind": "onsite",
    },
    "interview": {
        "label": "重点问询",
        "behavior_mode": "核查取证型",
        "stage_name": "重点问询",
        "stage_goal": "围绕关键事实、时间线与矛盾点展开多轮问询与压实。",
        "scene_kind": "interview",
    },
    "mediation": {
        "label": "调解稳控",
        "behavior_mode": "调解型",
        "stage_name": "调解稳控",
        "stage_goal": "稳住双方情绪，明确矛盾焦点并寻找可落地的缓和路径。",
        "scene_kind": "mediation",
    },
    "crisis": {
        "label": "危机干预",
        "behavior_mode": "危机干预型",
        "stage_name": "危机干预",
        "stage_goal": "优先稳住关系与安全，识别刺激源与牵挂对象，降低极端行为风险。",
        "scene_kind": "crisis",
    },
    "control": {
        "label": "现场管控",
        "behavior_mode": "管控型",
        "stage_name": "现场管控",
        "stage_goal": "降低现场刺激，阻断升级动作，明确边界并恢复可控秩序。",
        "scene_kind": "control",
    },
}

DIFFICULTY_MIN_TURNS = {"低": 2, "中等": 3, "高": 4, "中": 3}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _slugify(value: str, prefix: str, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    text = text.strip("_")
    if not text:
        text = fallback
    return f"{prefix}_{text}"


def infer_training_focus(
    scene_name: str = "",
    *,
    behavior_mode: str = "",
    stages: Any = None,
) -> str:
    if isinstance(stages, list) and stages:
        meta = (stages[0] or {}).get("meta") if isinstance(stages[0], dict) else {}
        if isinstance(meta, dict) and _as_text(meta.get("training_focus")) in TRAINING_FOCUS_OPTIONS:
            return _as_text(meta["training_focus"])

    name = _as_text(scene_name)
    if any(token in name for token in ["接警", "110", "报警"]):
        return "intake"
    if any(token in name for token in ["调解", "协商", "纠纷"]):
        return "mediation"
    if any(token in name for token in ["轻生", "危机", "干预", "跳楼"]):
        return "crisis"
    if any(token in name for token in ["醉酒", "管控", "围观", "控制"]):
        return "control"
    if any(token in name for token in ["问询", "询问", "笔录", "讯问"]):
        return "interview"
    if any(token in name for token in ["现场", "处置", "处警"]):
        return "onsite"

    mode = _as_text(behavior_mode) or infer_scene_behavior_mode(scene_name, "", stages)
    if mode == "调解型":
        return "mediation"
    if mode == "危机干预型":
        return "crisis"
    if mode == "管控型":
        return "control"
    return "interview"


def training_focus_meta(focus: str) -> dict[str, str]:
    return TRAINING_FOCUS_OPTIONS.get(focus) or TRAINING_FOCUS_OPTIONS["interview"]


def _normalize_assessment_cards(
    cards: list[Any] | None,
    *,
    stage_key: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, card in enumerate(cards or [], start=1):
        if not isinstance(card, dict):
            continue
        label = _as_text(card.get("label") or card.get("name") or card.get("title"))
        if not label:
            continue
        point_id = _as_text(card.get("id")) or _slugify(label, "ap", f"{stage_key}_{index}")
        content = resolve_assessment_point_content(
            label,
            _as_text(card.get("content")),
            category=_as_text(card.get("category")) or "procedure",
        )
        output.append(
            {
                "id": point_id,
                "label": label,
                "content": content,
                "category": _as_text(card.get("category")) or "procedure",
                "required": card.get("required", True) is not False,
                "weight": int(card.get("weight") or 10),
                "keywords": card.get("keywords") if isinstance(card.get("keywords"), list) else [],
                "knowledge_refs": [],
            }
        )
    return output


def build_scene_stages_from_compact(
    scene_compact: dict[str, Any] | None,
    *,
    case_type: str = "",
    scene_name: str = "",
) -> list[dict[str, Any]]:
    scene_compact = copy.deepcopy(scene_compact or {})
    scene_name = _as_text(scene_compact.get("name") or scene_name)
    focus = _as_text(scene_compact.get("training_focus")) or infer_training_focus(
        scene_name,
        behavior_mode=_as_text(scene_compact.get("behavior_mode")),
        stages=scene_compact.get("stages"),
    )
    meta = training_focus_meta(focus)
    behavior_mode = _as_text(scene_compact.get("behavior_mode")) or meta["behavior_mode"]
    difficulty = _as_text(scene_compact.get("difficulty")) or "中等"
    min_turns = DIFFICULTY_MIN_TURNS.get(difficulty, 3)

    cards = scene_compact.get("assessment_points")
    if cards is None:
        cards = []
        for stage in scene_compact.get("stages") or []:
            if isinstance(stage, dict) and isinstance(stage.get("assessment_points"), list):
                cards.extend(stage["assessment_points"])

    stage_key = _slugify(scene_name or meta["stage_name"], "stage", focus)
    assessment_points = _normalize_assessment_cards(cards, stage_key=stage_key)
    assessment_points, _ = finalize_assessment_points(
        assessment_points,
        case_type=case_type,
        scene_name=scene_name,
        stage_name=meta["stage_name"],
        stage_goal=meta["stage_goal"],
    )
    assessment_points = _normalize_assessment_cards(assessment_points, stage_key=stage_key)

    if not assessment_points:
        template = _build_stage_template(case_type, scene_name, meta["stage_name"], meta["stage_goal"])
        assessment_points = template.get("assessment_points") or []

    point_ids = [item["id"] for item in assessment_points]
    template = _build_stage_template(case_type, scene_name, meta["stage_name"], meta["stage_goal"])
    action_catalog = template.get("action_catalog") or []
    action_ids = [item.get("id") for item in action_catalog if isinstance(item, dict) and item.get("id")]

    required_point_ids = point_ids[: min(2, len(point_ids))] or [
        item.get("id") for item in (template.get("assessment_points") or [])[:2] if isinstance(item, dict)
    ]

    stage = {
        "stage_name": meta["stage_name"],
        "stage_goal": meta["stage_goal"],
        "recommended_prompts": [_as_text(item.get("label")) for item in assessment_points[:4] if _as_text(item.get("label"))],
        "assessment_points": assessment_points,
        "action_catalog": action_catalog,
        "completion_rules": {
            "min_user_turns": min_turns,
            "required_point_ids": required_point_ids,
            "required_action_ids": [],
        },
        "end_conditions": {
            "must_complete_current_stage": True,
            "required_point_ids": required_point_ids,
            "required_action_ids": [],
            "closure_actions": (template.get("end_conditions") or {}).get("closure_actions") or [],
            "closing_script": (template.get("end_conditions") or {}).get("closing_script") or "",
        },
        "meta": {
            "training_focus": focus,
            "behavior_mode": behavior_mode,
            "compact_v1": True,
        },
    }
    return [normalize_stage(stage, 1, case_type=case_type, scene_name=scene_name)]


def scene_to_compact_view(
    scene: dict[str, Any] | None,
    *,
    case_type: str = "",
) -> dict[str, Any]:
    scene = copy.deepcopy(scene or {})
    scene_name = _as_text(scene.get("name") or scene.get("scene_name"))
    stages = scene.get("stages") or []
    if isinstance(stages, str):
        stages = []
    focus = infer_training_focus(scene_name, behavior_mode=_as_text(scene.get("behavior_mode")), stages=stages)
    meta = training_focus_meta(focus)
    behavior_mode = _as_text(scene.get("behavior_mode"))
    if not behavior_mode and stages and isinstance(stages[0], dict):
        stage_meta = stages[0].get("meta") or {}
        behavior_mode = _as_text(stage_meta.get("behavior_mode"))
    if not behavior_mode:
        behavior_mode = meta["behavior_mode"]

    cards: list[dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        for point in stage.get("assessment_points") or []:
            if isinstance(point, dict) and _as_text(point.get("label")):
                cards.append(
                    {
                        "id": point.get("id"),
                        "label": point.get("label"),
                        "content": point.get("content") or "",
                    }
                )

    return {
        "name": scene_name,
        "training_focus": focus,
        "behavior_mode": behavior_mode,
        "difficulty": _as_text(scene.get("difficulty")) or "中等",
        "description": _as_text(scene.get("description") or scene.get("scene_description")),
        "dispatch_brief": _as_text(scene.get("dispatch_brief")),
        "first_impression": _as_text(scene.get("first_impression")),
        "role_names": scene.get("role_names") or [],
        "primary_role_name": _as_text(scene.get("primary_role_name")),
        "assessment_points": cards,
    }
