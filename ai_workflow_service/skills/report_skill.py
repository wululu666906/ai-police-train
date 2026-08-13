from __future__ import annotations

from datetime import datetime, timezone

from ai_workflow_service.contracts import SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.skills.base import Skill


class ReportSkill(Skill):
    name = SkillName.report
    next_stage = WorkflowStage.archived

    def execute(self, request: WorkflowRequest) -> dict:
        evaluation = dict(request.payload.get("evaluation") or {})
        return {
            "report": {
                "training_id": request.training_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": evaluation.get("ai_review", {}).get("summary", ""),
                "dimensions": evaluation.get("ai_review", {}).get("dimensions", []),
                "deductions": evaluation.get("ai_review", {}).get("deductions", []),
                "suggestions": evaluation.get("ai_review", {}).get("suggestions", []),
                "rule_results": evaluation.get("rule_results", []),
            }
        }
