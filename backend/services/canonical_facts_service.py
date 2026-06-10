"""Shared canonical case facts for multi-role dialogue consistency."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import models


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_structured(case: models.Case | None) -> dict[str, Any]:
    if not case or not case.structured_data:
        return {}
    try:
        payload = json.loads(case.structured_data)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def extract_canonical_facts(
    case: models.Case | None,
    scene: models.Scene | None = None,
) -> dict[str, Any]:
    structured = _safe_structured(case)
    fact_sheet = structured.get("fact_sheet") if isinstance(structured.get("fact_sheet"), dict) else {}

    case_time = _text(fact_sheet.get("case_time"))
    case_location = _text(fact_sheet.get("case_location"))
    report_time = _text(fact_sheet.get("report_time"))

    if not case_time:
        for item in _text_list(structured.get("timeline")):
            if re.search(r"\d|时|点|分|昨|今|晚|早", item):
                case_time = item
                break
    if not case_location:
        case_location = _first_location_from_text(
            " ".join(
                filter(
                    None,
                    [
                        _text(getattr(scene, "dispatch_brief", "")),
                        _text(getattr(scene, "first_impression", "")),
                        _text(getattr(case, "background", "")),
                        _text(structured.get("full_narrative")),
                    ],
                )
            )
        )

    timeline = _text_list(fact_sheet.get("timeline")) or _text_list(structured.get("timeline"))
    key_facts = _text_list(structured.get("key_facts"))[:4]

    return {
        "case_time": case_time or "未明确",
        "case_location": case_location or "未明确",
        "report_time": report_time or "未明确",
        "timeline": timeline,
        "key_facts": key_facts,
    }


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if _text(value):
        return [_text(value)]
    return []


def _first_location_from_text(text: str) -> str:
    if not text:
        return ""
    patterns = (
        r"[\u4e00-\u9fa5A-Za-z0-9]+(?:路|街|巷|道|交叉口|路口|小区|市场|广场|店|门口|现场|附近)",
        r"在([^，。；、\s]{2,24})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _text(match.group(1) if match.lastindex else match.group(0))
    return ""


def format_canonical_facts_block(
    case: models.Case | None,
    scene: models.Scene | None = None,
) -> str:
    facts = extract_canonical_facts(case, scene)
    lines = [
        f"- 标准案发时间：{facts['case_time']}",
        f"- 标准案发地点：{facts['case_location']}",
        f"- 报警/接警时间：{facts['report_time']}",
    ]
    if facts["timeline"]:
        lines.append(f"- 时间线摘要：{'；'.join(facts['timeline'][:3])}")
    if facts["key_facts"]:
        lines.append(f"- 关键事实：{'；'.join(facts['key_facts'][:3])}")
    lines.append(
        "- 同一案件内，所有角色对时间、地点等客观要素不得互相矛盾；"
        "记不清可说「大概」，但不得换成不同路口/不同小时段。"
    )
    return "\n".join(lines)


def format_peer_utterances_block(peer_utterances: list[dict[str, Any]]) -> str:
    if not peer_utterances:
        return "（本轮尚无其他角色发言）"
    lines: list[str] = []
    for item in peer_utterances:
        name = _text(item.get("speaker_name")) or "其他角色"
        for utterance in item.get("utterances") or []:
            content = _text(utterance.get("content") if isinstance(utterance, dict) else utterance)
            if content:
                lines.append(f"- {name}：{content}")
    return "\n".join(lines) if lines else "（本轮尚无其他角色发言）"


def merge_role_knows_facts(role: models.Role, case: models.Case | None) -> str:
    facts = extract_canonical_facts(case)
    existing = _text_list(getattr(role, "knows_facts", None))
    merged = list(existing)
    role_type = _text(getattr(role, "role_type", ""))
    for label, value in (
        ("案发时间", facts["case_time"]),
        ("案发地点", facts["case_location"]),
    ):
        if value and value != "未明确" and not any(value in item or label in item for item in merged):
            if any(token in role_type for token in ("报警", "被害", "受害", "证", "嫌疑", "当事")):
                merged.append(f"{label}：{value}")
    return "、".join(merged) if merged else "（无）"
