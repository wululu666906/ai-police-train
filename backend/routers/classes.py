from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user, require_admin_user
from services.classroom_service import (
    FINAL_SUBMISSION_STATUSES,
    generate_invite_code,
    get_effective_assignment_policy,
    get_assignment_case_ids,
    get_assignment_case_ids_from_scenes,
    get_assignment_scene_ids,
    get_assignment_scene_rows,
    require_student_membership,
    safe_json_loads,
    serialize_datetime,
    set_assignment_scenes,
)
from services.text_repair import repair_text

router = APIRouter(prefix="/classes", tags=["Classes"])


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def ensure_classroom(db: Session, class_id: int) -> models.TrainingClass:
    classroom = db.query(models.TrainingClass).filter(models.TrainingClass.id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")
    return classroom


def ensure_assignment(db: Session, class_id: int, assignment_id: int) -> models.TrainingAssignment:
    assignment = (
        db.query(models.TrainingAssignment)
        .filter(
            models.TrainingAssignment.id == assignment_id,
            models.TrainingAssignment.class_id == class_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def case_title(case: models.Case | None) -> str:
    return repair_text(getattr(case, "title", None)) if case else "未知案件"


def scene_name(scene: models.Scene | None) -> str:
    return repair_text(getattr(scene, "name", None)) if scene else "训练场景"


def serialize_case_brief(case: models.Case | None) -> dict:
    return {
        "id": getattr(case, "id", None),
        "title": case_title(case),
        "case_type": repair_text(getattr(case, "case_type", None)) if case else "",
        "background": repair_text(getattr(case, "background", None)) if case else "",
    }


def serialize_scene_brief(scene: models.Scene | None, case: models.Case | None = None) -> dict:
    return {
        "id": getattr(scene, "id", None),
        "case_id": getattr(scene, "case_id", getattr(case, "id", None)),
        "case_title": case_title(case),
        "name": scene_name(scene),
        "difficulty": repair_text(getattr(scene, "difficulty", None)) if scene else "",
        "description": repair_text(getattr(scene, "description", None)) if scene else "",
    }


def serialize_submission(submission: models.AssignmentSubmission | None, *, include_evaluation: bool = False) -> dict | None:
    if not submission:
        return None
    payload = {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "user_id": submission.user_id,
        "case_id": submission.case_id,
        "scene_id": submission.scene_id,
        "training_session_id": submission.training_session_id,
        "status": submission.status,
        "score": submission.score,
        "submitted_at": serialize_datetime(submission.submitted_at),
        "updated_at": serialize_datetime(submission.updated_at),
    }
    if include_evaluation:
        payload["evaluation_result"] = safe_json_loads(submission.evaluation_result, None)
    return payload


def serialize_announcement(item: models.ClassAnnouncement) -> dict:
    return {
        "id": item.id,
        "class_id": item.class_id,
        "title": item.title,
        "content": item.content or "",
        "category": item.category or "notice",
        "created_at": serialize_datetime(item.created_at),
    }


def serialize_assignment_base(db: Session, assignment: models.TrainingAssignment, *, include_cases: bool = True) -> dict:
    case_ids = get_assignment_case_ids_from_scenes(db, assignment)
    scene_ids = get_assignment_scene_ids(db, assignment)
    cases: list[dict] = []
    scenes: list[dict] = []
    if include_cases and case_ids:
        case_map = {
            item.id: item
            for item in db.query(models.Case).filter(models.Case.id.in_(case_ids)).all()
        }
        cases = [serialize_case_brief(case_map.get(case_id)) for case_id in case_ids]
    if include_cases and scene_ids:
        scene_rows = db.query(models.Scene).filter(models.Scene.id.in_(scene_ids)).all()
        scene_map = {item.id: item for item in scene_rows}
        case_map = {
            item.id: item
            for item in db.query(models.Case).filter(models.Case.id.in_({scene.case_id for scene in scene_rows})).all()
        } if scene_rows else {}
        scenes = [serialize_scene_brief(scene_map.get(scene_id), case_map.get(getattr(scene_map.get(scene_id), "case_id", None))) for scene_id in scene_ids]
    return {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "instructions": assignment.instructions or "",
        "scoring_rule": assignment.scoring_rule or "",
        "status": assignment.status,
        "allow_late": bool(assignment.allow_late),
        "published_at": serialize_datetime(assignment.published_at),
        "due_at": serialize_datetime(assignment.due_at),
        "created_at": serialize_datetime(assignment.created_at),
        "case_ids": case_ids,
        "scene_ids": scene_ids,
        "cases": cases,
        "scenes": scenes,
    }


def serialize_classroom(db: Session, classroom: models.TrainingClass) -> dict:
    student_count = (
        db.query(models.ClassMembership)
        .filter(
            models.ClassMembership.class_id == classroom.id,
            models.ClassMembership.status == "active",
            models.ClassMembership.role == "student",
        )
        .count()
    )
    assignment_count = (
        db.query(models.TrainingAssignment)
        .filter(models.TrainingAssignment.class_id == classroom.id)
        .count()
    )
    announcement_count = (
        db.query(models.ClassAnnouncement)
        .filter(models.ClassAnnouncement.class_id == classroom.id)
        .count()
    )
    return {
        "id": classroom.id,
        "name": classroom.name,
        "description": classroom.description or "",
        "invite_code": classroom.invite_code,
        "muted": bool(classroom.muted),
        "created_at": serialize_datetime(classroom.created_at),
        "student_count": student_count,
        "assignment_count": assignment_count,
        "announcement_count": announcement_count,
    }


def latest_submission_for_case(
    db: Session,
    assignment_id: int,
    user_id: int,
    case_id: int,
) -> models.AssignmentSubmission | None:
    final_submission = (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.assignment_id == assignment_id,
            models.AssignmentSubmission.user_id == user_id,
            models.AssignmentSubmission.case_id == case_id,
            models.AssignmentSubmission.status.in_(FINAL_SUBMISSION_STATUSES),
        )
        .order_by(
            models.AssignmentSubmission.submitted_at.desc(),
            models.AssignmentSubmission.updated_at.desc(),
            models.AssignmentSubmission.id.desc(),
        )
        .first()
    )
    if final_submission:
        return final_submission
    return (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.assignment_id == assignment_id,
            models.AssignmentSubmission.user_id == user_id,
            models.AssignmentSubmission.case_id == case_id,
        )
        .order_by(models.AssignmentSubmission.updated_at.desc(), models.AssignmentSubmission.id.desc())
        .first()
    )


def latest_submission_for_scene(
    db: Session,
    assignment_id: int,
    user_id: int,
    scene_id: int,
) -> models.AssignmentSubmission | None:
    return (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.assignment_id == assignment_id,
            models.AssignmentSubmission.user_id == user_id,
            models.AssignmentSubmission.scene_id == scene_id,
        )
        .order_by(
            models.AssignmentSubmission.submitted_at.desc(),
            models.AssignmentSubmission.updated_at.desc(),
            models.AssignmentSubmission.id.desc(),
        )
        .first()
    )


def scene_status_for_student(
    db: Session,
    assignment: models.TrainingAssignment,
    user_id: int,
    scene_id: int,
) -> dict:
    submission = latest_submission_for_scene(db, assignment.id, user_id, scene_id)
    policy = get_effective_assignment_policy(db, assignment, user_id)
    if submission and submission.status in FINAL_SUBMISSION_STATUSES:
        status = "late" if submission.status == "late" else "completed"
    elif submission and submission.status in {"in_progress", "evaluating"}:
        status = submission.status
    elif policy["is_overdue"] and not policy["allow_late"]:
        status = "expired"
    else:
        status = "pending"
    return {
        "scene_id": scene_id,
        "status": status,
        "submission": serialize_submission(submission),
    }


def case_status_for_student(
    db: Session,
    assignment: models.TrainingAssignment,
    user_id: int,
    case_id: int,
) -> dict:
    scene_ids = [
        row.scene_id
        for row in get_assignment_scene_rows(db, assignment)
        if row.case_id == case_id
    ]
    scene_statuses = [scene_status_for_student(db, assignment, user_id, scene_id) for scene_id in scene_ids]
    completed = [item for item in scene_statuses if item["status"] in {"completed", "late"}]
    active = [item for item in scene_statuses if item["status"] in {"in_progress", "evaluating"}]
    policy = get_effective_assignment_policy(db, assignment, user_id)
    if scene_ids and len(completed) == len(scene_ids):
        status = "late" if any(item["status"] == "late" for item in completed) else "completed"
    elif active:
        status = "in_progress"
    elif policy["is_overdue"] and not policy["allow_late"]:
        status = "expired"
    else:
        status = "pending"
    return {
        "case_id": case_id,
        "status": status,
        "completed_count": len(completed),
        "required_count": len(scene_ids),
        "scene_statuses": scene_statuses,
        "submission": completed[-1]["submission"] if completed else (active[-1]["submission"] if active else None),
    }


def assignment_status_for_student(
    db: Session,
    assignment: models.TrainingAssignment,
    user_id: int,
) -> dict:
    scene_ids = get_assignment_scene_ids(db, assignment)
    policy = get_effective_assignment_policy(db, assignment, user_id)
    scene_statuses = [scene_status_for_student(db, assignment, user_id, scene_id) for scene_id in scene_ids]
    case_statuses = [
        case_status_for_student(db, assignment, user_id, case_id)
        for case_id in get_assignment_case_ids_from_scenes(db, assignment)
    ]
    completed = [item for item in scene_statuses if item["status"] in {"completed", "late"}]
    active = [item for item in scene_statuses if item["status"] in {"in_progress", "evaluating"}]
    if scene_ids and len(completed) == len(scene_ids):
        status = "late" if any(item["status"] == "late" for item in completed) else "completed"
    elif active:
        status = "in_progress"
    elif policy["is_overdue"] and not policy["allow_late"]:
        status = "unsubmitted"
    else:
        status = "pending"
    return {
        "status": status,
        "completed_count": len(completed),
        "required_count": len(scene_ids),
        "case_statuses": case_statuses,
        "scene_statuses": scene_statuses,
        "effective_due_at": serialize_datetime(policy["due_at"]),
        "allow_late": policy["allow_late"],
        "is_overdue": policy["is_overdue"],
    }


@router.post("/join")
def join_class(
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_code = str(payload.get("invite_code") or payload.get("code") or "").strip().upper()
    if not invite_code:
        raise HTTPException(status_code=400, detail="Invite code is required")

    classroom = db.query(models.TrainingClass).filter(models.TrainingClass.invite_code == invite_code).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class invite code not found")

    membership = (
        db.query(models.ClassMembership)
        .filter(
            models.ClassMembership.class_id == classroom.id,
            models.ClassMembership.user_id == current_user.id,
        )
        .first()
    )
    if membership:
        membership.status = "active"
        membership.role = membership.role or "student"
    else:
        membership = models.ClassMembership(
            class_id=classroom.id,
            user_id=current_user.id,
            role="student",
            status="active",
        )
        db.add(membership)
    db.commit()
    return {"message": "Joined class", "classroom": serialize_classroom(db, classroom)}


@router.get("/student/my")
def list_my_classes(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.TrainingClass)
        .join(models.ClassMembership, models.ClassMembership.class_id == models.TrainingClass.id)
        .filter(
            models.ClassMembership.user_id == current_user.id,
            models.ClassMembership.status == "active",
        )
        .order_by(models.ClassMembership.joined_at.desc())
        .all()
    )
    return [serialize_classroom(db, item) for item in rows]


@router.get("/student/announcements")
def list_student_announcements(
    class_id: int | None = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    class_ids = [
        row.class_id
        for row in db.query(models.ClassMembership.class_id)
        .filter(
            models.ClassMembership.user_id == current_user.id,
            models.ClassMembership.status == "active",
        )
        .all()
    ]
    if class_id:
        if class_id not in class_ids and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You have not joined this class")
        class_ids = [class_id]
    if not class_ids:
        return []
    rows = (
        db.query(models.ClassAnnouncement)
        .filter(models.ClassAnnouncement.class_id.in_(class_ids))
        .order_by(models.ClassAnnouncement.created_at.desc())
        .limit(50)
        .all()
    )
    return [serialize_announcement(row) for row in rows]


@router.get("/student/assignments")
def list_student_assignments(
    class_id: int | None = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    class_ids = [
        row.class_id
        for row in db.query(models.ClassMembership.class_id)
        .filter(
            models.ClassMembership.user_id == current_user.id,
            models.ClassMembership.status == "active",
        )
        .all()
    ]
    if class_id:
        if class_id not in class_ids and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You have not joined this class")
        class_ids = [class_id]
    if not class_ids:
        return []

    class_map = {
        item.id: item
        for item in db.query(models.TrainingClass).filter(models.TrainingClass.id.in_(class_ids)).all()
    }
    rows = (
        db.query(models.TrainingAssignment)
        .filter(
            models.TrainingAssignment.class_id.in_(class_ids),
            models.TrainingAssignment.status == "published",
        )
        .order_by(models.TrainingAssignment.due_at.asc().nullslast(), models.TrainingAssignment.created_at.desc())
        .all()
    )
    results = []
    for assignment in rows:
        summary = assignment_status_for_student(db, assignment, current_user.id)
        results.append(
            {
                **serialize_assignment_base(db, assignment),
                **summary,
                "class_name": class_map.get(assignment.class_id).name if class_map.get(assignment.class_id) else "",
            }
        )
    return results


@router.get("/student/assignments/{assignment_id}")
def get_student_assignment_detail(
    assignment_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    assignment = db.query(models.TrainingAssignment).filter(models.TrainingAssignment.id == assignment_id).first()
    if not assignment or assignment.status != "published":
        raise HTTPException(status_code=404, detail="Assignment not found")
    require_student_membership(db, assignment.class_id, current_user)

    assignment_scene_rows = get_assignment_scene_rows(db, assignment)
    case_ids = get_assignment_case_ids_from_scenes(db, assignment)
    scene_ids = [row.scene_id for row in assignment_scene_rows]
    cases = db.query(models.Case).filter(models.Case.id.in_(case_ids)).all() if case_ids else []
    case_map = {item.id: item for item in cases}
    scenes = db.query(models.Scene).filter(models.Scene.id.in_(scene_ids)).all() if scene_ids else []
    scenes_by_case_id: dict[int, list[models.Scene]] = {}
    scene_order = {row.scene_id: row.sort_order or 0 for row in assignment_scene_rows}
    for scene in scenes:
        scenes_by_case_id.setdefault(scene.case_id, []).append(scene)

    case_payloads = []
    for case_id in case_ids:
        case = case_map.get(case_id)
        status_payload = case_status_for_student(db, assignment, current_user.id, case_id)
        scene_payloads = []
        for scene in sorted(scenes_by_case_id.get(case_id, []), key=lambda item: scene_order.get(item.id, item.id)):
            submission = latest_submission_for_scene(db, assignment.id, current_user.id, scene.id)
            training_status = "not_started"
            if submission and submission.status in FINAL_SUBMISSION_STATUSES:
                training_status = "completed" if submission.status == "submitted" else "late"
            elif submission and submission.status:
                training_status = submission.status
            scene_payloads.append(
                {
                    "id": scene.id,
                    "name": scene_name(scene),
                    "difficulty": repair_text(scene.difficulty) if scene.difficulty else "",
                    "description": repair_text(scene.description) if scene.description else "",
                    "training_status": training_status,
                    "active_session_id": submission.training_session_id if submission and submission.status in {"in_progress", "evaluating"} else None,
                    "finished_session_id": submission.training_session_id if submission and submission.status in FINAL_SUBMISSION_STATUSES else None,
                    "final_score": submission.score if submission and submission.status in FINAL_SUBMISSION_STATUSES else None,
                    "submission": serialize_submission(submission),
                }
            )
        case_payloads.append(
            {
                **serialize_case_brief(case),
                **status_payload,
                "scenes": scene_payloads,
            }
        )

    classroom = db.query(models.TrainingClass).filter(models.TrainingClass.id == assignment.class_id).first()
    return {
        **serialize_assignment_base(db, assignment, include_cases=False),
        **assignment_status_for_student(db, assignment, current_user.id),
        "class_name": classroom.name if classroom else "",
        "cases": case_payloads,
        "content_unit": "scene",
    }


@router.get("", dependencies=[Depends(require_admin_user)])
@router.get("/", dependencies=[Depends(require_admin_user)])
def list_classes(db: Session = Depends(database.get_db)):
    classes = db.query(models.TrainingClass).order_by(models.TrainingClass.created_at.desc()).all()
    return [serialize_classroom(db, classroom) for classroom in classes]


@router.post("", dependencies=[Depends(require_admin_user)])
@router.post("/", dependencies=[Depends(require_admin_user)])
def create_class(
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Class name is required")
    classroom = models.TrainingClass(
        name=name,
        description=str(payload.get("description") or "").strip(),
        invite_code=generate_invite_code(db),
        muted=True,
        created_by=current_user.id,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return serialize_classroom(db, classroom)


@router.get("/{class_id}", dependencies=[Depends(require_admin_user)])
def get_class_detail(class_id: int, db: Session = Depends(database.get_db)):
    classroom = ensure_classroom(db, class_id)
    members = (
        db.query(models.ClassMembership, models.User)
        .join(models.User, models.User.id == models.ClassMembership.user_id)
        .filter(
            models.ClassMembership.class_id == class_id,
            models.ClassMembership.status == "active",
            models.ClassMembership.role == "student",
        )
        .order_by(models.User.username.asc())
        .all()
    )
    assignments = (
        db.query(models.TrainingAssignment)
        .filter(models.TrainingAssignment.class_id == class_id)
        .order_by(models.TrainingAssignment.created_at.desc())
        .all()
    )
    announcements = (
        db.query(models.ClassAnnouncement)
        .filter(models.ClassAnnouncement.class_id == class_id)
        .order_by(models.ClassAnnouncement.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "classroom": serialize_classroom(db, classroom),
        "students": [
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "joined_at": serialize_datetime(membership.joined_at),
            }
            for membership, user in members
        ],
        "assignments": [serialize_assignment_base(db, assignment) for assignment in assignments],
        "announcements": [serialize_announcement(item) for item in announcements],
    }


@router.post("/{class_id}/students", dependencies=[Depends(require_admin_user)])
def add_class_students(
    class_id: int,
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    ensure_classroom(db, class_id)
    raw_user_ids = payload.get("user_ids") or []
    raw_usernames = payload.get("usernames") or []
    user_ids = [int(item) for item in raw_user_ids if str(item).strip().isdigit()]
    usernames = [str(item).strip() for item in raw_usernames if str(item).strip()]
    if not user_ids and not usernames:
        raise HTTPException(status_code=400, detail="At least one student is required")

    query = db.query(models.User).filter(models.User.role == "student")
    filters = []
    if user_ids:
        filters.append(models.User.id.in_(user_ids))
    if usernames:
        filters.append(models.User.username.in_(usernames))
    students = query.filter(filters[0] if len(filters) == 1 else filters[0] | filters[1]).all()
    added = 0
    reactivated = 0
    for student in students:
        membership = (
            db.query(models.ClassMembership)
            .filter(
                models.ClassMembership.class_id == class_id,
                models.ClassMembership.user_id == student.id,
            )
            .first()
        )
        if membership:
            if membership.status != "active":
                membership.status = "active"
                reactivated += 1
            continue
        db.add(models.ClassMembership(class_id=class_id, user_id=student.id, role="student", status="active"))
        added += 1
    db.commit()
    return {"added_count": added, "reactivated_count": reactivated, "matched_count": len(students)}


@router.post("/{class_id}/announcements", dependencies=[Depends(require_admin_user)])
def create_announcement(
    class_id: int,
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_classroom(db, class_id)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Announcement title is required")
    announcement = models.ClassAnnouncement(
        class_id=class_id,
        title=title,
        content=str(payload.get("content") or "").strip(),
        category=str(payload.get("category") or "notice").strip() or "notice",
        created_by=current_user.id,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return serialize_announcement(announcement)


@router.get("/{class_id}/assignments", dependencies=[Depends(require_admin_user)])
def list_class_assignments(class_id: int, db: Session = Depends(database.get_db)):
    ensure_classroom(db, class_id)
    assignments = (
        db.query(models.TrainingAssignment)
        .filter(models.TrainingAssignment.class_id == class_id)
        .order_by(models.TrainingAssignment.created_at.desc())
        .all()
    )
    return [serialize_assignment_base(db, assignment) for assignment in assignments]


@router.post("/{class_id}/assignments", dependencies=[Depends(require_admin_user)])
def create_assignment(
    class_id: int,
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_classroom(db, class_id)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Assignment title is required")
    case_ids = []
    for item in payload.get("case_ids") or []:
        try:
            case_id = int(item)
        except (TypeError, ValueError):
            continue
        if case_id not in case_ids:
            case_ids.append(case_id)
    scene_ids = []
    for item in payload.get("scene_ids") or []:
        try:
            scene_id = int(item)
        except (TypeError, ValueError):
            continue
        if scene_id not in scene_ids:
            scene_ids.append(scene_id)
    if not case_ids and not scene_ids:
        raise HTTPException(status_code=400, detail="Select at least one case or scene")

    if case_ids:
        existing_case_ids = {
            row.id
            for row in db.query(models.Case.id).filter(models.Case.id.in_(case_ids)).all()
        }
        missing_case_ids = [case_id for case_id in case_ids if case_id not in existing_case_ids]
        if missing_case_ids:
            raise HTTPException(status_code=400, detail=f"Cases not found: {missing_case_ids}")

    published_at = parse_datetime(payload.get("published_at")) or datetime.utcnow()
    assignment = models.TrainingAssignment(
        class_id=class_id,
        title=title,
        instructions=str(payload.get("instructions") or "").strip(),
        scoring_rule=str(payload.get("scoring_rule") or "").strip(),
        allow_late=bool(payload.get("allow_late", False)),
        published_at=published_at,
        due_at=parse_datetime(payload.get("due_at")),
        created_by=current_user.id,
        status="published",
    )
    db.add(assignment)
    db.flush()
    if scene_ids and not case_ids:
        linked_case_ids = [
            row.case_id
            for row in db.query(models.Scene.case_id).filter(models.Scene.id.in_(scene_ids)).all()
        ]
        for case_id in linked_case_ids:
            if case_id not in case_ids:
                case_ids.append(case_id)
    for index, case_id in enumerate(case_ids):
        db.add(models.TrainingAssignmentCase(assignment_id=assignment.id, case_id=case_id, sort_order=index))
    set_assignment_scenes(db, assignment, scene_ids=scene_ids, case_ids=case_ids)
    db.commit()
    db.refresh(assignment)
    return serialize_assignment_base(db, assignment)


@router.post("/{class_id}/assignments/{assignment_id}/late-policy", dependencies=[Depends(require_admin_user)])
def update_assignment_late_policy(
    class_id: int,
    assignment_id: int,
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    assignment = ensure_assignment(db, class_id, assignment_id)
    if "allow_late" in payload:
        assignment.allow_late = bool(payload.get("allow_late"))
    if "due_at" in payload:
        assignment.due_at = parse_datetime(payload.get("due_at"))
    db.commit()
    db.refresh(assignment)
    return serialize_assignment_base(db, assignment)


@router.post("/{class_id}/assignments/{assignment_id}/students/{student_id}/override", dependencies=[Depends(require_admin_user)])
def update_student_assignment_override(
    class_id: int,
    assignment_id: int,
    student_id: int,
    payload: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    assignment = ensure_assignment(db, class_id, assignment_id)
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    membership = (
        db.query(models.ClassMembership)
        .filter(
            models.ClassMembership.class_id == class_id,
            models.ClassMembership.user_id == student_id,
            models.ClassMembership.status == "active",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=400, detail="Student is not in this class")
    override = (
        db.query(models.AssignmentStudentOverride)
        .filter(
            models.AssignmentStudentOverride.assignment_id == assignment.id,
            models.AssignmentStudentOverride.user_id == student_id,
        )
        .first()
    )
    if not override:
        override = models.AssignmentStudentOverride(assignment_id=assignment.id, user_id=student_id)
        db.add(override)
    if "allow_late" in payload:
        value = payload.get("allow_late")
        override.allow_late = None if value is None else bool(value)
    if "due_at" in payload:
        override.due_at = parse_datetime(payload.get("due_at"))
    if "note" in payload:
        override.note = str(payload.get("note") or "").strip()
    db.commit()
    db.refresh(override)
    policy = get_effective_assignment_policy(db, assignment, student_id)
    return {
        "student_id": student_id,
        "assignment_id": assignment_id,
        "allow_late": policy["allow_late"],
        "due_at": serialize_datetime(policy["due_at"]),
        "override_allow_late": override.allow_late,
        "override_due_at": serialize_datetime(override.due_at),
        "note": override.note or "",
    }


@router.get("/{class_id}/assignments/{assignment_id}/review", dependencies=[Depends(require_admin_user)])
def get_assignment_review(class_id: int, assignment_id: int, db: Session = Depends(database.get_db)):
    assignment = ensure_assignment(db, class_id, assignment_id)
    assignment_scene_rows = get_assignment_scene_rows(db, assignment)
    scene_ids = [row.scene_id for row in assignment_scene_rows]
    case_ids = get_assignment_case_ids_from_scenes(db, assignment)
    case_map = {
        item.id: item
        for item in db.query(models.Case).filter(models.Case.id.in_(case_ids)).all()
    } if case_ids else {}
    scene_map = {
        item.id: item
        for item in db.query(models.Scene).filter(models.Scene.id.in_(scene_ids)).all()
    } if scene_ids else {}
    students = (
        db.query(models.User)
        .join(models.ClassMembership, models.ClassMembership.user_id == models.User.id)
        .filter(
            models.ClassMembership.class_id == class_id,
            models.ClassMembership.status == "active",
            models.ClassMembership.role == "student",
        )
        .order_by(models.User.username.asc())
        .all()
    )
    rows = []
    for student in students:
        policy = get_effective_assignment_policy(db, assignment, student.id)
        case_rows = []
        scores = []
        final_statuses = []
        active_count = 0
        last_submitted_at = None
        for scene_id in scene_ids:
            scene = scene_map.get(scene_id)
            case_id = getattr(scene, "case_id", None)
            submission = latest_submission_for_scene(db, assignment.id, student.id, scene_id)
            is_final = bool(submission and submission.status in FINAL_SUBMISSION_STATUSES)
            if submission and submission.status in {"in_progress", "evaluating"}:
                active_count += 1
            if is_final:
                final_statuses.append(submission.status)
                if isinstance(submission.score, int):
                    scores.append(submission.score)
                if submission.submitted_at and (last_submitted_at is None or submission.submitted_at > last_submitted_at):
                    last_submitted_at = submission.submitted_at
            case_rows.append(
                {
                    **serialize_case_brief(case_map.get(case_id)),
                    "scene": serialize_scene_brief(scene, case_map.get(case_id)),
                    "submission": serialize_submission(submission),
                    "status": "submitted" if is_final else (submission.status if submission else "missing"),
                }
            )

        completed_count = len(final_statuses)
        required_count = len(scene_ids)
        if required_count and completed_count == required_count:
            status = "late" if any(item == "late" for item in final_statuses) else "submitted"
        elif active_count:
            status = "in_progress"
        elif policy["is_overdue"]:
            status = "unsubmitted"
        else:
            status = "pending"

        rows.append(
            {
                "student": {"id": student.id, "username": student.username},
                "status": status,
                "completed_count": completed_count,
                "required_count": required_count,
                "missing_count": max(required_count - completed_count, 0),
                "score_avg": round(sum(scores) / len(scores), 1) if scores else None,
                "last_submitted_at": serialize_datetime(last_submitted_at),
                "effective_due_at": serialize_datetime(policy["due_at"]),
                "allow_late": policy["allow_late"],
                "is_overdue": policy["is_overdue"],
                "cases": case_rows,
            }
        )

    return {
        "assignment": serialize_assignment_base(db, assignment),
        "cases": [serialize_case_brief(case_map.get(case_id)) for case_id in case_ids],
        "scenes": [
            serialize_scene_brief(scene_map.get(scene_id), case_map.get(getattr(scene_map.get(scene_id), "case_id", None)))
            for scene_id in scene_ids
        ],
        "rows": rows,
        "summary": {
            "student_count": len(rows),
            "submitted_count": sum(1 for row in rows if row["status"] in {"submitted", "late"}),
            "in_progress_count": sum(1 for row in rows if row["status"] == "in_progress"),
            "unsubmitted_count": sum(1 for row in rows if row["status"] == "unsubmitted"),
            "pending_count": sum(1 for row in rows if row["status"] == "pending"),
        },
        "incomplete_students": [
            row["student"]
            for row in rows
            if row["status"] == "unsubmitted"
        ],
    }


@router.get(
    "/{class_id}/assignments/{assignment_id}/submissions/{submission_id}",
    dependencies=[Depends(require_admin_user)],
)
def get_submission_detail(
    class_id: int,
    assignment_id: int,
    submission_id: int,
    db: Session = Depends(database.get_db),
):
    ensure_assignment(db, class_id, assignment_id)
    submission = (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.id == submission_id,
            models.AssignmentSubmission.assignment_id == assignment_id,
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    session = (
        db.query(models.TrainingSession)
        .filter(models.TrainingSession.id == submission.training_session_id)
        .first()
    )
    messages = []
    if session:
        messages = (
            db.query(models.Message)
            .filter(models.Message.session_id == session.id)
            .order_by(models.Message.created_at.asc())
            .all()
        )
    student = db.query(models.User).filter(models.User.id == submission.user_id).first()
    case = db.query(models.Case).filter(models.Case.id == submission.case_id).first()
    scene = db.query(models.Scene).filter(models.Scene.id == submission.scene_id).first() if submission.scene_id else None
    return {
        "submission": serialize_submission(submission, include_evaluation=True),
        "student": {"id": getattr(student, "id", None), "username": getattr(student, "username", "")},
        "case": serialize_case_brief(case),
        "scene": {"id": getattr(scene, "id", None), "name": scene_name(scene)},
        "session": {
            "id": getattr(session, "id", None),
            "status": getattr(session, "status", None),
            "created_at": serialize_datetime(getattr(session, "created_at", None)),
            "evaluation_result": safe_json_loads(getattr(session, "evaluation_result", None), None),
        },
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "speaker_name": message.speaker_name,
                "created_at": serialize_datetime(message.created_at),
            }
            for message in messages
        ],
    }
