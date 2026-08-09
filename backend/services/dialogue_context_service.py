"""LangGraph-backed layered context over the durable SQL transcript."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # Allows an in-place deployment before dependencies are installed.
    END = START = StateGraph = None

CONTEXT_VERSION = "langgraph_layered_v1"
RECENT_RAW_COUNT = 12
RELEVANT_EARLIER_COUNT = 10


class ContextState(TypedDict, total=False):
    history: list[Any]
    previous_context: dict[str, Any]
    current_query: str
    target_role_name: str
    rows: list[dict[str, Any]]
    recent_messages: list[dict[str, Any]]
    earlier_messages: list[dict[str, Any]]
    relevant_messages: list[dict[str, Any]]
    role_threads: dict[str, list[dict[str, Any]]]
    running_summary: str
    result: dict[str, Any]


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _speaker(message: Any) -> str:
    role = _text(getattr(message, "role", ""))
    if role == "user":
        return "学员"
    if role == "action":
        return "动作"
    return _text(getattr(message, "speaker_name", "")) or "现场角色"


def _message_row(message: Any, fallback_id: int) -> dict[str, Any] | None:
    content = _text(getattr(message, "content", ""))
    if not content:
        return None
    return {
        "id": int(getattr(message, "id", None) or fallback_id),
        "role": _text(getattr(message, "role", "")),
        "speaker": _speaker(message),
        "speaker_role_id": getattr(message, "speaker_role_id", None),
        "content": content,
    }


def _hydrate_node(state: ContextState) -> dict[str, Any]:
    rows = [
        row
        for index, message in enumerate(state.get("history") or [], start=1)
        if (row := _message_row(message, -index)) is not None
    ]
    return {
        "rows": rows,
        "recent_messages": rows[-RECENT_RAW_COUNT:],
        "earlier_messages": rows[:-RECENT_RAW_COUNT],
    }


def _terms(value: str) -> set[str]:
    value = _text(value).lower()
    latin = set(re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}", value))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", value))
    latin.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in latin if item}


def _relevance_node(state: ContextState) -> dict[str, Any]:
    query_terms = _terms(f"{state.get('current_query', '')} {state.get('target_role_name', '')}")
    earlier = state.get("earlier_messages") or []
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(earlier):
        overlap = len(query_terms & _terms(f"{row.get('speaker', '')} {row.get('content', '')}"))
        target_bonus = 3 if state.get("target_role_name") and row.get("speaker") == state.get("target_role_name") else 0
        if overlap or target_bonus:
            ranked.append((overlap + target_bonus, index, row))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    relevant = [item[2] for item in ranked[:RELEVANT_EARLIER_COUNT]]
    relevant.sort(key=lambda item: item.get("id", 0))
    return {"relevant_messages": relevant}


def _summary_node(state: ContextState) -> dict[str, Any]:
    earlier = state.get("earlier_messages") or []
    if not earlier:
        return {"running_summary": "暂无较早对话。"}
    lines = [f"{row['speaker']}：{row['content']}" for row in earlier]
    # This is a working digest only. SQL rows remain complete and are recalled raw.
    summary = "\n".join(lines)
    if len(summary) > 8000:
        summary = f"{summary[:3900]}\n（中段由相关原文召回）\n{summary[-3900:]}"
    return {"running_summary": summary}


def _project_node(state: ContextState) -> dict[str, Any]:
    rows = state.get("rows") or []
    role_threads: dict[str, list[dict[str, Any]]] = {}
    role_names = {row["speaker"] for row in rows if row["role"] in {"assistant", "ai"}}
    for role_name in role_names:
        role_threads[role_name] = [
            row for row in rows
            if row["role"] in {"user", "action"} or row["speaker"] == role_name
        ]
    role_summaries = {
        role_name: {
            "turn_count": sum(1 for row in thread if row["speaker"] == role_name),
            "last_utterance": next((row["content"] for row in reversed(thread) if row["speaker"] == role_name), ""),
        }
        for role_name, thread in role_threads.items()
    }
    open_loops = []
    if rows and rows[-1]["role"] in {"user", "action"}:
        open_loops.append({"message_id": rows[-1]["id"], "content": rows[-1]["content"]})
    result = {
        "version": CONTEXT_VERSION,
        "message_count": len(rows),
        "last_message_id": rows[-1]["id"] if rows else None,
        "running_summary": state.get("running_summary") or "暂无较早对话。",
        "recent_messages": state.get("recent_messages") or [],
        "relevant_messages": state.get("relevant_messages") or [],
        "role_threads": role_threads,
        "role_summaries": role_summaries,
        "open_loops": open_loops,
    }
    return {"role_threads": role_threads, "result": result}


def _build_graph():
    if StateGraph is None:
        return None
    builder = StateGraph(ContextState)
    builder.add_node("hydrate", _hydrate_node)
    builder.add_node("summarize", _summary_node)
    builder.add_node("retrieve", _relevance_node)
    builder.add_node("project", _project_node)
    builder.add_edge(START, "hydrate")
    builder.add_edge("hydrate", "summarize")
    builder.add_edge("summarize", "retrieve")
    builder.add_edge("retrieve", "project")
    builder.add_edge("project", END)
    return builder.compile()


_CONTEXT_GRAPH = _build_graph()


def build_agent_context(
    history: list[Any],
    *,
    previous_context: dict[str, Any] | None = None,
    current_query: str = "",
    target_role_name: str = "",
) -> dict[str, Any]:
    state: ContextState = {
        "history": history or [],
        "previous_context": previous_context or {},
        "current_query": current_query,
        "target_role_name": target_role_name,
    }
    if _CONTEXT_GRAPH is not None:
        output = _CONTEXT_GRAPH.invoke(state)
        return output.get("result") or {}
    state.update(_hydrate_node(state))
    state.update(_summary_node(state))
    state.update(_relevance_node(state))
    state.update(_project_node(state))
    return state.get("result") or {}


def format_agent_context(context: dict[str, Any] | None) -> str:
    context = context if isinstance(context, dict) else {}
    lines = [f"累计消息数：{int(context.get('message_count') or 0)}"]
    summary = _text(context.get("running_summary"))
    if summary:
        lines.extend(["较早对话工作摘要：", summary])
    relevant = context.get("relevant_messages") if isinstance(context.get("relevant_messages"), list) else []
    if relevant:
        lines.append("与当前问题相关的较早原文：")
        lines.extend(f"- {item.get('speaker') or '未知'}：{item.get('content') or ''}" for item in relevant)
    recent = context.get("recent_messages") if isinstance(context.get("recent_messages"), list) else []
    if recent:
        lines.append("最近对话原文：")
        lines.extend(f"- {item.get('speaker') or '未知'}：{item.get('content') or ''}" for item in recent)
    return "\n".join(lines)


def build_conversation_summary(history: list[Any]) -> dict[str, Any]:
    """Compatibility wrapper for callers outside the multi-role pipeline."""
    return build_agent_context(history)


def format_conversation_summary(summary: dict[str, Any] | None, max_chars: int = 0) -> str:
    return format_agent_context(summary)


def normalize_spoken_line(value: Any) -> str:
    text = _text(value).lower()
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return re.sub(r"^(嗯|啊|这个|那个|我说|就是说)+", "", text)


def spoken_similarity(left: Any, right: Any) -> float:
    a = normalize_spoken_line(left)
    b = normalize_spoken_line(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def find_repetition(
    content: str,
    *,
    speaker_name: str,
    history: list[Any],
    peer_utterances: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    candidates: list[tuple[str, str]] = []
    for message in history or []:
        if _text(getattr(message, "role", "")) not in {"assistant", "ai"}:
            continue
        previous = _text(getattr(message, "content", ""))
        if previous:
            candidates.append((_text(getattr(message, "speaker_name", "")) or "现场角色", previous))
    for actor in peer_utterances or []:
        peer_name = _text(actor.get("speaker_name")) or "现场角色"
        for utterance in actor.get("utterances") or []:
            previous = _text(utterance.get("content") if isinstance(utterance, dict) else utterance)
            if previous:
                candidates.append((peer_name, previous))

    strongest: dict[str, Any] | None = None
    for previous_speaker, previous in candidates:
        similarity = spoken_similarity(content, previous)
        threshold = 0.78 if previous_speaker == speaker_name else 0.86
        if similarity >= threshold and (strongest is None or similarity > strongest["similarity"]):
            strongest = {
                "speaker_name": previous_speaker,
                "content": previous,
                "similarity": round(similarity, 3),
                "threshold": threshold,
            }
    return strongest
