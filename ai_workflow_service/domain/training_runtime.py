from __future__ import annotations

import re
from typing import Any


MAX_ASSESSMENT_POINTS = 12


def _text(value: Any) -> str:
    return str(value or "").strip()


def dedupe_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(points or []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        key = _text(item.get("id") or item.get("point_id") or item.get("label") or item.get("content"))
        if not key or key.casefold() in seen:
            continue
        seen.add(key.casefold())
        item["id"] = _text(item.get("id") or item.get("point_id") or f"point-{index + 1}")
        item["required"] = bool(item.get("required", item.get("is_required", True)))
        item["keywords"] = list(dict.fromkeys(_text(value) for value in item.get("keywords") or [] if _text(value)))
        result.append(item)
        if len(result) >= MAX_ASSESSMENT_POINTS:
            break
    return result


def evaluate_points(points: list[dict[str, Any]], transcript: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    corpus = "\n".join(_text(item.get("content")) for item in transcript if item.get("role") in {"user", "action"})
    compact_corpus = "".join(ch for ch in corpus if not ch.isspace())
    action_set = {_text(item) for item in actions if _text(item)}
    # 领域短词：用于从考察点正文派生可观察命中词
    domain_terms = (
        "报警人", "报警", "身份", "姓名", "联系方式", "电话", "时间", "地点", "地址", "在场",
        "经过", "原因", "诉求", "矛盾", "伤情", "伤员", "受伤", "流血", "危险", "风险", "安全",
        "证据", "监控", "现场", "隔离", "疏散", "控制", "警告", "告知", "劝离", "制止",
        "救护", "救护车", "急救", "派警", "增援", "武器", "刀具", "持刀", "斗殴", "冲突",
        "情绪", "安抚", "询问", "核实", "确认", "记录", "闭环", "收尾", "总结", "反馈",
        "暴力", "规模", "人数", "人员", "嫌疑人", "证人", "当事人", "被害人", "受害者",
    )
    stopwords = {"能够", "可以", "应当", "应该", "需要", "要求", "迅速", "及时", "正确", "有效", "充分", "进行", "完成"}
    results = []
    for point in dedupe_points(points):
        keywords = [_text(item) for item in (point.get("keywords") or []) if _text(item)]
        label = _text(point.get("label") or point.get("content"))
        content = _text(point.get("content") or point.get("label"))
        compact_content = "".join(ch for ch in content if not ch.isspace())
        derived: list[str] = []
        for term in sorted(domain_terms, key=len, reverse=True):
            if term in compact_content and term not in derived:
                derived.append(term)
            if len(derived) >= 6:
                break
        for chunk in re.split(r"[，。；、,/；]", content or label):
            token = "".join(ch for ch in chunk if not ch.isspace())
            token = re.sub(r"^(能够|可以|应当|应该|需要|要求|迅速|及时|正确|有效|充分|进行)", "", token)
            if 2 <= len(token) <= 8 and token not in stopwords and token not in derived:
                derived.append(token)
            if len(derived) >= 8:
                break
        # 过滤过长整句关键词（历史数据可能仍带 10+ 字整句）
        usable_keywords = [word for word in keywords if 2 <= len(word) <= 8 and word not in stopwords]
        search_terms = list(dict.fromkeys([*usable_keywords, *derived[:6]]))
        if not search_terms and label:
            short_label = re.sub(r"^(能够|可以|应当|应该|需要|要求)", "", "".join(ch for ch in label if not ch.isspace()))
            if 2 <= len(short_label) <= 8:
                search_terms = [short_label]
        keyword_hits = [word for word in search_terms if word and (word in corpus or word in compact_corpus)]
        if not keyword_hits and compact_content:
            # 短前缀兜底：仅用前 6 字，降低整句永不命中概率
            tip = compact_content[:6]
            if tip and tip in compact_corpus:
                keyword_hits = [tip]
        related = {_text(item) for item in point.get("related_actions") or point.get("actions") or []}
        action_hits = sorted(related & action_set)
        evidence = keyword_hits + [f"action:{item}" for item in action_hits]
        ratio = (len(keyword_hits) / max(len([w for w in search_terms if w]), 1)) if search_terms else (1.0 if action_hits else 0.0)
        if action_hits:
            ratio = max(ratio, 1.0)
        if keyword_hits and ratio < 0.34:
            ratio = 0.34
        # 命中任一可观察短词即至少 partial；命中过半或 >=2 词视为 hit
        if keyword_hits:
            if len(keyword_hits) >= 2 or ratio >= 0.5:
                ratio = max(ratio, 0.5)
            else:
                ratio = max(ratio, 0.34)
        status = "hit" if ratio >= 0.5 else "partial" if ratio > 0 else "missed"
        results.append({**point, "status": status, "hit_ratio": round(min(ratio, 1.0), 4), "evidence": evidence})
    return results


def evaluate_training(payload: dict[str, Any], learner_input: str) -> dict[str, Any]:
    stage = dict(payload.get("stage") or {})
    transcript = list(payload.get("public_history") or payload.get("recent_dialogue") or [])
    transcript.append({"role": payload.get("input_kind", "user"), "content": learner_input})
    actions = list(payload.get("completed_action_ids") or [])
    if payload.get("input_kind") == "action" and payload.get("action_id"):
        actions.append(_text(payload.get("action_id")))
    outcome_points = []
    for index, item in enumerate(payload.get("expected_outcomes") or []):
        text = _text(item)
        if not text:
            continue
        outcome_points.append({
            "id": f"eo_{index + 1}",
            "label": text[:40],
            "content": text,
            "required": True,
            "keywords": [],
        })
    points = outcome_points or stage.get("assessment_points") or payload.get("assessment_points") or []
    results = evaluate_points(points, transcript, actions)
    previously_completed = {_text(item) for item in payload.get("completed_point_ids") or []}
    for item in results:
        if _text(item.get("id")) in previously_completed:
            item.update({"status": "hit", "hit_ratio": 1.0, "evidence": [*(item.get("evidence") or []), "prior_turn"]})
    required = [item for item in results if item.get("required")]
    completed_ids = [_text(item.get("id")) for item in results if item.get("status") == "hit"]
    required_complete = all(item.get("status") == "hit" for item in required) if required else False
    prerequisites = [_text(item) for item in stage.get("prerequisites") or []]
    prerequisites_met = all(item in completed_ids for item in prerequisites)
    stage_allowed = required_complete and prerequisites_met
    completion_rules = list(stage.get("completion_rules") or [])
    if completion_rules:
        stage_allowed = stage_allowed and all(
            not isinstance(rule, dict) or not rule.get("required_point_ids")
            or all(_text(item) in completed_ids for item in rule.get("required_point_ids") or [])
            for rule in completion_rules
        )
    end_conditions = list(stage.get("end_conditions") or [])
    stages = list((payload.get("scene_world") or {}).get("stages") or [])
    current_name = _text(stage.get("stage_name") or payload.get("current_stage") or "训练中")
    current_index = next((index for index, item in enumerate(stages) if _text(item.get("stage_name")) == current_name), -1)
    next_stage = stages[current_index + 1] if stage_allowed and 0 <= current_index < len(stages) - 1 else None
    final_stage = bool(stages) and current_index == len(stages) - 1
    training_finished = bool(stage_allowed and final_stage and end_conditions)
    requirements = [_text(item.get("label") or item.get("content") or item.get("id")) for item in results]
    satisfied = [_text(item.get("label") or item.get("content") or item.get("id")) for item in results if item.get("status") == "hit"]
    missing = [_text(item.get("label") or item.get("content") or item.get("id")) for item in results if item.get("status") != "hit"]
    return {
        "current_stage": _text(next_stage.get("stage_name")) if next_stage else current_name,
        "stage_advanced": bool(next_stage),
        "assessment_results": results,
        "assessment_progress": {
            "total": len(results),
            "hit": sum(item.get("status") == "hit" for item in results),
            "partial": sum(item.get("status") == "partial" for item in results),
            "missed": sum(item.get("status") == "missed" for item in results),
        },
        "completed_point_ids": completed_ids,
        "completed_action_ids": list(dict.fromkeys(actions)),
        "action_effective": payload.get("input_kind") != "action" or bool(payload.get("action_id")),
        "stage_advance_allowed": stage_allowed,
        "training_finished": training_finished,
        "stage_completion_requirements": requirements,
        "stage_completion_satisfied": satisfied,
        "stage_completion_missing": missing,
        "recommended_questions": [],
        "recommended_question_items": [],
        "communication_feedback": {
            "level": "warning" if missing else "success",
            "tags": ["stage_gap"] if missing else ["stage_complete"],
            "message": f"仍需完成：{'、'.join(missing[:3])}" if missing else "当前阶段要求已完成。",
            "all_messages": [f"仍需完成：{'、'.join(missing[:3])}" if missing else "当前阶段要求已完成。"],
        },
    }
