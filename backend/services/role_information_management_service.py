"""Compile source memories into ordered, queryable role information."""
from __future__ import annotations

import copy
import re
from typing import Any


ROLE_INFORMATION_VERSION = "role_information_v3"

_PHASE_ORDER = {
    "origin": 10,
    "preparation": 20,
    "action": 30,
    "escalation": 40,
    "intervention": 50,
    "outcome": 60,
    "aftermath": 70,
    "unknown": 80,
}

_PHASE_LABELS = {
    "origin": "事情缘由",
    "preparation": "事前准备",
    "action": "主要行为",
    "escalation": "事态发展",
    "intervention": "报警或介入",
    "outcome": "当时结果",
    "aftermath": "事后情况",
    "unknown": "相关情况",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalized(value: Any) -> str:
    return re.sub(r"[\s，。！？,.!?、；;：:\"'（）()]+", "", _text(value))


def _clean_statement(value: Any) -> str:
    statement = _text(value)
    statement = re.sub(
        r"^\s*[（(]?\d+[、.．]?\s*[^，。；:：]{0,30}(?:证言|陈述|供述|辩解|询问笔录|讯问笔录)[，,:：]?\s*",
        "",
        statement,
    )
    return statement.strip(" ）)\t\r\n")


def _source_start(memory: dict[str, Any], fallback: int) -> int:
    starts = [
        ref.get("start")
        for ref in _items(memory.get("source_refs"))
        if isinstance(ref, dict) and isinstance(ref.get("start"), int)
    ]
    return min(starts) if starts else fallback


def infer_event_phase(memory: dict[str, Any]) -> str:
    text = " ".join(
        filter(
            None,
            (
                _text(memory.get("statement") or memory.get("content")),
                _text(memory.get("time_hint")),
            ),
        )
    )
    rules = (
        ("aftermath", ("事后", "后来得知", "之后得知", "庭审", "赔偿", "鉴定", "送医后", "到案后")),
        ("preparation", ("开会", "商量", "通知", "召集", "喊每家", "前一天", "头一天")),
        ("origin", ("起因", "因为", "此前", "之前", "清明前后", "3月份", "三月份", "矛盾", "纠纷", "阻止", "认为不能")),
        ("intervention", ("报警", "民警", "公安", "政府", "工作人员", "救护车", "送医", "赶到现场", "到场处置")),
        ("escalation", ("争吵", "冲突", "打斗", "动手", "持刀", "受伤", "砍伤", "围堵", "追赶", "毁坏")),
        ("action", ("前往", "赶往", "到达", "上山", "拔", "砍", "跟着", "参与", "实施", "看见")),
        ("outcome", ("最终", "最后", "散去", "离开", "死亡", "被抓", "被带走", "下山", "签字", "结束")),
        ("preparation", ("准备", "拿刀", "拿柴刀", "出发")),
    )
    for phase, markers in rules:
        if any(marker in text for marker in markers):
            return phase
    return "unknown"


def _response_facets(memory: dict[str, Any], phase: str) -> list[str]:
    content = _text(memory.get("statement") or memory.get("content"))
    facets = [phase]
    if _text(memory.get("time_hint")) and _text(memory.get("time_hint")) not in {"未明确", "未知"}:
        facets.append("time")
    if _text(memory.get("place_hint")) and _text(memory.get("place_hint")) not in {"未明确", "未知"}:
        facets.append("location")
    if _items(memory.get("actors")):
        facets.append("actors")
    if any(token in content for token in ("为什么", "因为", "起因", "矛盾", "之前")):
        facets.append("reason")
    if any(token in content for token in ("最后", "最终", "后来", "之后", "结果", "下山", "离开")):
        facets.append("result")
    return list(dict.fromkeys(facets))


def compile_person_role_information(person: dict[str, Any]) -> dict[str, Any]:
    """Normalize one newly parsed person without changing legacy cases on read."""
    output = copy.deepcopy(person or {})
    name = _text(output.get("name")) or "相关人员"
    memories = [dict(item) for item in _items(output.get("role_memories")) if isinstance(item, dict)]
    memories.sort(key=lambda item: _source_start(item, 10**9))

    unique: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for index, memory in enumerate(memories, start=1):
        statement = _clean_statement(memory.get("statement") or memory.get("content"))
        if not statement:
            continue
        fingerprint = (_source_start(memory, index), _normalized(statement))
        if fingerprint in seen:
            continue
        normalized_statement = fingerprint[1]
        if any(
            len(normalized_statement) >= 40
            and len(existing_statement) >= 40
            and (normalized_statement in existing_statement or existing_statement in normalized_statement)
            for _, existing_statement in seen
        ):
            continue
        seen.add(fingerprint)
        memory["statement"] = statement
        memory["content"] = statement
        unique.append(memory)

    ledger: list[dict[str, Any]] = []
    normalized_memories: list[dict[str, Any]] = []
    for sequence, memory in enumerate(unique, start=1):
        knowledge_id = f"{name}-R{sequence}"
        phase = infer_event_phase(memory)
        normalized_memory = {
            **memory,
            "memory_id": knowledge_id,
            "statement": _text(memory.get("statement") or memory.get("content")),
            "content": _text(memory.get("statement") or memory.get("content")),
            "sequence": sequence,
            "event_phase": phase,
            "event_phase_label": _PHASE_LABELS[phase],
            "information_version": ROLE_INFORMATION_VERSION,
        }
        normalized_memories.append(normalized_memory)
        ledger.append(
            {
                "knowledge_id": knowledge_id,
                "claim_id": _text(memory.get("event_id")),
                "sequence": sequence,
                "event_phase": phase,
                "event_phase_label": _PHASE_LABELS[phase],
                "knowledge_mode": _text(memory.get("memory_type")) or "source_mention",
                "content": normalized_memory["statement"],
                "time_hint": _text(memory.get("time_hint")) or "未明确",
                "place_hint": _text(memory.get("place_hint")) or "未明确",
                "actors": [_text(item) for item in _items(memory.get("actors")) if _text(item)],
                "certainty": _text(memory.get("certainty")) or "source_supported",
                "disclosure_policy": _text(memory.get("disclosure_policy")) or "answer_when_asked",
                "response_facets": _response_facets(memory, phase),
                "source_refs": copy.deepcopy(_items(memory.get("source_refs"))),
                "information_version": ROLE_INFORMATION_VERSION,
            }
        )

    output["role_memories"] = normalized_memories
    output["knowledge_ledger"] = copy.deepcopy(ledger)
    output["role_event_ledger"] = ledger
    output["role_information_version"] = ROLE_INFORMATION_VERSION
    return output


def compile_role_information(persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [compile_person_role_information(person) for person in persons if isinstance(person, dict)]


def analyze_role_question(user_text: str) -> dict[str, Any]:
    text = _text(user_text)
    compact = _normalized(text)
    if not text or (not re.search(r"[\u4e00-\u9fffA-Za-z]", text) and len(compact) <= 8):
        return {"intent": "clarification", "confidence": 0.0, "phases": [], "needs_clarification": True}

    full_terms = ("全过程", "完整经过", "详细经过", "事情经过", "从头说", "说清楚", "详细一点", "前因后果", "怎么回事", "发生了什么")
    beginning_terms = ("怎么开始", "如何开始", "事情的开始", "一开始", "最开始", "起因", "缘由", "为什么会", "之前发生")
    outcome_terms = ("后来呢", "后来怎么样", "最后呢", "最终", "结尾", "结果", "怎么结束", "事后")
    if any(term in text for term in full_terms):
        return {"intent": "full_process", "confidence": 1.0, "phases": list(_PHASE_ORDER), "needs_clarification": False}
    if any(term in text for term in beginning_terms):
        return {"intent": "beginning", "confidence": 1.0, "phases": ["origin", "preparation"], "needs_clarification": False}
    if any(term in text for term in outcome_terms):
        return {"intent": "outcome", "confidence": 1.0, "phases": ["outcome", "aftermath"], "needs_clarification": False}
    if any(term in text for term in ("什么时候", "几点", "时间", "哪天")):
        return {"intent": "time", "confidence": 1.0, "phases": [], "needs_clarification": False}
    if any(term in text for term in ("在哪里", "哪儿", "哪里", "地点", "位置")):
        return {"intent": "location", "confidence": 1.0, "phases": [], "needs_clarification": False}
    if any(term in text for term in ("谁", "哪些人", "什么人", "你们")):
        return {"intent": "actors", "confidence": 0.85, "phases": [], "needs_clarification": False}
    if any(term in text for term in ("干嘛", "做什么", "做了什么", "怎么做", "什么情况", "经过")):
        return {"intent": "action", "confidence": 0.85, "phases": ["action", "escalation"], "needs_clarification": False}
    return {"intent": "fact", "confidence": 0.55, "phases": [], "needs_clarification": False}


def phase_order(phase: Any) -> int:
    return _PHASE_ORDER.get(_text(phase), _PHASE_ORDER["unknown"])
