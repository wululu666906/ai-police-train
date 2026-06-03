from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

import database
import models
from routers.auth import require_admin_user
from services.training_runtime_service import load_runtime_state
from services.state_contract_postcheck import validate_response_against_contract
from services.state_influence_config import export_tables_for_admin, save_overrides
from services.state_influence_metrics import (
    build_session_metrics,
    run_regression_suite,
    simulate_state_influence,
)

router = APIRouter(prefix="/admin/state-influence", tags=["StateInfluenceAdmin"])


@router.get("/tables")
def get_state_influence_tables(_user=Depends(require_admin_user)) -> dict[str, Any]:
    return export_tables_for_admin()


@router.put("/tables")
def update_state_influence_tables(
    payload: dict[str, Any] = Body(...),
    _user=Depends(require_admin_user),
) -> dict[str, Any]:
    overrides = payload.get("overrides") if isinstance(payload, dict) else payload
    if not isinstance(overrides, dict):
        overrides = {}
    tables = save_overrides(overrides)
    return {"ok": True, "tables": tables, "message": "触发表已更新（覆盖项写入 overrides 文件）"}


@router.post("/simulate")
def simulate_state_influence_tables(
    payload: dict[str, Any] = Body(...),
    _user=Depends(require_admin_user),
) -> dict[str, Any]:
    scores = payload.get("scores") if isinstance(payload, dict) else {}
    user_message = str(payload.get("user_message") or "").strip()
    actions = payload.get("recognized_actions") if isinstance(payload.get("recognized_actions"), list) else []
    return simulate_state_influence(scores, user_message=user_message, recognized_actions=actions)


@router.get("/metrics/regression")
def get_state_influence_regression_metrics(_user=Depends(require_admin_user)) -> dict[str, Any]:
    return run_regression_suite()


@router.post("/metrics/validate-turn")
def validate_turn_against_contract(
    payload: dict[str, Any] = Body(...),
    _user=Depends(require_admin_user),
) -> dict[str, Any]:
    contract = payload.get("contract") if isinstance(payload, dict) else {}
    text = str(payload.get("text") or "").strip()
    if not isinstance(contract, dict):
        contract = {}
    validation = validate_response_against_contract(text, contract)
    return {"validation": validation, "text": text}


@router.get("/metrics/session/{session_id}")
def get_session_state_influence_metrics(
    session_id: int,
    db: Session = Depends(database.get_db),
    _user=Depends(require_admin_user),
) -> dict[str, Any]:
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="训练会话不存在")
    runtime_state = load_runtime_state(session.revealed_info)
    return {
        "session_id": session_id,
        "status": session.status,
        "metrics": build_session_metrics(runtime_state),
        "turn_log": runtime_state.get("state_influence_turn_log") or [],
    }
