"""Platform AI role registry — each role has a dedicated prompt module and duty boundary."""

from __future__ import annotations

from typing import Any

from .prompts.assessment_point_officer import (
    ASSESSMENT_POINT_OFFICER_ROLE,
    ASSESSMENT_POINT_OFFICER_SYSTEM_PROMPT,
    ASSESSMENT_POINT_OFFICER_USER_TEMPLATE,
)
from .case_completion_service import CASE_COMPLETION_PROMPT, CASE_OFFICER_ROLE

# Role id → metadata (prompt text loaded from module constants)
AI_ROLES: dict[str, dict[str, Any]] = {
    "case_completion_officer": {
        "id": "case_completion_officer",
        "role_name": CASE_OFFICER_ROLE,
        "duty": "根据案件原文补全表单空白字段（基础信息、人物、场景骨架）。",
        "prompt_module": "case_completion_service.CASE_COMPLETION_PROMPT",
        "consumer": "POST /cases/ai-complete",
    },
    "assessment_point_officer": {
        "id": "assessment_point_officer",
        "role_name": ASSESSMENT_POINT_OFFICER_ROLE,
        "duty": "根据案件与场景列表，为接警/现场/询问三场景分别生成考察点并分桶输出。",
        "prompt_module": "prompts.assessment_point_officer",
        "system_prompt": ASSESSMENT_POINT_OFFICER_SYSTEM_PROMPT,
        "user_template": ASSESSMENT_POINT_OFFICER_USER_TEMPLATE,
        "consumer": "POST /cases/assessment-points/distribute",
        "scene_buckets": ["intake", "onsite", "investigation"],
        "scene_bucket_labels": {"intake": "接警", "onsite": "现场", "investigation": "询问"},
        "standard_scene_names": {
            "intake": "接警研判",
            "onsite": "现场处置",
            "investigation": "重点询问",
        },
    },
    "training_dialogue_role": {
        "id": "training_dialogue_role",
        "role_name": "训练对话角色",
        "duty": "学员训练时扮演现场人物，遵守人设与四轴状态契约。",
        "prompt_module": "ai_service.SYSTEM_PROMPT_TEMPLATE",
        "consumer": "POST /training/chat",
    },
    "multi_role_director": {
        "id": "multi_role_director",
        "role_name": "多角色导演",
        "duty": "决定同一场景多角色发言顺序，不写台词。",
        "prompt_module": "multi_role_director",
        "consumer": "训练多角色链路",
    },
    "evaluation_officer": {
        "id": "evaluation_officer",
        "role_name": "训练评估官",
        "duty": "根据对话与考察点要求表出具结构化评分。",
        "prompt_module": "evaluation_service.EVALUATION_PROMPT_TEMPLATE",
        "consumer": "训练结束评估",
    },
}


def list_ai_roles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in AI_ROLES.values():
        row = {k: v for k, v in role.items() if k not in {"system_prompt", "user_template"}}
        rows.append(row)
    return rows


def get_assessment_point_officer_prompts() -> dict[str, str]:
    return {
        "role_name": ASSESSMENT_POINT_OFFICER_ROLE,
        "system_prompt": ASSESSMENT_POINT_OFFICER_SYSTEM_PROMPT,
        "user_template": ASSESSMENT_POINT_OFFICER_USER_TEMPLATE,
    }
