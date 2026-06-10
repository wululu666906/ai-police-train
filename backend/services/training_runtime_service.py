from __future__ import annotations

import json
from typing import Any


DEFAULT_RUNTIME_STATE = {
    "revealed_info": [],
    "assessment_progress": {
        "points": [],
        "actions": [],
        "summary": {
            "requirements": [],
            "satisfied": [],
            "missing": [],
            "completed_point_ids": [],
            "completed_action_ids": [],
            "total_weight": 0,
            "earned_weight": 0,
        },
    },
    "completed_point_ids": [],
    "completed_action_ids": [],
    "auto_finish_ready": False,
    "closure_summary": {},
    "state_snapshot": {
        "cooperation": 30,
        "risk": 50,
        "clarity": 50,
    },
    "role_state_snapshots": {},
    "last_active_role_ids": [],
    "last_target_role_name": "",
    "state_influence_turn_log": [],
}

_RUNTIME_PASSTHROUGH_KEYS = (
    "state_contract",
    "role_contracts",
    "last_postcheck",
    "state_influence_turn_log",
    "opening_delivered",
    "dialogue_mode",
)


def _safe_json_loads(value: Any, default: Any):
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen = set()
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _clamp_score(value: Any, fallback: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def _normalize_state_snapshot(value: Any) -> dict[str, int]:
    value = value if isinstance(value, dict) else {}
    defaults = DEFAULT_RUNTIME_STATE["state_snapshot"]
    return {
        "cooperation": _clamp_score(value.get("cooperation"), defaults["cooperation"]),
        "risk": _clamp_score(value.get("risk"), defaults["risk"]),
        "clarity": _clamp_score(value.get("clarity"), defaults["clarity"]),
    }


def _normalize_role_state_snapshot(value: Any, fallback: dict[str, int] | None = None) -> dict[str, int]:
    fallback = fallback or {"emotion": 50, "cooperation": 30, "risk": 50, "clarity": 50}
    value = value if isinstance(value, dict) else {}
    return {
        "emotion": _clamp_score(value.get("emotion"), fallback["emotion"]),
        "cooperation": _clamp_score(value.get("cooperation"), fallback["cooperation"]),
        "risk": _clamp_score(value.get("risk"), fallback["risk"]),
        "clarity": _clamp_score(value.get("clarity"), fallback["clarity"]),
    }


def _normalize_role_state_snapshots(value: Any) -> dict[str, dict[str, int]]:
    if not isinstance(value, dict):
        return {}
    snapshots: dict[str, dict[str, int]] = {}
    for raw_key, raw_snapshot in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        snapshots[key] = _normalize_role_state_snapshot(raw_snapshot)
    return snapshots


def _normalize_role_id_list(value: Any) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for item in value if isinstance(value, list) else []:
        try:
            numeric = int(item)
        except (TypeError, ValueError):
            continue
        if numeric in seen:
            continue
        seen.add(numeric)
        result.append(numeric)
    return result


def load_runtime_state(raw_value: Any) -> dict[str, Any]:
    parsed = _safe_json_loads(raw_value, [])
    if isinstance(parsed, list):
        state = json.loads(json.dumps(DEFAULT_RUNTIME_STATE, ensure_ascii=False))
        state["revealed_info"] = _dedupe_strings(parsed)
        return state
    if not isinstance(parsed, dict):
        return json.loads(json.dumps(DEFAULT_RUNTIME_STATE, ensure_ascii=False))

    state = json.loads(json.dumps(DEFAULT_RUNTIME_STATE, ensure_ascii=False))
    state["revealed_info"] = _dedupe_strings(parsed.get("revealed_info") or [])
    state["completed_point_ids"] = _dedupe_strings(parsed.get("completed_point_ids") or [])
    state["completed_action_ids"] = _dedupe_strings(parsed.get("completed_action_ids") or [])
    state["auto_finish_ready"] = bool(parsed.get("auto_finish_ready", False))
    state["closure_summary"] = parsed.get("closure_summary") if isinstance(parsed.get("closure_summary"), dict) else {}
    state["state_snapshot"] = _normalize_state_snapshot(parsed.get("state_snapshot"))
    state["role_state_snapshots"] = _normalize_role_state_snapshots(parsed.get("role_state_snapshots"))
    state["last_active_role_ids"] = _normalize_role_id_list(parsed.get("last_active_role_ids"))
    state["last_target_role_name"] = str(parsed.get("last_target_role_name") or "").strip()
    progress = parsed.get("assessment_progress")
    if isinstance(progress, dict):
        state["assessment_progress"] = progress
    for key in _RUNTIME_PASSTHROUGH_KEYS:
        if key in parsed:
            state[key] = parsed[key]
    if "opening_delivered" in parsed:
        state["opening_delivered"] = bool(parsed.get("opening_delivered"))
    if parsed.get("dialogue_mode"):
        state["dialogue_mode"] = str(parsed.get("dialogue_mode"))
    if not isinstance(state.get("state_influence_turn_log"), list):
        state["state_influence_turn_log"] = []
    return state


def dump_runtime_state(state: dict[str, Any]) -> str:
    payload = {
        "revealed_info": _dedupe_strings((state or {}).get("revealed_info") or []),
        "assessment_progress": (state or {}).get("assessment_progress") or DEFAULT_RUNTIME_STATE["assessment_progress"],
        "completed_point_ids": _dedupe_strings((state or {}).get("completed_point_ids") or []),
        "completed_action_ids": _dedupe_strings((state or {}).get("completed_action_ids") or []),
        "auto_finish_ready": bool((state or {}).get("auto_finish_ready", False)),
        "closure_summary": (state or {}).get("closure_summary") or {},
        "state_snapshot": _normalize_state_snapshot((state or {}).get("state_snapshot")),
        "role_state_snapshots": _normalize_role_state_snapshots((state or {}).get("role_state_snapshots")),
        "last_active_role_ids": _normalize_role_id_list((state or {}).get("last_active_role_ids")),
        "last_target_role_name": str((state or {}).get("last_target_role_name") or "").strip(),
    }
    for key in _RUNTIME_PASSTHROUGH_KEYS:
        if key in (state or {}):
            payload[key] = state[key]
    return json.dumps(payload, ensure_ascii=False)


def _message_snippet(content: str, keyword: str) -> str:
    content = str(content or "").strip()
    if not content:
        return ""
    if keyword and keyword in content:
        return content[:120]
    return content[:120]


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    text = str(text or "")
    return [keyword for keyword in keywords if keyword and keyword in text]


def collect_stage_progress(
    stage_config: dict[str, Any],
    messages: list[Any],
    revealed_info: list[str],
    extra_texts: list[str] | None = None,
    recognized_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    extra_texts = extra_texts or []
    recognized_actions = recognized_actions or []
    action_catalog = stage_config.get("action_catalog") or []
    assessment_points = stage_config.get("assessment_points") or []
    action_map = {item.get("id"): item for item in action_catalog if isinstance(item, dict)}

    completed_action_ids: list[str] = []
    action_results: list[dict[str, Any]] = []
    for action in action_catalog:
        action_id = str(action.get("id") or "").strip()
        label = str(action.get("label") or action_id).strip()
        aliases = [label, *(action.get("aliases") or [])]
        evidence: list[str] = []

        for message in messages:
            role = str(getattr(message, "role", "") or "")
            content = str(getattr(message, "content", "") or "")
            if role == "action":
                if any(alias and alias in content for alias in aliases):
                    evidence.append(_message_snippet(content, label))
            elif role == "user" and any(alias and alias in content for alias in aliases):
                evidence.append(_message_snippet(content, label))

        for text in extra_texts:
            if any(alias and alias in text for alias in aliases):
                evidence.append(_message_snippet(text, label))

        for action_event in recognized_actions:
            if action_event.get("action_id") == action_id:
                evidence.append(str(action_event.get("note") or action_event.get("label") or label).strip())

        unique_evidence = _dedupe_strings(evidence)
        status = "hit" if unique_evidence else "missed"
        if status == "hit":
            completed_action_ids.append(action_id)

        action_results.append(
            {
                "id": action_id,
                "label": label,
                "type": str(action.get("type") or "physical"),
                "status": status,
                "evidence": unique_evidence[:3],
            }
        )

    point_results: list[dict[str, Any]] = []
    completed_point_ids: list[str] = []
    requirements: list[str] = []
    satisfied: list[str] = []
    missing: list[str] = []
    total_weight = 0
    earned_weight = 0

    corpus = list(extra_texts)
    corpus.extend(str(item) for item in revealed_info if str(item).strip())
    corpus.extend(str(getattr(message, "content", "") or "") for message in messages if getattr(message, "role", "") in {"user", "assistant", "action"})

    for point in assessment_points:
        point_id = str(point.get("id") or "").strip()
        label = str(point.get("label") or point_id).strip()
        keywords = [str(item or "").strip() for item in point.get("keywords") or [] if str(item or "").strip()]
        required = bool(point.get("required", True))
        weight = max(1, int(point.get("weight", 10) or 10))
        knowledge_refs = _dedupe_strings(point.get("knowledge_refs") or [])
        counts_for_actions = [
            action_id
            for action_id, action in action_map.items()
            if point_id in (action.get("counts_for") or [])
        ]

        keyword_matches: list[str] = []
        evidence: list[str] = []
        for text in corpus:
            hits = _keyword_hits(text, keywords)
            if hits:
                keyword_matches.extend(hits)
                evidence.append(_message_snippet(text, hits[0]))

        linked_actions = [item for item in completed_action_ids if item in counts_for_actions]
        hit_count = len(set(keyword_matches))
        keyword_target = min(len(keywords), 2) if keywords else 1
        has_action_credit = bool(linked_actions)
        status = "missed"
        if hit_count >= keyword_target or has_action_credit:
            status = "hit"
        elif hit_count > 0:
            status = "partial"

        score = weight if status == "hit" else max(1, weight // 2) if status == "partial" else 0
        if status == "hit":
            completed_point_ids.append(point_id)
            satisfied.append(label)
            earned_weight += weight
        elif status == "partial":
            earned_weight += max(1, weight // 2)
        else:
            missing.append(label)

        total_weight += weight
        requirements.append(label)
        point_results.append(
            {
                "id": point_id,
                "label": label,
                "category": str(point.get("category") or "procedure"),
                "required": required,
                "weight": weight,
                "status": status,
                "score": score,
                "evidence": _dedupe_strings(evidence)[:3],
                "feedback": "",
                "knowledge_refs": knowledge_refs,
                "linked_action_ids": counts_for_actions,
                "linked_actions_completed": linked_actions,
            }
        )

    return {
        "points": point_results,
        "actions": action_results,
        "summary": {
            "requirements": requirements,
            "satisfied": satisfied,
            "missing": missing,
            "completed_point_ids": _dedupe_strings(completed_point_ids),
            "completed_action_ids": _dedupe_strings(completed_action_ids),
            "total_weight": total_weight,
            "earned_weight": earned_weight,
        },
    }


def detect_actions_from_text(stage_config: dict[str, Any], text: str) -> list[dict[str, Any]]:
    text = str(text or "").strip()
    if not text:
        return []

    recognized: list[dict[str, Any]] = []
    for action in stage_config.get("action_catalog") or []:
        aliases = [str(item or "").strip() for item in action.get("aliases") or [] if str(item or "").strip()]
        if any(alias in text for alias in aliases):
            recognized.append(
                {
                    "action_id": str(action.get("id") or "").strip(),
                    "label": str(action.get("label") or "").strip(),
                    "type": str(action.get("type") or "physical").strip(),
                    "source": "text",
                    "note": text,
                }
            )
    return recognized


def evaluate_stage_completion(stage_config: dict[str, Any], progress: dict[str, Any], stage_turn_count: int, llm_completed: bool = False) -> bool:
    completion_rules = stage_config.get("completion_rules") or {}
    required_turns = max(1, int(completion_rules.get("min_user_turns", 3) or 3))
    required_point_ids = _dedupe_strings(completion_rules.get("required_point_ids") or [])
    required_action_ids = _dedupe_strings(completion_rules.get("required_action_ids") or [])
    completed_points = set(progress.get("summary", {}).get("completed_point_ids") or [])
    completed_actions = set(progress.get("summary", {}).get("completed_action_ids") or [])

    if stage_turn_count < required_turns:
        return False
    if any(point_id not in completed_points for point_id in required_point_ids):
        return False
    if any(action_id not in completed_actions for action_id in required_action_ids):
        return False
    if required_point_ids or required_action_ids:
        return True
    return bool(llm_completed) or not progress.get("summary", {}).get("missing")


def evaluate_end_conditions(
    stage_config: dict[str, Any],
    progress: dict[str, Any],
    stage_completed: bool,
    is_last_stage: bool,
    message_text: str = "",
    recognized_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    recognized_actions = recognized_actions or []
    end_conditions = stage_config.get("end_conditions") or {}
    completed_points = set(progress.get("summary", {}).get("completed_point_ids") or [])
    completed_actions = set(progress.get("summary", {}).get("completed_action_ids") or [])
    closure_actions = [str(item or "").strip() for item in end_conditions.get("closure_actions") or [] if str(item or "").strip()]
    text = str(message_text or "").strip()
    action_labels = [str(item.get("label") or "").strip() for item in recognized_actions]

    closure_hit = any(keyword in text for keyword in closure_actions)
    closure_hit = closure_hit or any(any(keyword in label for keyword in closure_actions) for label in action_labels)

    required_point_ids = _dedupe_strings(end_conditions.get("required_point_ids") or [])
    required_action_ids = _dedupe_strings(end_conditions.get("required_action_ids") or [])
    missing_point_ids = [item for item in required_point_ids if item not in completed_points]
    missing_action_ids = [item for item in required_action_ids if item not in completed_actions]
    must_complete_current_stage = bool(end_conditions.get("must_complete_current_stage", True))

    if required_point_ids or required_action_ids or closure_actions:
        ready = (not must_complete_current_stage or stage_completed) and not missing_point_ids and not missing_action_ids and (closure_hit or not closure_actions)
        return {
            "ready": ready,
            "closure_hit": closure_hit,
            "missing_point_ids": missing_point_ids,
            "missing_action_ids": missing_action_ids,
            "closing_script": str(end_conditions.get("closing_script") or "").strip(),
        }

    fallback_keywords = ["带离", "带回", "笔录", "移交", "结束训练", "处置完毕", "处理完毕", "后续处理"]
    fallback_hit = any(keyword in text for keyword in fallback_keywords) or any(any(keyword in label for keyword in fallback_keywords) for label in action_labels)
    ready = is_last_stage and stage_completed and (fallback_hit or not progress.get("summary", {}).get("missing"))
    return {
        "ready": ready,
        "closure_hit": fallback_hit,
        "missing_point_ids": [],
        "missing_action_ids": [],
        "closing_script": "",
    }


def build_closure_message(stage_config: dict[str, Any], current_stage: str, role_name: str, emotion: int) -> str:
    end_conditions = stage_config.get("end_conditions") or {}
    configured = str(end_conditions.get("closing_script") or "").strip()
    if configured:
        return configured
    if emotion >= 70:
        return f"{role_name or '对方'}的主要情绪和关键信息已处置到位，当前“{current_stage or '本阶段'}”训练结束，转入后续程序。"
    return f"当前“{current_stage or '本阶段'}”关键处置已完成，现转入后续笔录或处置流程，本轮训练结束。"


def build_follow_up_reply(role_name: str, emotion: int, reason: str, recognized_actions: list[dict[str, Any]] | None = None) -> str:
    recognized_actions = recognized_actions or []
    if reason == "closure":
        return ""
    if reason == "action" and recognized_actions:
        action_label = str(recognized_actions[0].get("label") or "这个动作").strip()
        return f"好，你们现在是在{action_label}，那我就按你要求继续配合。"
    if reason == "emotion":
        return "我现在情绪还没完全缓下来，你别一下子催太快，我慢慢说。"
    if reason == "trigger":
        return f"你这话问到点子上了，但有些细节我得再想一下。"
    return ""
