import json
import random
import string
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models


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

    if scene.case_id not in set(get_assignment_case_ids(assignment)):
        raise HTTPException(status_code=400, detail="This scene does not belong to the assignment")

    policy = get_effective_assignment_policy(db, assignment, user.id)
    if (
        policy["is_overdue"]
        and not policy["allow_late"]
        and not has_active_assignment_submission(db, assignment.id, user.id, scene.id)
    ):
        raise HTTPException(status_code=403, detail="Assignment is closed. Ask the administrator to enable late submission.")

    return assignment, scene


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

    report_json = json.dumps(report, ensure_ascii=False) if isinstance(report, dict) else session.evaluation_result
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
