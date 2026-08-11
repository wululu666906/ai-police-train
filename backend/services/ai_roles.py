"""Platform AI role registry — aligned with the case-generation flowchart."""

from __future__ import annotations

from typing import Any

from .prompts.case_pipeline import (
    ASSESSMENT_POINT_PROMPT,
    COMPLETE_CASE_STORY_PROMPT,
    FACTS_ROLES_MEMORIES_PROMPT,
    SCENE_BLUEPRINT_PROMPT,
)

AI_ROLES: dict[str, dict[str, Any]] = {
    # ── 案件生成流水线（A→H）──
    "source_cleaner": {
        "id": "source_cleaner",
        "role_name": "文本清洗",
        "duty": "去除非案件信息，保留可训练正文。",
        "prompt_module": "case_source_compaction_service（规则）",
        "consumer": "案件导入流水线 B",
    },
    "complete_case_story_writer": {
        "id": "complete_case_story_writer",
        "role_name": "完整案件剧情生成",
        "duty": "依据清洗后原文生成完整剧情与基础案件元数据（合并原结构化解析）。",
        "prompt_module": "prompts.case_pipeline.COMPLETE_CASE_STORY_PROMPT",
        "system_prompt": COMPLETE_CASE_STORY_PROMPT,
        "consumer": "案件导入流水线 C",
    },
    "facts_roles_memories_extractor": {
        "id": "facts_roles_memories_extractor",
        "role_name": "事实解析与角色记忆",
        "duty": "从完整剧情提取事实、人物与角色记忆（合并人名识别）。",
        "prompt_module": "workflow_service.parse_case_for_training / prompts.case_pipeline.FACTS_ROLES_MEMORIES_PROMPT",
        "system_prompt": FACTS_ROLES_MEMORIES_PROMPT,
        "consumer": "案件导入流水线 D",
    },
    "story_world_builder": {
        "id": "story_world_builder",
        "role_name": "案件故事世界",
        "duty": "汇总完整剧情、事实与角色记忆为训练世界载体。",
        "prompt_module": "case_pipeline_service._build_story_world_payload",
        "consumer": "案件导入流水线 E",
    },
    "scene_blueprint_planner": {
        "id": "scene_blueprint_planner",
        "role_name": "场景蓝图生成",
        "duty": "按场景训练目标、角色、接警简报与现场第一印象生成蓝图。",
        "prompt_module": "prompts.case_pipeline.SCENE_BLUEPRINT_PROMPT",
        "system_prompt": SCENE_BLUEPRINT_PROMPT,
        "consumer": "案件导入流水线 F",
    },
    "role_info_reader": {
        "id": "role_info_reader",
        "role_name": "角色信息读取",
        "duty": "为回复组装角色记忆、角色信息、事实与上下文。",
        "prompt_module": "role_generation_context_service / role_memory_retrieval_service",
        "consumer": "训练运行时 G",
    },
    # ── 训练运行时（G→H）──
    "training_dialogue_role": {
        "id": "training_dialogue_role",
        "role_name": "训练对话角色",
        "duty": "扮演现场人物生成回复；开场发言亦由此角色承担。",
        "prompt_module": "ai_service.SYSTEM_PROMPT_TEMPLATE",
        "guardrails": "prompts.guardrails.DIALOGUE_ROLE_GUARDRAILS",
        "consumer": "POST /training/chat 与开场轮",
    },
    "multi_role_actor": {
        "id": "multi_role_actor",
        "role_name": "多角色演员",
        "duty": "多角色场景下为单个现场人物生成自然台词。",
        "prompt_module": "multi_role_actor.ROLE_ACTOR_PROMPT",
        "guardrails": "prompts.guardrails.DIALOGUE_ROLE_GUARDRAILS",
        "consumer": "训练多角色链路",
    },
    "multi_role_director": {
        "id": "multi_role_director",
        "role_name": "多角色导演",
        "duty": "决定同一场景多角色发言顺序，不写台词。",
        "prompt_module": "multi_role_director.DIRECTOR_ORCHESTRATION_PROMPT",
        "guardrails": "prompts.guardrails.DIRECTOR_GUARDRAILS",
        "consumer": "训练多角色链路",
    },
    "assessment_point_generator": {
        "id": "assessment_point_generator",
        "role_name": "考察点生成",
        "duty": "根据完整剧情与本场景训练目标直接生成考察点（不分桶编排）。",
        "prompt_module": "prompts.case_pipeline.ASSESSMENT_POINT_PROMPT",
        "system_prompt": ASSESSMENT_POINT_PROMPT,
        "guardrails": "prompts.guardrails.ADMIN_JSON_GUARDRAILS",
        "consumer": "POST /cases/assessment-points/generate",
    },
    "evaluation_officer": {
        "id": "evaluation_officer",
        "role_name": "训练评估官",
        "duty": "根据对话与考察点要求表出具结构化评分。",
        "prompt_module": "evaluation_service.EVALUATION_PROMPT_TEMPLATE",
        "guardrails": "prompts.guardrails.EVALUATION_GUARDRAILS",
        "consumer": "训练结束评估",
    },
    "recommended_questions_coach": {
        "id": "recommended_questions_coach",
        "role_name": "追问话术教练",
        "duty": "为学员生成可直接说出口的追问句。",
        "prompt_module": "recommended_questions_service（内联）",
        "guardrails": "prompts.guardrails.COACH_SPEECH_GUARDRAILS",
        "consumer": "训练页推荐追问",
    },
    "video_training_analyst": {
        "id": "video_training_analyst",
        "role_name": "视频训练分析",
        "duty": "分析执法示范视频并编排交互训练节点。",
        "prompt_module": "video_auto_config_service（内联）",
        "consumer": "视频训练配置",
    },
    "video_semantic_evaluator": {
        "id": "video_semantic_evaluator",
        "role_name": "视频语义评估",
        "duty": "判断学员回答是否语义覆盖处置要点。",
        "prompt_module": "video_training._LLM_SEMANTIC_RESCUE_PROMPT",
        "guardrails": "prompts.guardrails.EVALUATION_GUARDRAILS",
        "consumer": "视频训练评分兜底",
    },
}


def list_ai_roles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in AI_ROLES.values():
        row = {k: v for k, v in role.items() if k not in {"system_prompt", "user_template"}}
        rows.append(row)
    return rows
