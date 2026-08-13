from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from ai_workflow_service.contracts import SkillName, WorkflowError, WorkflowRequest, WorkflowResponse, WorkflowStage
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.skills.base import Skill
from ai_workflow_service.tools.audit_log import AuditLogTool
from ai_workflow_service.tools.state_store import JsonStateStore


STAGE_SKILLS: dict[WorkflowStage, SkillName] = {
    WorkflowStage.case_uploaded: SkillName.case_parse,
    WorkflowStage.case_parsed: SkillName.persona_build,
    WorkflowStage.personas_ready: SkillName.scene_build,
    WorkflowStage.training: SkillName.role_simulation,
    WorkflowStage.completed: SkillName.evaluation,
    WorkflowStage.evaluated: SkillName.report,
}


class TrainingOrchestratorAgent:
    def __init__(self, skills: list[Skill], state_store: JsonStateStore, audit_log: AuditLogTool):
        self.skills = {skill.name: skill for skill in skills}
        self.state_store = state_store
        self.audit_log = audit_log

    def execute(self, request: WorkflowRequest, trace_id: str, idempotency_key: str) -> WorkflowResponse:
        existing = self.state_store.get(request.workflow_id)
        if existing and existing.get("idempotency_key") == idempotency_key and existing.get("response"):
            return WorkflowResponse.model_validate(existing["response"])

        skill_name = request.skill or STAGE_SKILLS.get(request.stage)
        if not skill_name or skill_name not in self.skills:
            raise WorkflowServiceError("NO_SKILL_FOR_STAGE", f"阶段 {request.stage.value} 没有可执行 Skill")

        started = time.perf_counter()
        skill = self.skills[skill_name]
        try:
            result = skill.execute(request)
            response = WorkflowResponse(
                workflow_id=request.workflow_id,
                trace_id=trace_id,
                stage=request.stage,
                next_stage=skill.next_stage,
                skill=skill_name,
                status="succeeded",
                result=result,
                transition_proposal={"from": request.stage.value, "to": skill.next_stage.value},
            )
        except WorkflowServiceError as exc:
            response = WorkflowResponse(
                workflow_id=request.workflow_id,
                trace_id=trace_id,
                stage=request.stage,
                next_stage=WorkflowStage.failed,
                skill=skill_name,
                status="failed",
                error=WorkflowError(code=exc.code, message=exc.message, retryable=exc.retryable),
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        record: dict[str, Any] = {
            "workflow_id": request.workflow_id,
            "trace_id": trace_id,
            "idempotency_key": idempotency_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "response": response.model_dump(mode="json"),
        }
        self.state_store.put(request.workflow_id, record)
        self.audit_log.write({
            "trace_id": trace_id,
            "workflow_id": request.workflow_id,
            "skill": skill_name.value,
            "status": response.status,
            "duration_ms": duration_ms,
            "error_code": response.error.code if response.error else None,
        })
        return response
