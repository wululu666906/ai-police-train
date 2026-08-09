"""Compile the shared full-story context used by every role actor call."""
from __future__ import annotations

from typing import Any

from .case_knowledge_service import load_case_knowledge_bundle


def _text(value: Any) -> str:
    return str(value or "").strip()


def format_full_story_block(source: dict[str, Any]) -> str:
    content = _text(source.get("content"))
    if not content:
        return (
            "完整剧情数据源缺失。只能依据角色专属知识、现场公开信息和对话历史回答；"
            "不得自行补全案件事实。"
        )
    return "\n".join(
        (
            f"数据源：{_text(source.get('source')) or 'unknown'}；内容哈希：{_text(source.get('content_hash')) or 'unknown'}",
            "以下全文是本案全局逻辑基准。先用它核对时间、地点、人物关系、因果和前后结果。",
            "它不等于当前角色全部知情：角色台词仍只能披露角色专属知识或本轮公开信息。",
            "--- 完整剧情开始 ---",
            content,
            "--- 完整剧情结束 ---",
        )
    )


def compile_role_generation_context(case: Any, role: Any) -> dict[str, Any]:
    """Force-load the current case story and role-scoped knowledge together."""
    bundle = load_case_knowledge_bundle(case, role)
    story_source = bundle.get("complete_story_source") if isinstance(bundle, dict) else {}
    story_source = story_source if isinstance(story_source, dict) else {}
    return {
        "full_story_block": format_full_story_block(story_source),
        "full_story_source": story_source,
        "role_knowledge_block": _text(bundle.get("knowledge_block")) or "暂无角色专属案件知识",
        "role_knowledge_view": bundle.get("role_knowledge_view") or {},
        "documents": bundle.get("documents") or [],
    }
