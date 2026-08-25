from collections import defaultdict
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user
from services.agent_training_service import is_current_evaluation_report
from services.text_repair import repair_payload, repair_text
from services.training_runtime_service import load_runtime_state
from datetime import datetime

router = APIRouter(prefix="/student", tags=["Student"])


def format_utc_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    if getattr(value, "tzinfo", None):
        return value.isoformat()
    return f"{value.isoformat()}+00:00"


def build_message_activity_subquery(db: Session):
    return (
        db.query(
            models.Message.session_id.label("session_id"),
            func.sum(case((models.Message.role == "user", 1), else_=0)).label("user_message_count"),
            func.sum(case((models.Message.role.in_(("assistant", "ai")), 1), else_=0)).label("assistant_message_count"),
            func.count(models.Message.id).label("message_count"),
        )
        .group_by(models.Message.session_id)
        .subquery()
    )


def get_case_title(case_title: Optional[str]) -> str:
    title = repair_text(case_title) if case_title else ""
    return title or "未知案件"


def safe_json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return repair_payload(value)
    try:
        return repair_payload(json.loads(value))
    except Exception:
        return default


def _scene_estimated_minutes(scene: models.Scene) -> int | None:
    value = getattr(scene, "estimated_minutes", None)
    if value is None:
        return None
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None
    return minutes if minutes > 0 else None


def _normalize_difficulty_label(value: str | None) -> str:
    text_value = repair_text(value) if value else ""
    text_value = str(text_value or "").strip().lower()
    if any(token in text_value for token in ("低", "简", "easy", "low")):
        return "低"
    if any(token in text_value for token in ("高", "困", "hard", "high")):
        return "高"
    return "中"


def _difficulty_rank(value: str | None) -> int:
    return {"低": 1, "中": 2, "高": 3}.get(_normalize_difficulty_label(value), 2)


def _format_minutes_summary(minutes: list[int]) -> str | None:
    values = sorted({item for item in minutes if item > 0})
    if not values:
        return None
    if len(values) == 1:
        return f"{values[0]} 分钟"
    return f"{values[0]}-{values[-1]} 分钟"


def _stage_core_items(raw_stages) -> list[str]:
    stages = safe_json_loads(raw_stages, [])
    if not isinstance(stages, list):
        return []
    items: list[str] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        text_value = (
            stage.get("stage_name")
            or stage.get("name")
            or stage.get("title")
            or stage.get("stage_goal")
            or stage.get("goal")
        )
        text_value = repair_text(str(text_value or "")).strip()
        if text_value and text_value not in items:
            items.append(text_value)
        if len(items) >= 4:
            break
    return items


@router.get("/cases")
def get_student_cases(
    case_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Case)
    if search:
        query = query.filter(models.Case.title.contains(search))
    if case_type:
        query = query.filter(models.Case.case_type == case_type)

    cases = query.order_by(models.Case.created_at.desc()).all()
    if not cases:
        return []

    case_ids = [case.id for case in cases]
    scenes = (
        db.query(models.Scene)
        .filter(models.Scene.case_id.in_(case_ids))
        .order_by(models.Scene.case_id.asc(), models.Scene.id.asc())
        .all()
    )
    if difficulty:
        scenes = [scene for scene in scenes if scene.difficulty == difficulty]
        if not scenes:
            return []

    scenes_by_case_id: dict[int, list[models.Scene]] = defaultdict(list)
    scene_ids: list[int] = []
    for scene in scenes:
        scenes_by_case_id[scene.case_id].append(scene)
        scene_ids.append(scene.id)

    if not scene_ids:
        return []

    activity_subquery = build_message_activity_subquery(db)

    session_rows = (
        db.query(
            models.TrainingSession.id.label("session_id"),
            models.TrainingSession.scene_id.label("scene_id"),
            models.TrainingSession.status.label("status"),
            models.TrainingSession.evaluation_result.label("evaluation_result"),
            func.coalesce(activity_subquery.c.message_count, 0).label("message_count"),
            func.coalesce(activity_subquery.c.user_message_count, 0).label("user_message_count"),
            func.coalesce(activity_subquery.c.assistant_message_count, 0).label("assistant_message_count"),
        )
        .outerjoin(activity_subquery, activity_subquery.c.session_id == models.TrainingSession.id)
        .filter(
            models.TrainingSession.user_id == current_user.id,
            models.TrainingSession.scene_id.in_(scene_ids),
        )
        .all()
    )

    latest_session_id_by_scene = {
        row.scene_id: row.session_id
        for row in (
            db.query(
                models.TrainingSession.scene_id.label("scene_id"),
                func.max(models.TrainingSession.id).label("session_id"),
            )
            .filter(
                models.TrainingSession.user_id == current_user.id,
                models.TrainingSession.scene_id.in_(scene_ids),
            )
            .group_by(models.TrainingSession.scene_id)
            .all()
        )
    }

    scene_stats: dict[int, dict] = defaultdict(lambda: {"valid_train_count": 0, "empty_session_count": 0})
    latest_session_meta_by_scene: dict[int, dict] = {}

    for row in session_rows:
        user_message_count = int(row.user_message_count or 0)
        assistant_message_count = int(row.assistant_message_count or 0)
        is_empty_session = user_message_count == 0

        if is_empty_session:
            scene_stats[row.scene_id]["empty_session_count"] += 1
        else:
            scene_stats[row.scene_id]["valid_train_count"] += 1

        if latest_session_id_by_scene.get(row.scene_id) == row.session_id:
            evaluation_result = safe_json_loads(row.evaluation_result, {})
            final_score = evaluation_result.get("total_score") if isinstance(evaluation_result, dict) else None
            raw_status = str(row.status or "active").strip().lower()
            is_completed_report = (
                isinstance(evaluation_result, dict)
                and bool(evaluation_result)
                and (raw_status == "finished" or isinstance(evaluation_result.get("total_score"), (int, float)))
            )
            if is_completed_report:
                training_status = "completed"
            elif raw_status == "evaluating":
                training_status = "evaluating"
            elif raw_status == "active":
                training_status = "in_progress"
            else:
                training_status = "not_started"
            latest_session_meta_by_scene[row.scene_id] = {
                "status": row.status,
                "training_status": training_status,
                "active_session_id": row.session_id if training_status in {"in_progress", "evaluating"} else None,
                "active_session_is_empty": is_empty_session if training_status in {"in_progress", "evaluating"} else False,
                "finished_session_id": row.session_id if training_status == "completed" else None,
                "final_score": final_score if training_status == "completed" else None,
            }

    results = []
    for case in cases:
        case_scenes = scenes_by_case_id.get(case.id, [])
        if not case_scenes:
            continue
        estimated_values = [minutes for minutes in (_scene_estimated_minutes(scene) for scene in case_scenes) if minutes]
        primary_scene = max(case_scenes, key=lambda item: _difficulty_rank(item.difficulty))
        core_items = []
        for scene in case_scenes:
            for item in _stage_core_items(scene.stages):
                if item not in core_items:
                    core_items.append(item)
                if len(core_items) >= 4:
                    break
            if len(core_items) >= 4:
                break

        results.append(
            {
                "id": case.id,
                "title": get_case_title(case.title),
                "case_type": repair_text(case.case_type) or "未分类",
                "background": repair_text(case.background),
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "train_count": sum(scene_stats[scene.id]["valid_train_count"] for scene in case_scenes),
                "empty_session_count": sum(scene_stats[scene.id]["empty_session_count"] for scene in case_scenes),
                "scene_count": len(case_scenes),
                "primary_difficulty": _normalize_difficulty_label(primary_scene.difficulty),
                "estimated_minutes_summary": _format_minutes_summary(estimated_values),
                "core_items": core_items,
                "scenes": [
                    {
                        "id": scene.id,
                        "name": repair_text(scene.name),
                        "difficulty": repair_text(scene.difficulty),
                        "estimated_minutes": _scene_estimated_minutes(scene),
                        "description": repair_text(scene.description),
                        "dispatch_brief": repair_text(scene.dispatch_brief),
                        "first_impression": repair_text(scene.first_impression),
                        "stages": safe_json_loads(scene.stages, []),
                        "training_status": latest_session_meta_by_scene.get(scene.id, {}).get("training_status", "not_started"),
                        "status_label": {
                            "not_started": "未开始训练",
                            "in_progress": "继续训练",
                            "evaluating": "评估中",
                            "completed": "已完成训练",
                        }.get(latest_session_meta_by_scene.get(scene.id, {}).get("training_status", "not_started"), "未开始训练"),
                        "has_active_session": latest_session_meta_by_scene.get(scene.id, {}).get("training_status") in {"in_progress", "evaluating"},
                        "active_session_id": latest_session_meta_by_scene.get(scene.id, {}).get("active_session_id"),
                        "active_session_is_empty": latest_session_meta_by_scene.get(scene.id, {}).get("active_session_is_empty", False),
                        "finished_session_id": latest_session_meta_by_scene.get(scene.id, {}).get("finished_session_id"),
                        "final_score": latest_session_meta_by_scene.get(scene.id, {}).get("final_score"),
                    }
                    for scene in case_scenes
                ],
            }
        )

    return results


def _repair_finished_sessions_with_reports(db: Session, user_id: int) -> int:
    """Fix sessions that already have reports but remain active/evaluating."""
    stuck = (
        db.query(models.TrainingSession)
        .filter(
            models.TrainingSession.user_id == user_id,
            models.TrainingSession.status.in_(("active", "evaluating")),
            models.TrainingSession.evaluation_result.isnot(None),
        )
        .all()
    )
    repaired = 0
    now = datetime.utcnow()
    for session in stuck:
        try:
            report = json.loads(session.evaluation_result or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(report, dict) or not is_current_evaluation_report(report):
            # Still treat any persisted score-bearing or termination report as finished.
            if not (
                isinstance(report, dict)
                and (
                    isinstance(report.get("total_score"), (int, float))
                    or bool(report.get("termination_reason"))
                    or isinstance(report.get("evaluation_meta"), dict)
                )
            ):
                continue
        session.status = "finished"
        if session.training_finished_at is None:
            session.training_finished_at = now
        if session.training_started_at is None:
            session.training_started_at = session.created_at or now
        repaired += 1
    if repaired:
        db.commit()
    return repaired


@router.get("/history")
def get_student_history(
    page: int = 1,
    page_size: int = 10,
    include_empty: bool = False,
    include_assignments: bool = False,
    status: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    _repair_finished_sessions_with_reports(db, current_user.id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    offset = (page - 1) * page_size
    normalized_status = (status or "").strip().lower()
    if normalized_status and normalized_status not in {"active", "evaluating", "finished"}:
        raise HTTPException(status_code=400, detail="Unsupported history status filter")

    activity_subquery = build_message_activity_subquery(db)

    has_report_expr = models.TrainingSession.evaluation_result.isnot(None)
    is_empty_expr = (func.coalesce(activity_subquery.c.user_message_count, 0) == 0) & ~has_report_expr

    base_query = (
        db.query(
            models.TrainingSession.id.label("id"),
            models.TrainingSession.status.label("status"),
            models.TrainingSession.revealed_info.label("revealed_info"),
            models.TrainingSession.evaluation_result.label("evaluation_result"),
            models.TrainingSession.current_emotion.label("final_emotion"),
            models.TrainingSession.current_trust.label("final_trust"),
            models.TrainingSession.created_at.label("created_at"),
            models.TrainingSession.training_started_at.label("training_started_at"),
            models.TrainingSession.training_finished_at.label("training_finished_at"),
            models.Scene.name.label("scene_name"),
            models.Scene.difficulty.label("difficulty"),
            models.Case.title.label("case_title"),
            models.Case.case_type.label("case_type"),
            func.coalesce(activity_subquery.c.message_count, 0).label("message_count"),
            func.coalesce(activity_subquery.c.user_message_count, 0).label("user_message_count"),
            func.coalesce(activity_subquery.c.assistant_message_count, 0).label("assistant_message_count"),
        )
        .outerjoin(activity_subquery, activity_subquery.c.session_id == models.TrainingSession.id)
        .outerjoin(models.Scene, models.Scene.id == models.TrainingSession.scene_id)
        .outerjoin(models.Case, models.Case.id == models.Scene.case_id)
        .filter(models.TrainingSession.user_id == current_user.id)
    )
    if not include_assignments:
        assignment_session_ids = db.query(models.AssignmentSubmission.training_session_id).filter(
            models.AssignmentSubmission.training_session_id.isnot(None)
        )
        base_query = base_query.filter(~models.TrainingSession.id.in_(assignment_session_ids))

    empty_session_count = base_query.filter(is_empty_expr).count()
    visible_query = base_query if include_empty else base_query.filter(~is_empty_expr)
    visible_non_empty_query = base_query.filter(~is_empty_expr)
    active_count = visible_non_empty_query.filter(models.TrainingSession.status == "active").count()
    evaluating_count = visible_non_empty_query.filter(models.TrainingSession.status == "evaluating").count()
    finished_count = visible_non_empty_query.filter(models.TrainingSession.status == "finished").count()

    filtered_query = visible_query
    if normalized_status:
        filtered_query = filtered_query.filter(models.TrainingSession.status == normalized_status)
    total = filtered_query.count()

    rows = (
        filtered_query
        .order_by(models.TrainingSession.created_at.desc(), models.TrainingSession.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        runtime_state = load_runtime_state(row.revealed_info)
        revealed_info = runtime_state.get("revealed_info") or []
        state_snapshot = runtime_state.get("state_snapshot") if isinstance(runtime_state, dict) else {}
        revealed_info_count = len(revealed_info) if isinstance(revealed_info, list) else 0
        user_message_count = int(row.user_message_count or 0)
        assistant_message_count = int(row.assistant_message_count or 0)
        evaluation_result = safe_json_loads(row.evaluation_result, {})
        evaluation_meta = evaluation_result.get("evaluation_meta") if isinstance(evaluation_result, dict) else {}
        report_header = evaluation_meta.get("report_header") if isinstance(evaluation_meta, dict) else {}
        display_time = (
            row.training_finished_at
            if row.status == "finished" and row.training_finished_at
            else row.training_started_at or row.created_at
        )
        if row.status == "finished" and isinstance(report_header, dict) and report_header.get("finished_at"):
            display_time = report_header.get("training_finished_at") or report_header.get("finished_at") or display_time
        stage_gap_summary = evaluation_meta.get("stage_gap_summary") if isinstance(evaluation_meta, dict) else None
        stage_gap_missing = []
        if isinstance(stage_gap_summary, dict):
            stage_gap_missing = stage_gap_summary.get("missing") if isinstance(stage_gap_summary.get("missing"), list) else []
        items.append(
            {
                "id": row.id,
                "case_title": get_case_title(row.case_title),
                "case_type": repair_text(row.case_type) if row.case_type else "未分类",
                "scene_name": repair_text(row.scene_name) if row.scene_name else "未知场景",
                "difficulty": repair_text(row.difficulty) if row.difficulty else "中等",
                "status": row.status,
                "message_count": int(row.message_count or 0),
                "user_message_count": user_message_count,
                "assistant_message_count": assistant_message_count,
                "turn_count": user_message_count,
                "is_empty_session": user_message_count == 0,
                "revealed_info_count": revealed_info_count,
                "final_emotion": row.final_emotion,
                "final_trust": int((state_snapshot or {}).get("cooperation") or row.final_trust or 30),
                "final_cooperation": int((state_snapshot or {}).get("cooperation") or row.final_trust or 30),
                "final_risk": int((state_snapshot or {}).get("risk") or 50),
                "final_clarity": int((state_snapshot or {}).get("clarity") or 50),
                "total_score": evaluation_result.get("total_score") if isinstance(evaluation_result, dict) else None,
                "stage_gap_scene_type": stage_gap_summary.get("scene_type") if isinstance(stage_gap_summary, dict) else None,
                "stage_gap_missing": [repair_text(str(item)) for item in stage_gap_missing[:3]],
                "created_at": format_utc_datetime(display_time),
                "session_created_at": format_utc_datetime(row.created_at),
                "training_started_at": format_utc_datetime(row.training_started_at),
                "training_finished_at": format_utc_datetime(row.training_finished_at),
                "display_time": format_utc_datetime(display_time),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
        "include_empty": include_empty,
        "status_filter": normalized_status or "all",
        "visible_total_count": active_count + evaluating_count + finished_count,
        "active_count": active_count,
        "evaluating_count": evaluating_count,
        "finished_count": finished_count,
        "hidden_empty_count": 0 if include_empty else empty_session_count,
        "empty_session_count": empty_session_count,
    }


@router.get("/case-types")
def get_case_types(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    types = db.query(models.Case.case_type).distinct().all()
    return [repair_text(item[0]) for item in types if item[0]]
