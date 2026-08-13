from __future__ import annotations

import uuid

from fastapi import FastAPI, Header, HTTPException

from ai_workflow_service.agents import TrainingOrchestratorAgent
from ai_workflow_service.config import settings
from ai_workflow_service.contracts import WorkflowRequest, WorkflowResponse
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.tinytroupe_adapter import TinyTroupeAdapter
from ai_workflow_service.skills import CaseParseSkill, EvaluationSkill, PersonaBuildSkill, ReportSkill, RoleSimulationSkill, SceneBuildSkill
from ai_workflow_service.tools.audit_log import AuditLogTool
from ai_workflow_service.tools.state_store import JsonStateStore


llm = DeepSeekAdapter(settings)
simulation = TinyTroupeAdapter()
state_store = JsonStateStore(settings.data_dir / "workflows")
orchestrator = TrainingOrchestratorAgent(
    skills=[
        CaseParseSkill(llm),
        PersonaBuildSkill(),
        SceneBuildSkill(),
        RoleSimulationSkill(llm, simulation),
        EvaluationSkill(llm),
        ReportSkill(),
    ],
    state_store=state_store,
    audit_log=AuditLogTool(settings.data_dir / "audit.jsonl"),
)

app = FastAPI(title="AI Police Workflow Service", version="1.0.0")


def _authorize(token: str | None) -> None:
    if settings.internal_token and token != settings.internal_token:
        raise HTTPException(status_code=401, detail="内部服务认证失败")


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "service": settings.service_name,
        "components": {"deepseek_configured": llm.configured, "tinytroupe_available": simulation.available},
    }


@app.post("/v1/workflows/execute", response_model=WorkflowResponse)
def execute_workflow(
    request: WorkflowRequest,
    x_trace_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
):
    _authorize(x_internal_token)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="缺少 Idempotency-Key")
    trace_id = x_trace_id or uuid.uuid4().hex
    try:
        return orchestrator.execute(request, trace_id, idempotency_key)
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc


@app.get("/v1/workflows/{workflow_id}")
def get_workflow(workflow_id: str, x_internal_token: str | None = Header(default=None)):
    _authorize(x_internal_token)
    value = state_store.get(workflow_id)
    if not value:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return value["response"]
