import json
import random
import string
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from services.evaluation_service import enforce_final_score_policy, is_current_evaluation_report


ACTIVE_SUBMISSION_STATUSES = {"in_progress", "evaluating"}
FINAL_SUBMISSION_STATUSES = {"submitted", "late"}


def utcnow() -> datetime:
    return datetime.utcnow()


def serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def safe_json_loads(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def generate_invite_code(db: Session, length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(30):
        code = "".join(random.choice(alphabet) for _ in range(length))
        exists = db.query(models.TrainingClass).filter(models.TrainingClass.invite_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Failed to generate invite code")


def get_assignment_case_ids(assignment: models.TrainingAssignment) -> list[int]:
    return [item.case_id for item in sorted(assignment.cases or [], key=lambda row: row.sort_order or 0)]


def get_assignment_scene_rows(db: Session, assignment: models.TrainingAssignment) -> list[models.TrainingAssignmentScene]:
    rows = (
        db.query(models.TrainingAssignmentScene)
        .filter(models.TrainingAssignmentScene.assignment_id == assignment.id)
        .order_by(models.TrainingAssignmentScene.sort_order.asc(), models.TrainingAssignmentScene.id.asc())
        .all()
    )
    if rows:
        return rows
    return backfill_assignment_scenes_from_cases(db, assignment)


def get_assignment_scene_ids(db: Session, assignment: models.TrainingAssignment) -> list[int]:
    return [row.scene_id for row in get_assignment_scene_rows(db, assignment)]


def get_assignment_case_ids_from_scenes(db: Session, assignment: models.TrainingAssignment) -> list[int]:
    case_ids: list[int] = []
    for row in get_assignment_scene_rows(db, assignment):
        if row.case_id not in case_ids:
            case_ids.append(row.case_id)
    if case_ids:
        return case_ids
    return get_assignment_case_ids(assignment)


def backfill_assignment_scenes_from_cases(db: Session, assignment: models.TrainingAssignment) -> list[models.TrainingAssignmentScene]:
    case_ids = get_assignment_case_ids(assignment)
    if not case_ids:
        return []
    scenes = (
        db.query(models.Scene)
        .filter(models.Scene.case_id.in_(case_ids))
        .order_by(models.Scene.case_id.asc(), models.Scene.id.asc())
        .all()
    )
    case_order = {case_id: index for index, case_id in enumerate(case_ids)}
    scenes.sort(key=lambda scene: (case_order.get(scene.case_id, 999999), scene.id))
    rows: list[models.TrainingAssignmentScene] = []
    for index, scene in enumerate(scenes):
        row = models.TrainingAssignmentScene(
            assignment_id=assignment.id,
            scene_id=scene.id,
            case_id=scene.case_id,
            sort_order=index,
        )
        db.add(row)
        rows.append(row)
    if rows:
        db.flush()
    return rows


def set_assignment_scenes(
    db: Session,
    assignment: models.TrainingAssignment,
    *,
    scene_ids: list[int] | None = None,
    case_ids: list[int] | None = None,
) -> list[models.TrainingAssignmentScene]:
    normalized_scene_ids: list[int] = []
    for item in scene_ids or []:
        try:
            scene_id = int(item)
        except (TypeError, ValueError):
            continue
        if scene_id not in normalized_scene_ids:
            normalized_scene_ids.append(scene_id)

    normalized_case_ids: list[int] = []
    for item in case_ids or []:
        try:
            case_id = int(item)
        except (TypeError, ValueError):
            continue
        if case_id not in normalized_case_ids:
            normalized_case_ids.append(case_id)

    scenes: list[models.Scene] = []
    if normalized_scene_ids:
        scene_map = {
            scene.id: scene
            for scene in db.query(models.Scene).filter(models.Scene.id.in_(normalized_scene_ids)).all()
        }
        missing_scene_ids = [scene_id for scene_id in normalized_scene_ids if scene_id not in scene_map]
        if missing_scene_ids:
            raise HTTPException(status_code=400, detail=f"Scenes not found: {missing_scene_ids}")
        scenes = [scene_map[scene_id] for scene_id in normalized_scene_ids]
    elif normalized_case_ids:
        scene_rows = (
            db.query(models.Scene)
            .filter(models.Scene.case_id.in_(normalized_case_ids))
            .order_by(models.Scene.case_id.asc(), models.Scene.id.asc())
            .all()
        )
        case_order = {case_id: index for index, case_id in enumerate(normalized_case_ids)}
        scenes = sorted(scene_rows, key=lambda scene: (case_order.get(scene.case_id, 999999), scene.id))

    if not scenes:
        raise HTTPException(status_code=400, detail="Select at least one training scene")

    db.query(models.TrainingAssignmentScene).filter(
        models.TrainingAssignmentScene.assignment_id == assignment.id
    ).delete(synchronize_session=False)
    rows: list[models.TrainingAssignmentScene] = []
    for index, scene in enumerate(scenes):
        row = models.TrainingAssignmentScene(
            assignment_id=assignment.id,
            scene_id=scene.id,
            case_id=scene.case_id,
            sort_order=index,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def get_active_membership(db: Session, class_id: int, user_id: int) -> models.ClassMembership | None:
    return (
        db.query(models.ClassMembership)
        .filter(
            models.ClassMembership.class_id == class_id,
            models.ClassMembership.user_id == user_id,
            models.ClassMembership.status == "active",
        )
        .first()
    )


def require_student_membership(db: Session, class_id: int, user: models.User) -> models.ClassMembership | None:
    if user.role == "admin":
        return None
    membership = get_active_membership(db, class_id, user.id)
    if not membership:
        raise HTTPException(status_code=403, detail="You have not joined this class")
    return membership


def get_student_override(
    db: Session,
    assignment_id: int,
    user_id: int,
) -> models.AssignmentStudentOverride | None:
    return (
        db.query(models.AssignmentStudentOverride)
        .filter(
            models.AssignmentStudentOverride.assignment_id == assignment_id,
            models.AssignmentStudentOverride.user_id == user_id,
        )
        .first()
    )


def get_effective_assignment_policy(
    db: Session,
    assignment: models.TrainingAssignment,
    user_id: int,
) -> dict[str, Any]:
    override = get_student_override(db, assignment.id, user_id)
    due_at = override.due_at if override and override.due_at else assignment.due_at
    allow_late = (
        bool(override.allow_late)
        if override and override.allow_late is not None
        else bool(assignment.allow_late)
    )
    return {
        "due_at": due_at,
        "allow_late": allow_late,
        "override": override,
        "is_overdue": bool(due_at and utcnow() > due_at),
    }


def has_active_assignment_submission(
    db: Session,
    assignment_id: int,
    user_id: int,
    scene_id: int,
) -> bool:
    return (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.assignment_id == assignment_id,
            models.AssignmentSubmission.user_id == user_id,
            models.AssignmentSubmission.scene_id == scene_id,
            models.AssignmentSubmission.status.in_(ACTIVE_SUBMISSION_STATUSES),
        )
        .first()
        is not None
    )


def validate_assignment_training_access(
    db: Session,
    assignment_id: int,
    user: models.User,
    scene_id: int,
) -> tuple[models.TrainingAssignment, models.Scene]:
    assignment = (
        db.query(models.TrainingAssignment)
        .filter(models.TrainingAssignment.id == assignment_id)
        .first()
    )
    if not assignment or assignment.status != "published":
        raise HTTPException(status_code=404, detail="Assignment not found")

    require_student_membership(db, assignment.class_id, user)

    scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Training scene not found")

    assignment_scene_ids = set(get_assignment_scene_ids(db, assignment))
    if scene.id not in assignment_scene_ids:
        raise HTTPException(status_code=400, detail="This scene does not belong to the assignment")

    policy = get_effective_assignment_policy(db, assignment, user.id)
    if (
        policy["is_overdue"]
        and not policy["allow_late"]
        and not has_active_assignment_submission(db, assignment.id, user.id, scene.id)
    ):
        raise HTTPException(status_code=403, detail="Assignment is closed. Ask the administrator to enable late submission.")

    return assignment, scene


def get_session_assignment_context(
    db: Session,
    session_id: int,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    query = (
        db.query(models.AssignmentSubmission, models.TrainingAssignment, models.TrainingClass)
        .join(models.TrainingAssignment, models.TrainingAssignment.id == models.AssignmentSubmission.assignment_id)
        .join(models.TrainingClass, models.TrainingClass.id == models.TrainingAssignment.class_id)
        .filter(models.AssignmentSubmission.training_session_id == session_id)
        .order_by(models.AssignmentSubmission.updated_at.desc(), models.AssignmentSubmission.id.desc())
    )
    if user_id is not None:
        query = query.filter(models.AssignmentSubmission.user_id == user_id)
    row = query.first()
    if not row:
        return None
    submission, assignment, classroom = row
    policy = get_effective_assignment_policy(db, assignment, submission.user_id)
    return {
        "type": "assignment",
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "class_id": classroom.id,
        "class_name": classroom.name,
        "due_at": serialize_datetime(policy["due_at"]),
        "allow_late": policy["allow_late"],
        "is_overdue": policy["is_overdue"],
        "submission_id": submission.id,
        "submission_status": submission.status,
        "return_path": "/student/classes",
    }


def extract_total_score(evaluation_result: Any) -> int | None:
    payload = safe_json_loads(evaluation_result, {})
    if not isinstance(payload, dict):
        return None
    score = payload.get("total_score")
    if not isinstance(score, (int, float)):
        return None
    return int(round(float(score)))


def resolve_submission_status(
    db: Session,
    assignment: models.TrainingAssignment,
    user_id: int,
    session: models.TrainingSession,
    submitted_at: datetime | None = None,
) -> str:
    if session.status == "finished":
        policy = get_effective_assignment_policy(db, assignment, user_id)
        due_at = policy["due_at"]
        effective_submitted_at = submitted_at or utcnow()
        return "late" if due_at and effective_submitted_at > due_at else "submitted"
    if session.status == "evaluating":
        return "evaluating"
    return "in_progress"


def link_session_to_assignment(
    db: Session,
    assignment_id: int,
    user: models.User,
    session: models.TrainingSession,
    scene: models.Scene | None = None,
) -> models.AssignmentSubmission:
    assignment = (
        db.query(models.TrainingAssignment)
        .filter(models.TrainingAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    scene = scene or db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Training scene not found")

    submission = (
        db.query(models.AssignmentSubmission)
        .filter(models.AssignmentSubmission.training_session_id == session.id)
        .first()
    )
    if not submission:
        submission = (
            db.query(models.AssignmentSubmission)
            .filter(
                models.AssignmentSubmission.assignment_id == assignment.id,
                models.AssignmentSubmission.user_id == user.id,
                models.AssignmentSubmission.scene_id == scene.id,
                models.AssignmentSubmission.status.in_(ACTIVE_SUBMISSION_STATUSES),
            )
            .order_by(models.AssignmentSubmission.updated_at.desc(), models.AssignmentSubmission.id.desc())
            .first()
        )

    if not submission:
        submission = models.AssignmentSubmission(
            assignment_id=assignment.id,
            user_id=user.id,
            case_id=scene.case_id,
            scene_id=scene.id,
            training_session_id=session.id,
        )
        db.add(submission)

    submission.assignment_id = assignment.id
    submission.user_id = user.id
    submission.case_id = scene.case_id
    submission.scene_id = scene.id
    submission.training_session_id = session.id
    submitted_at = submission.submitted_at
    if session.status == "finished" and submitted_at is None:
        submitted_at = utcnow()
    submission.status = resolve_submission_status(db, assignment, user.id, session, submitted_at=submitted_at)
    submission.updated_at = utcnow()
    if session.evaluation_result:
        session_report = safe_json_loads(session.evaluation_result, {})
        if is_current_evaluation_report(session_report):
            session.evaluation_result = json.dumps(enforce_final_score_policy(session_report, policy_source="assignment_link"), ensure_ascii=False)
            submission.evaluation_result = session.evaluation_result
            submission.score = extract_total_score(session.evaluation_result)
    if submission.status in FINAL_SUBMISSION_STATUSES and not submission.submitted_at:
        submission.submitted_at = submitted_at or utcnow()

    return submission


def sync_assignment_submission_for_session(
    db: Session,
    session_id: int,
    user_id: int | None = None,
    report: dict | None = None,
) -> list[int]:
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        return []
    query = db.query(models.AssignmentSubmission).filter(
        models.AssignmentSubmission.training_session_id == session_id
    )
    if user_id is not None:
        query = query.filter(models.AssignmentSubmission.user_id == user_id)
    submissions = query.all()
    if not submissions:
        return []

    if isinstance(report, dict):
        report = enforce_final_score_policy(report, policy_source="assignment_sync")
        report_json = json.dumps(report, ensure_ascii=False)
    else:
        session_report = safe_json_loads(session.evaluation_result, {})
        report_json = session.evaluation_result if is_current_evaluation_report(session_report) else None
    updated_ids: list[int] = []
    for submission in submissions:
        assignment = (
            db.query(models.TrainingAssignment)
            .filter(models.TrainingAssignment.id == submission.assignment_id)
            .first()
        )
        if not assignment:
            continue
        submitted_at = submission.submitted_at
        if session.status == "finished" and submitted_at is None:
            submitted_at = utcnow()
        submission.status = resolve_submission_status(
            db,
            assignment,
            submission.user_id,
            session,
            submitted_at=submitted_at,
        )
        submission.updated_at = utcnow()
        if report_json:
            submission.evaluation_result = report_json
            submission.score = extract_total_score(report_json)
        if submission.status in FINAL_SUBMISSION_STATUSES and not submission.submitted_at:
            submission.submitted_at = submitted_at or utcnow()
        updated_ids.append(submission.id)

    if updated_ids:
        db.commit()
    return updated_ids
