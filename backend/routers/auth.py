from datetime import datetime, timedelta, timezone
import os
import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import database
import models
import schemas

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-jwt-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def needs_password_upgrade(stored_password: str) -> bool:
    return not stored_password.startswith("$pbkdf2-sha256$")


def create_access_token(*, user_id: int, username: str, role: str) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def build_username_from_template(template: str, seq_no: int) -> str:
    raw_template = (template or "").strip()
    if not raw_template:
        raise HTTPException(status_code=400, detail="Template is required")

    suffix_len = 0
    for char in reversed(raw_template):
        if char in {"x", "X"}:
            suffix_len += 1
        else:
            break

    if suffix_len <= 0:
        raise HTTPException(status_code=400, detail="Template must end with x placeholders, for example 251040702xx")

    number_text = str(seq_no)
    if len(number_text) > suffix_len:
        raise HTTPException(status_code=400, detail=f"Number {seq_no} exceeds template capacity")

    prefix = raw_template[:-suffix_len]
    return f"{prefix}{number_text.zfill(suffix_len)}"


def build_username_range(template: str, start_no: int, end_no: int) -> list[str]:
    if start_no <= 0 or end_no <= 0:
        raise HTTPException(status_code=400, detail="Start and end numbers must be positive integers")
    if start_no > end_no:
        raise HTTPException(status_code=400, detail="Start number cannot be greater than end number")
    return [build_username_from_template(template, seq_no) for seq_no in range(start_no, end_no + 1)]


def authenticate_user(db: Session, identifier: str, password: str) -> models.User | None:
    user = db.query(models.User).filter(models.User.username == identifier).first()
    if not user:
        return None

    stored_password = user.hashed_password or ""
    if verify_password(password, stored_password):
        return user

    if needs_password_upgrade(stored_password) and stored_password == password:
        user.hashed_password = hash_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub") or 0)
    except (JWTError, ValueError, TypeError):
        raise credentials_error

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise credentials_error
    return user


def require_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    return current_user


def _safe_json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    identifier = (form_data.username or "").strip()
    password = form_data.password or ""
    user = authenticate_user(db, identifier, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect account or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }


@router.post("/register", response_model=schemas.User)
def register(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = models.User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/students", response_model=list[schemas.AdminStudentOverview])
def list_students(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    students = (
        db.query(models.User)
        .filter(models.User.role == "student")
        .order_by(models.User.username.asc())
        .all()
    )
    if not students:
        return []

    user_ids = [student.id for student in students]
    sessions = (
        db.query(
            models.TrainingSession.user_id,
            models.TrainingSession.status,
            models.TrainingSession.evaluation_result,
        )
        .filter(models.TrainingSession.user_id.in_(user_ids))
        .all()
    )

    stats_by_user: dict[int, dict] = {
        user_id: {"total_sessions": 0, "finished_sessions": 0, "scores": [], "gap_counter": Counter()}
        for user_id in user_ids
    }
    for row in sessions:
        current = stats_by_user.setdefault(row.user_id, {"total_sessions": 0, "finished_sessions": 0, "scores": [], "gap_counter": Counter()})
        current["total_sessions"] += 1
        if row.status == "finished":
            current["finished_sessions"] += 1

        payload = _safe_json_loads(row.evaluation_result, {})
        if not isinstance(payload, dict):
            continue
        total_score = payload.get("total_score")
        if isinstance(total_score, (int, float)):
            current["scores"].append(float(total_score))
        meta = payload.get("evaluation_meta") if isinstance(payload.get("evaluation_meta"), dict) else {}
        stage_gap_summary = meta.get("stage_gap_summary") if isinstance(meta, dict) else {}
        missing_items = stage_gap_summary.get("missing") if isinstance(stage_gap_summary, dict) and isinstance(stage_gap_summary.get("missing"), list) else []
        for item in missing_items:
            clean = str(item or "").strip()
            if clean:
                current["gap_counter"][clean] += 1

    results = []
    for student in students:
        stats = stats_by_user.get(student.id, {})
        scores = stats.get("scores") or []
        gap_counter = stats.get("gap_counter") or Counter()
        results.append(
            schemas.AdminStudentOverview(
                id=student.id,
                username=student.username,
                role=student.role,
                created_at=student.created_at,
                total_sessions=int(stats.get("total_sessions") or 0),
                finished_sessions=int(stats.get("finished_sessions") or 0),
                avg_score=round(sum(scores) / len(scores), 1) if scores else None,
                top_gap_missing=[label for label, _ in gap_counter.most_common(3)],
            )
        )
    return results


@router.post("/students/batch", response_model=schemas.BatchStudentCreateResponse)
def batch_create_students(
    payload: schemas.BatchStudentCreateRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    password = (payload.password or "").strip()

    if not password:
        raise HTTPException(status_code=400, detail="Initial password is required")

    created_usernames: list[str] = []
    skipped_usernames: list[str] = []
    usernames = build_username_range(payload.template, int(payload.start_no), int(payload.end_no))

    for username in usernames:
        existing_user = db.query(models.User).filter(models.User.username == username).first()
        if existing_user:
            skipped_usernames.append(username)
            continue

        db.add(
            models.User(
                username=username,
                hashed_password=hash_password(password),
                role="student",
            )
        )
        created_usernames.append(username)

    if created_usernames:
        db.commit()

    return schemas.BatchStudentCreateResponse(
        created_count=len(created_usernames),
        skipped_count=len(skipped_usernames),
        created_usernames=created_usernames,
        skipped_usernames=skipped_usernames,
    )


@router.post("/students/import", response_model=schemas.BatchStudentCreateResponse)
def import_students(
    payload: schemas.StudentImportCreateRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    password = (payload.password or "").strip()
    if not password:
        raise HTTPException(status_code=400, detail="Initial password is required")

    raw_usernames = [str(item or "").strip() for item in payload.usernames]
    usernames = [item for item in raw_usernames if item]
    if not usernames:
        raise HTTPException(status_code=400, detail="At least one username is required")

    unique_usernames = list(dict.fromkeys(usernames))
    created_usernames: list[str] = []
    skipped_usernames: list[str] = []

    for username in unique_usernames:
        existing_user = db.query(models.User).filter(models.User.username == username).first()
        if existing_user:
            skipped_usernames.append(username)
            continue

        db.add(
            models.User(
                username=username,
                hashed_password=hash_password(password),
                role="student",
            )
        )
        created_usernames.append(username)

    if created_usernames:
        db.commit()

    return schemas.BatchStudentCreateResponse(
        created_count=len(created_usernames),
        skipped_count=len(skipped_usernames),
        created_usernames=created_usernames,
        skipped_usernames=skipped_usernames,
    )


@router.api_route("/students/batch", methods=["DELETE"], response_model=schemas.BatchStudentDeleteResponse)
def batch_delete_students(
    payload: schemas.BatchStudentDeleteRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    usernames = build_username_range(payload.template, int(payload.start_no), int(payload.end_no))
    users = (
        db.query(models.User)
        .filter(models.User.role == "student", models.User.username.in_(usernames))
        .all()
    )

    found_by_username = {user.username: user for user in users}
    deleted_usernames = [username for username in usernames if username in found_by_username]
    skipped_usernames = [username for username in usernames if username not in found_by_username]

    if users:
        user_ids = [user.id for user in users]
        session_ids = [
            item[0]
            for item in db.query(models.TrainingSession.id)
            .filter(models.TrainingSession.user_id.in_(user_ids))
            .all()
        ]

        if session_ids:
            db.query(models.Message).filter(models.Message.session_id.in_(session_ids)).delete(
                synchronize_session=False
            )
            db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(
                synchronize_session=False
            )

        db.query(models.User).filter(models.User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()

    return schemas.BatchStudentDeleteResponse(
        deleted_count=len(deleted_usernames),
        skipped_count=len(skipped_usernames),
        deleted_usernames=deleted_usernames,
        skipped_usernames=skipped_usernames,
    )
