from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user
from services.multimodal_service import build_scene_performance_report, get_engine_status, record_frame


router = APIRouter(prefix="/multimodal", tags=["Multimodal"])


class FrameAnalysisRequest(BaseModel):
    frame: str
    client_signals: dict[str, Any] | None = None


@router.post("/session/{session_id}/frame")
def analyze_session_frame(
    session_id: int,
    payload: FrameAnalysisRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    return record_frame(
        db,
        session_id=session_id,
        user=current_user,
        frame_data_url=payload.frame,
        client_signals=payload.client_signals,
    )


@router.get("/engine")
def get_multimodal_engine_status(_: models.User = Depends(get_current_user)) -> dict[str, Any]:
    return get_engine_status()


@router.get("/session/{session_id}/summary")
def get_session_summary(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if current_user.role != "admin":
        query = query.filter(models.TrainingSession.user_id == current_user.id)
    if not query.first():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Training session not found")
    return build_scene_performance_report(db, session_id)
