from __future__ import annotations

import json

from pydantic import TypeAdapter

from ai_workflow_service.contracts import CaseWorld, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.skills.base import Skill


class CaseParseSkill(Skill):
    name = SkillName.case_parse
    next_stage = WorkflowStage.case_parsed

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(self, request: WorkflowRequest) -> dict:
        source_text = str(request.payload.get("source_text") or "").strip()
        if not source_text:
            raise WorkflowServiceError("INVALID_CASE_SOURCE", "案件原文不能为空")
        result = self.llm.complete_json(
            system="提取案件世界模型。事实必须可追溯，不得虚构。只输出 JSON。",
            user=json.dumps({"case_id": request.case_id or request.workflow_id, "source_text": source_text}, ensure_ascii=False),
            max_tokens=8000,
        )
        result.setdefault("case_id", request.case_id or request.workflow_id)
        world = CaseWorld.model_validate(result)
        return {"case_world": world.model_dump(mode="json")}
