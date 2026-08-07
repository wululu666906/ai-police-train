"""Retrieve ordered role information for the learner's current question."""
from __future__ import annotations

import re
from typing import Any

from .role_information_management_service import analyze_role_question, infer_event_phase, phase_order


def _text(value: Any) -> str:
    return str(value or "").strip()


def _terms(text: Any) -> set[str]:
    content = _text(text)
    clean = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", content)
    stopwords = {"一下", "什么", "怎么", "这个", "那个", "事情", "情况", "经过", "开始", "后来", "最后", "你们", "我们", "请问"}
    terms = {clean[index:index + 2] for index in range(max(0, len(clean) - 1))}
    terms.update(re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,6}", content))
    return {item for item in terms if item and item not in stopwords}


def _eligible(view: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_modes = {
        "known", "withheld", "direct_statement", "personal_statement", "personal_experience",
        "direct_observation", "hearsay", "later_learned", "source_mention",
    }
    result = []
    for index, raw in enumerate(view.get("ledger") or [], start=1):
        if not isinstance(raw, dict) or not _text(raw.get("content")):
            continue
        mode = _text(raw.get("knowledge_mode"))
        if mode not in allowed_modes:
            continue
        content = _text(raw.get("content"))
        if mode == "source_mention" and any(
            token in content for token in ("辨认笔录", "鉴定意见", "证据目录", "户籍证明", "判决书", "裁定书")
        ):
            continue
        item = dict(raw)
        item.setdefault("sequence", index)
        if _text(item.get("event_phase")) in {"", "unknown"}:
            item["event_phase"] = infer_event_phase(item)
        result.append(item)
    return result


def _history_contents(history: list[Any] | None, role_name: str) -> list[str]:
    contents: list[str] = []
    for message in (history or [])[-12:]:
        if _text(getattr(message, "role", "")) not in {"assistant", "ai"}:
            continue
        speaker = _text(getattr(message, "speaker_name", ""))
        if speaker and role_name and speaker != role_name:
            continue
        content = _text(getattr(message, "content", ""))
        if content:
            contents.append(content)
    return contents


def _was_covered(item: dict[str, Any], history_contents: list[str]) -> bool:
    item_terms = _terms(item.get("content"))
    if not item_terms:
        return False
    for content in history_contents:
        history_terms = _terms(content)
        if len(item_terms & history_terms) / max(1, min(len(item_terms), len(history_terms))) >= 0.55:
            return True
    return False


def _rank(items: list[dict[str, Any]], query: str, phases: list[str], history_contents: list[str]) -> list[dict[str, Any]]:
    query_terms = _terms(query)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(items):
        content_terms = _terms(item.get("content"))
        overlap = len(query_terms & content_terms)
        phase = _text(item.get("event_phase")) or "unknown"
        phase_bonus = 18 if phases and phase in phases else 0
        source_bonus = 4 if _text(item.get("knowledge_mode")) in {"personal_experience", "direct_observation", "direct_statement"} else 1
        covered_penalty = 14 if _was_covered(item, history_contents) else 0
        ranked.append((overlap * 8 + phase_bonus + source_bonus - covered_penalty, -index, item))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for score, _, item in ranked if score > 0]


def build_role_answer_context(
    view: dict[str, Any],
    query: str,
    *,
    history: list[Any] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    intent = analyze_role_question(query)
    if intent["needs_clarification"]:
        return {**intent, "items": [], "knowledge_ids": [], "matched": False}

    items = _eligible(view)
    history_contents = _history_contents(history, _text(view.get("role_name")))
    phases = list(intent.get("phases") or [])

    if intent["intent"] == "full_process":
        narrative_items = [item for item in items if _text(item.get("knowledge_mode")) != "source_mention"]
        covered_phases = {_text(item.get("event_phase")) for item in narrative_items}
        phase_supplements = [
            item
            for item in items
            if _text(item.get("knowledge_mode")) == "source_mention"
            and _text(item.get("event_phase")) not in covered_phases
            and not any(token in _text(item.get("content")) for token in ("辨认笔录", "鉴定意见", "证据目录"))
        ]
        selected = sorted(
            [*narrative_items, *phase_supplements] or items,
            key=lambda item: (phase_order(item.get("event_phase")), int(item.get("sequence", 10**9) or 10**9)),
        )
    elif phases:
        phase_items = [item for item in items if _text(item.get("event_phase")) in phases]
        selected = sorted(
            phase_items or _rank(items, query, phases, history_contents),
            key=lambda item: (phase_order(item.get("event_phase")), int(item.get("sequence", 10**9) or 10**9)),
        )
    elif intent["intent"] == "time":
        selected = [item for item in items if _text(item.get("time_hint")) not in {"", "未明确", "未知"}]
        selected = _rank(selected, query, [], history_contents)
    elif intent["intent"] == "location":
        selected = [item for item in items if _text(item.get("place_hint")) not in {"", "未明确", "未知"}]
        selected = _rank(selected, query, [], history_contents)
    elif intent["intent"] == "actors":
        selected = [item for item in items if item.get("actors")]
        selected = _rank(selected, query, [], history_contents)
    else:
        selected = _rank(items, query, [], history_contents)

    if intent["intent"] == "outcome":
        uncovered = [item for item in selected if not _was_covered(item, history_contents)]
        selected = uncovered or selected

    selected = selected[: max(1, limit)]
    return {
        **intent,
        "items": selected,
        "knowledge_ids": [_text(item.get("knowledge_id")) for item in selected if _text(item.get("knowledge_id"))],
        "matched": bool(selected),
    }


def retrieve_role_memories(
    view: dict[str, Any],
    query: str,
    *,
    history: list[Any] | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    return build_role_answer_context(view, query, history=history, limit=limit)["items"]


def format_retrieved_memories(
    view: dict[str, Any],
    query: str,
    *,
    history: list[Any] | None = None,
    limit: int = 8,
    max_chars: int = 4200,
) -> str:
    context = build_role_answer_context(view, query, history=history, limit=limit)
    if context["needs_clarification"]:
        return "当前输入没有形成可回答的案件问题，不得主动抛出案件事实；先自然询问学员具体想了解哪件事。"
    if not context["matched"]:
        return "本人信息中没有与当前问题相符的内容。具体说明自己不能确认哪一部分，不得拿无关记忆代替回答。"

    lines = [f"回答意图：{context['intent']}。以下信息已按本轮需要排序："]
    used = len(lines[0])
    for item in context["items"]:
        line = (
            f"[{_text(item.get('knowledge_id'))}｜{_text(item.get('event_phase_label')) or _text(item.get('event_phase'))}｜"
            f"{_text(item.get('knowledge_mode'))}｜{_text(item.get('time_hint')) or '时间未明确'}｜"
            f"{_text(item.get('place_hint')) or '地点未明确'}] {_text(item.get('content'))}"
        )
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    lines.extend((
        "先直接回答学员当前问题，只说本人知道的内容。",
        "完整经过要自然连贯地从最早缘由讲到本人所知的最后情况，不要念出后台阶段标签。",
        "没有对应信息时具体说明不知道哪一部分。",
    ))
    return "\n".join(lines)
