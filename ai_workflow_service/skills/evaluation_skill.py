from __future__ import annotations

import json

from ai_workflow_service.contracts import SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.skills.base import Skill


class EvaluationSkill(Skill):
    name = SkillName.evaluation
    next_stage = WorkflowStage.evaluated

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(self, request: WorkflowRequest) -> dict:
        transcript = list(request.payload.get("transcript") or [])
        assessment_points = list(request.payload.get("assessment_points") or [])
        completed = []
        corpus = "\n".join(str(item.get("content") or "") for item in transcript if item.get("role") == "user")
        for point in assessment_points:
            keywords = [str(item) for item in point.get("keywords") or []]
            completed.append({**point, "rule_hit": any(word and word in corpus for word in keywords)})
        ai_review = self.llm.complete_json(
            system="评估警情处置训练。只依据对话和考核点，输出 summary、dimensions、deductions、suggestions。",
            user=json.dumps({"transcript": transcript, "assessment_points": completed}, ensure_ascii=False),
            max_tokens=5000,
        )
        return {"rule_results": completed, "ai_review": ai_review}
