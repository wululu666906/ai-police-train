from __future__ import annotations

import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from ai_workflow_service.agents import TrainingOrchestratorAgent
from ai_workflow_service.agents.case_import_harness import CaseImportHarnessAgent
from ai_workflow_service.config import settings
from ai_workflow_service.contracts import WORKFLOW_CONTRACT_VERSION, WorkflowRequest, WorkflowResponse
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.tinytroupe_adapter import TinyTroupeAdapter
from ai_workflow_service.skills import EvaluationSkill, ReportSkill, RoleSimulationSkill
from ai_workflow_service.tools.audit_log import AuditLogTool
from ai_workflow_service.tools.state_store import JsonStateStore


llm = DeepSeekAdapter(settings)
audit_log = AuditLogTool(settings.data_dir / "audit.jsonl")
simulation = TinyTroupeAdapter(settings, llm, audit_log)
state_store = JsonStateStore(settings.data_dir / "workflows")
orchestrator = TrainingOrchestratorAgent(
    skills=[
        RoleSimulationSkill(llm, simulation),
        EvaluationSkill(llm),
        ReportSkill(),
    ],
    state_store=state_store,
    audit_log=audit_log,
)
case_import_harness = CaseImportHarnessAgent(llm, audit_log)

app = FastAPI(title="AI Police Workflow Service", version="1.0.0")


def _authorize(token: str | None) -> None:
    if settings.internal_token and token != settings.internal_token:
        raise HTTPException(status_code=401, detail="内部服务认证失败")


@app.get("/healthz")
def healthz():
    components = {
        "deepseek_configured": llm.configured,
        "tinytroupe_available": simulation.available,
        "tinytroupe_mode": settings.tinytroupe_mode,
        "tinytroupe_model_configured": simulation.model_configured,
        "tinytroupe_state_store_writable": simulation.state_store_writable,
        "tinytroupe_max_actors": settings.tinytroupe_max_actors,
    }
    ready = all((
        components["deepseek_configured"],
        components["tinytroupe_available"],
        components["tinytroupe_model_configured"],
        components["tinytroupe_state_store_writable"],
    ))
    return JSONResponse(status_code=200 if ready else 503, content={
        "status": "ok" if ready else "unavailable",
        "service": settings.service_name,
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "components": components,
    })


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


@app.post("/v1/case-imports/execute")
def execute_case_import(
    payload: dict,
    x_trace_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
):
    _authorize(x_internal_token)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")
    workflow_id = str(payload.get("workflow_id") or "").strip()
    source_text = str(payload.get("source_text") or "").strip()
    case_id = str(payload.get("case_id") or workflow_id).strip()
    if not workflow_id or not source_text:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CASE_IMPORT", "message": "workflow_id and source_text are required"})
    existing = state_store.get(workflow_id)
    if existing and existing.get("idempotency_key") == idempotency_key and existing.get("response"):
        return existing["response"]
    trace_id = x_trace_id or uuid.uuid4().hex
    try:
        result = case_import_harness.execute(
            workflow_id=workflow_id,
            case_id=case_id,
            source_text=source_text,
            trace_id=trace_id,
        )
        response = {"workflow_id": workflow_id, "trace_id": trace_id, "status": "succeeded", "result": result}
    except WorkflowServiceError as exc:
        response = {
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "status": "failed",
            "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        }
    except Exception as exc:
        response = {
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "status": "failed",
            "error": {"code": "CASE_IMPORT_FAILED", "message": f"案件导入失败: {exc}", "retryable": False},
        }
    state_store.put(workflow_id, {"workflow_id": workflow_id, "trace_id": trace_id, "idempotency_key": idempotency_key, "response": response})
    return response


@app.get("/v1/workflows/{workflow_id}")
def get_workflow(workflow_id: str, x_internal_token: str | None = Header(default=None)):
    _authorize(x_internal_token)
    value = state_store.get(workflow_id)
    if not value:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return value["response"]
