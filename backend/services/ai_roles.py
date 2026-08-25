"""Agent 工作流 Skill 目录。"""

from __future__ import annotations

from typing import Any

AI_ROLES: dict[str, dict[str, Any]] = {
    skill: {"id": skill, "role_name": label, "duty": duty, "consumer": "ai_workflow_service"}
    for skill, label, duty in (
        ("case_import_harness", "案件导入 Harness", "完成清洗、剧情、事实、人物、记忆与场景蓝图闭环。"),
        ("role_simulation", "角色推演 Skill", "TinyTroupe 多角色世界推演；DeepSeek 只做事实审计，不改写台词。"),
        ("evaluation", "训练评估 Skill", "规则评分与 AI 分析。"),
        ("report", "报告生成 Skill", "生成可归档训练报告。"),
    )
}


def list_ai_roles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in AI_ROLES.values():
        row = {k: v for k, v in role.items() if k not in {"system_prompt", "user_template"}}
        rows.append(row)
    return rows
