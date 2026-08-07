"""Question-first policy for role dialogue generation."""
from __future__ import annotations

from typing import Any

from .role_information_management_service import analyze_role_question


def build_dialogue_priority(user_text: str, history: list[Any]) -> dict[str, Any]:
    question = analyze_role_question(user_text)
    instructions = {
        "clarification": "这句话没有形成明确案件问题。不要主动讲案件内容，自然问清学员具体想了解什么。",
        "full_process": (
            "学员要了解完整经过。用自然口语从本人最早知道的缘由说起，顺着关键变化讲到本人所知的最后情况；"
            "不得只挑其中一段，也不要使用‘起因、经过、结果’等机械标题。"
        ),
        "beginning": "学员在追问事情如何开始。优先说明最早缘由和事前发生的关键事情，不要重复后段概述代替开头。",
        "outcome": "学员在追问后来或最终情况。承接已经说过的内容，补充本人所知的后续和结果，不要从头复读。",
        "time": "直接回答本人能确认的时间；只能确认大概范围时明确说是大概时间。",
        "location": "直接回答本人能确认的地点或位置，不知道精确位置时说明边界。",
        "actors": "直接回答本人知道或亲眼见到的相关人员，不替别人确认其未见行为。",
        "action": "直接说明当时在做什么、看见什么以及紧接着发生了什么。",
        "fact": "直接回答学员当前问题；只在回答需要时补充相关本人信息。",
    }
    return {
        "question_intent": question["intent"],
        "needs_clarification": question["needs_clarification"],
        "expansion_requested": question["intent"] == "full_process",
        "instruction": instructions[question["intent"]],
        "priority": (
            "1本人来源事实与认知边界；2学员当前问题和所需详略；3尚未回答的信息；"
            "4本轮公开信息；5互动状态；6人物画像只影响自然口吻。"
        ),
    }
