from __future__ import annotations

import json

from ai_workflow_service.contracts import SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.domain.evaluation_engine import build_adaptive_report
from ai_workflow_service.domain.training_runtime import evaluate_points
from ai_workflow_service.skills.base import Skill


class EvaluationSkill(Skill):
    name = SkillName.evaluation
    next_stage = WorkflowStage.evaluated

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(self, request: WorkflowRequest) -> dict:
        transcript = list(request.payload.get("transcript") or [])
        assessment_points = list(request.payload.get("assessment_points") or [])
        action_ids = [str(item.get("action_id") or item.get("id") or "") for item in request.payload.get("action_results") or [] if isinstance(item, dict)]
        completed = evaluate_points(assessment_points, transcript, action_ids)
        try:
            ai_review = self.llm.complete_json(
                system=("你是警务训练评估官。只依据结构化对话和考察点给出辅助审阅。输出 JSON："
                        "summary、common_reviews、strengths、improvements、suggestions。不得自行计算最终总分。"),
                user=json.dumps({"transcript": transcript, "assessment_points": completed, "knowledge_refs": request.payload.get("knowledge_refs") or []}, ensure_ascii=False),
                max_tokens=5000,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            ai_review = {}
        report = build_adaptive_report(
            transcript=transcript, point_results=completed, action_results=list(request.payload.get("action_results") or []),
            ai_review=ai_review, scene_type=str(request.payload.get("scene_type") or "通用"),
            rule_checks=dict(request.payload.get("rule_checks") or {}), report_header=dict(request.payload.get("report_header") or {}),
            knowledge_refs=[str(item) for item in request.payload.get("knowledge_refs") or []],
        )
        return {"rule_results": completed, "ai_review": ai_review, "report": report}
