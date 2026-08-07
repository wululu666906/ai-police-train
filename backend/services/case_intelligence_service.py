"""Canonical case intelligence and per-role epistemic views.

The original workflow stored model summaries as undifferentiated "facts".
This module introduces a backward-compatible semantic layer inside
``Case.structured_data``: claims, evidence, events and unresolved questions.
Roleplay code consumes only a role-scoped epistemic view, never the whole case.
"""

from __future__ import annotations

import json
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [line.strip(" -\t") for line in value.splitlines() if line.strip(" -\t")]
    return []


def _dedupe_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _text(value)
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def normalize_case_intelligence(structured: dict[str, Any] | None) -> dict[str, Any]:
    """Return the v2 intelligence contract while accepting legacy payloads."""
    source = structured if isinstance(structured, dict) else {}
    current = source.get("case_intelligence")
    current = current if isinstance(current, dict) else {}

    claims = [dict(item) for item in _list(current.get("claims")) if isinstance(item, dict)]
    if not claims:
        legacy_world = source.get("story_world") if isinstance(source.get("story_world"), dict) else {}
        legacy_facts = _list(legacy_world.get("fact_cards")) or _list(source.get("key_facts"))
        for index, item in enumerate(legacy_facts, start=1):
            content = _text(item.get("content")) if isinstance(item, dict) else _text(item)
            if not content:
                continue
            claims.append(
                {
                    "claim_id": _text(item.get("id")) if isinstance(item, dict) else f"LC{index}",
                    "statement": content,
                    "claim_type": "legacy_summary",
                    "verification_status": "unverified",
                    "certainty": "unknown",
                    "source_refs": _list(item.get("source_refs")) if isinstance(item, dict) else [],
                    "legacy_migrated": True,
                }
            )

    normalized_claims = []
    for index, claim in enumerate(claims, start=1):
        statement = _text(claim.get("statement") or claim.get("content"))
        if not statement:
            continue
        normalized_claims.append(
            {
                **claim,
                "claim_id": _text(claim.get("claim_id") or claim.get("id")) or f"C{index}",
                "statement": statement,
                "claim_type": _text(claim.get("claim_type")) or "statement",
                "verification_status": _text(claim.get("verification_status")) or "unverified",
                "certainty": _text(claim.get("certainty")) or "unknown",
                "source_refs": _list(claim.get("source_refs")),
            }
        )

    return {
        "schema_version": 2,
        "source_documents": [dict(item) for item in _list(current.get("source_documents")) if isinstance(item, dict)],
        "claims": normalized_claims,
        "evidence": [dict(item) for item in _list(current.get("evidence")) if isinstance(item, dict)],
        "events": [dict(item) for item in _list(current.get("events")) if isinstance(item, dict)],
        "unresolved_questions": [
            dict(item) if isinstance(item, dict) else {"question": _text(item), "reason": "source_incomplete"}
            for item in _list(current.get("unresolved_questions")) or _list(source.get("inconsistencies"))
            if (_text(item.get("question")) if isinstance(item, dict) else _text(item))
        ],
    }


def assess_source_quality(text: Any) -> dict[str, Any]:
    """Make source ambiguity explicit instead of inviting the model to fill gaps."""
    source = _text(text)
    flags = []
    if len(source) < 80:
        flags.append("source_too_short")
    if source.count("?") + source.count("？") >= 3:
        flags.append("possible_ocr_or_redaction_loss")
    uncertainty_markers = ("不清楚", "没看清", "不详", "大概", "可能", "不确定", "不记得")
    if any(marker in source for marker in uncertainty_markers):
        flags.append("material_contains_explicit_uncertainty")
    if not any(marker in source for marker in ("时间", "时", "点", "昨", "今", "日")):
        flags.append("time_not_explicit")
    if not any(marker in source for marker in ("路", "街", "小区", "现场", "门", "店", "楼")):
        flags.append("location_not_explicit")
    return {
        "grade": "low" if len(flags) >= 3 else ("medium" if flags else "high"),
        "flags": flags,
        "policy": "specific_uncertainty_only" if flags else "source_grounded",
    }


def _find_person(structured: dict[str, Any], role_name: str) -> dict[str, Any]:
    for item in _list(structured.get("persons")):
        if isinstance(item, dict) and _text(item.get("name")) == role_name:
            return item
    return {}


def build_role_knowledge_view(
    structured: dict[str, Any] | None,
    *,
    role_name: str,
    role_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the only case-information view an actor model may receive."""
    structured = structured if isinstance(structured, dict) else {}
    role_payload = role_payload if isinstance(role_payload, dict) else {}
    person = _find_person(structured, role_name)
    combined = {**person, **role_payload}

    known = _dedupe_text(
        _list(combined.get("knows_facts"))
        + _list(combined.get("known_information"))
        + _list(combined.get("known_key_points"))
    )
    withheld = _dedupe_text(
        _list(combined.get("hidden_truths"))
        + _list(combined.get("hidden_information"))
        + _list(combined.get("withheld_key_points"))
    )
    unknown = _dedupe_text(
        _list(combined.get("does_not_know"))
        + _list(combined.get("cannot_answer"))
    )

    ledger = []
    claims = normalize_case_intelligence(structured)["claims"]
    role_event_ledger = [item for item in _list(combined.get("role_event_ledger")) if isinstance(item, dict)]
    explicit_ledger = role_event_ledger or [item for item in _list(combined.get("knowledge_ledger")) if isinstance(item, dict)]
    for index, item in enumerate(explicit_ledger, start=1):
        content = _text(item.get("content"))
        if not content:
            continue
        mode = _text(item.get("knowledge_mode")) or "known"
        ledger.append({
            **item,
            "knowledge_id": _text(item.get("knowledge_id")) or f"K{index}",
            "content": content,
            "knowledge_mode": mode,
            "sequence": item.get("sequence", index),
            "event_phase": _text(item.get("event_phase")) or "unknown",
            "event_phase_label": _text(item.get("event_phase_label")) or "相关情况",
            "time_hint": _text(item.get("time_hint")) or "未明确",
            "place_hint": _text(item.get("place_hint")) or "未明确",
            "actors": _list(item.get("actors")),
            "certainty": _text(item.get("certainty")) or "explicit_role_config",
            "source_refs": _list(item.get("source_refs")),
        })

    for mode, values, disclosure in (
        ("known", known, "answer_when_asked"),
        ("withheld", withheld, "withhold_until_triggered"),
        ("unknown", unknown, "must_not_assert"),
    ):
        for index, content in enumerate(values, start=1):
            matched = next(
                (claim for claim in claims if content in _text(claim.get("statement")) or _text(claim.get("statement")) in content),
                None,
            )
            ledger.append(
                {
                    "knowledge_id": f"{mode[:1].upper()}{index}",
                    "content": content,
                    "knowledge_mode": mode,
                    "claim_id": _text(matched.get("claim_id")) if matched else "",
                    "certainty": _text(matched.get("certainty")) if matched else "explicit_role_config",
                    "source_refs": _list(matched.get("source_refs")) if matched else [],
                    "disclosure_policy": disclosure,
                }
            )

    return {
        "role_name": role_name,
        "ledger": ledger,
        "known": known,
        "withheld": withheld,
        "unknown": unknown,
        "unresolved_questions": normalize_case_intelligence(structured)["unresolved_questions"],
        "role_information_version": _text(combined.get("role_information_version")),
        "quality_policy": {
            "unsupported_answer": "state_specific_uncertainty",
            "may_invent": False,
            "may_use_global_case_facts": False,
        },
    }


def format_role_knowledge_view(view: dict[str, Any]) -> str:
    def block(title: str, values: list[str], empty: str) -> list[str]:
        return [f"{title}：", *([f"- {item}" for item in values] or [f"- {empty}"])]

    lines = [f"角色：{_text(view.get('role_name')) or '相关人员'}"]
    for item in view.get("ledger") or []:
        if isinstance(item, dict) and _text(item.get("content")):
            lines.append(f"[{_text(item.get('knowledge_id'))}] {item.get('knowledge_mode')}：{_text(item.get('content'))}")
    lines += block("本人明确知道", _dedupe_text(_list(view.get("known"))), "暂无已配置的确定信息")
    lines += block("本人知道但当前可能隐瞒", _dedupe_text(_list(view.get("withheld"))), "无")
    lines += block("本人不知道或无法确认", _dedupe_text(_list(view.get("unknown"))), "未明确配置")
    lines += [
        "回答规则：只能依据以上角色知识和本轮公开听到的信息作答。",
        "材料不足时必须具体说明看见了什么、没看清什么、信息来自谁；不得补造时间、地点、人物或行为。",
    ]
    return "\n".join(lines)


def validate_supporting_knowledge_ids(
    view: dict[str, Any],
    ids: Any,
    *,
    require_support: bool = False,
) -> dict[str, Any]:
    requested = _dedupe_text(_list(ids))
    # The evidence ledger is populated from both legacy persona fields and the
    # source-document memory line.  A direct statement/observation is just as
    # valid a grounding source as a legacy `known` item.
    allowed_modes = {
        "known",
        "withheld",
        "direct_statement",
        "personal_experience",
        "direct_observation",
        "hearsay",
        "source_mention",
    }
    allowed = {
        _text(item.get("knowledge_id"))
        for item in view.get("ledger") or []
        if isinstance(item, dict)
        and _text(item.get("knowledge_mode")) in allowed_modes
        and _text(item.get("knowledge_id"))
    }
    invalid = [item for item in requested if item not in allowed]
    if require_support and allowed and not requested:
        invalid.append("missing_supporting_knowledge_id")
    return {"requested": requested, "valid": not invalid, "invalid": invalid, "allowed": sorted(allowed)}
