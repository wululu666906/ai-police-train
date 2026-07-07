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
SECRET_KEY = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "change-this-jwt-secret-in-production"
)
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


PROFILE_DIMENSIONS = [
    ("communication", "沟通表达"),
    ("procedure", "流程规范"),
    ("risk", "风险判断"),
    ("emotion", "情绪控制"),
    ("information", "信息获取"),
]


def _round_score(value):
    if isinstance(value, (int, float)):
        return round(float(value), 1)
    return None


def _classify_score_level(score: float | None) -> str:
    if score is None:
        return "待积累"
    if score >= 85:
        return "优势明显"
    if score >= 70:
        return "基础稳定"
    if score >= 60:
        return "需要巩固"
    return "重点提升"


def _scene_status(score: float | None) -> str:
    if score is None:
        return "待积累"
    if score >= 85:
        return "表现突出"
    if score >= 70:
        return "相对稳定"
    if score >= 60:
        return "波动可控"
    return "需重点跟进"


def _stability_status(scores: list[float]) -> str:
    if len(scores) < 3:
        return "样本积累中"
    score_range = max(scores) - min(scores)
    if score_range <= 8:
        return "稳定优秀" if sum(scores) / len(scores) >= 80 else "稳定一般"
    if score_range <= 18:
        return "轻微波动"
    return "波动较大"


def _progress_status(scores: list[float]) -> str:
    if len(scores) < 4:
        return "趋势待观察"
    midpoint = len(scores) // 2
    early = scores[:midpoint]
    recent = scores[midpoint:]
    if not early or not recent:
        return "趋势待观察"
    diff = (sum(recent) / len(recent)) - (sum(early) / len(early))
    if diff >= 5:
        return "近期进步明显"
    if diff <= -5:
        return "近期有所回落"
    return "近期相对平稳"


def _dimension_key_from_index(index: int) -> tuple[str, str]:
    if 0 <= index < len(PROFILE_DIMENSIONS):
        return PROFILE_DIMENSIONS[index]
    return ("general", f"能力项{index + 1}")


def _extract_dimension_scores(payload: dict) -> dict[str, dict]:
    rows = payload.get("scores") if isinstance(payload.get("scores"), list) else []
    result: dict[str, dict] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        score = row.get("score")
        full_score = row.get("full_score")
        if not isinstance(score, (int, float)):
            continue
        key, default_label = _dimension_key_from_index(index)
        label = str(row.get("dimension") or default_label).strip() or default_label
        result[key] = {
            "label": default_label,
            "raw_label": label,
            "score": float(score),
            "full_score": float(full_score) if isinstance(full_score, (int, float)) and float(full_score) > 0 else 100.0,
        }
    return result


def _normalize_issue_label(item) -> str:
    return str(item or "").strip()


def _issue_category(label: str) -> str:
    lowered = label.lower()
    if any(keyword in label for keyword in ("情绪", "安抚", "沟通", "语言")):
        return "沟通处置"
    if any(keyword in label for keyword in ("流程", "规范", "处置", "程序")):
        return "流程执行"
    if any(keyword in label for keyword in ("风险", "受伤", "安全", "危险")):
        return "风险判断"
    if any(keyword in label for keyword in ("信息", "事实", "时间", "地点", "身份", "经过")):
        return "信息采集"
    if "law" in lowered:
        return "规范执行"
    return "综合能力"


def _issue_severity(count: int, boosted: bool = False) -> str:
    if boosted or count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def _build_profile_summary(student: models.User, stats: dict, dimensions: list[schemas.StudentProfileDimension], suggestions: list[str]) -> schemas.StudentProfileSummary:
    avg_score = stats.get("average_score")
    stability_status = _stability_status(stats.get("finished_scores") or [])
    progress_status = _progress_status(stats.get("finished_scores") or [])
    top_dimension = max(dimensions, key=lambda item: item.score, default=None)
    weak_dimension = min(dimensions, key=lambda item: item.score, default=None)

    strengths_text = top_dimension.label if top_dimension and top_dimension.score > 0 else "基础能力"
    weakness_text = weak_dimension.label if weak_dimension and weak_dimension.score > 0 else "综合表现"
    suggestion_text = suggestions[0] if suggestions else "建议继续通过阶段训练积累稳定表现。"
    summary_text = (
        f"{student.username} 当前整体处于“{_classify_score_level(avg_score)}”阶段，"
        f"{strengths_text}相对更稳，{weakness_text}仍需优先补强。{suggestion_text}"
    )

    return schemas.StudentProfileSummary(
        level=_classify_score_level(avg_score),
        summary_text=summary_text,
        total_sessions=int(stats.get("total_sessions") or 0),
        finished_sessions=int(stats.get("finished_sessions") or 0),
        average_score=_round_score(avg_score),
        latest_training_at=stats.get("latest_training_at"),
        stability_status=stability_status,
        progress_status=progress_status,
    )


def _build_dimension_cards(history_rows: list[dict]) -> list[schemas.StudentProfileDimension]:
    series_map: dict[str, list[tuple[float, float]]] = {key: [] for key, _ in PROFILE_DIMENSIONS}
    recent_map: dict[str, list[float]] = {key: [] for key, _ in PROFILE_DIMENSIONS}
    previous_map: dict[str, list[float]] = {key: [] for key, _ in PROFILE_DIMENSIONS}
    finished_rows = [row for row in history_rows if row.get("status") == "finished"]
    midpoint = len(finished_rows) // 2

    for index, row in enumerate(finished_rows):
        dimension_scores = row.get("dimension_scores") or {}
        for key, label in PROFILE_DIMENSIONS:
            payload = dimension_scores.get(key)
            if not payload:
                continue
            score = float(payload.get("score") or 0)
            full_score = float(payload.get("full_score") or 100)
            series_map[key].append((score, full_score))
            normalized_score = (score / full_score) * 100 if full_score else 0
            if index < midpoint:
                previous_map[key].append(normalized_score)
            else:
                recent_map[key].append(normalized_score)

    cards: list[schemas.StudentProfileDimension] = []
    for key, label in PROFILE_DIMENSIONS:
        values = series_map.get(key) or []
        if values:
            normalized_values = [(score / full_score) * 100 if full_score else 0 for score, full_score in values]
            avg_score = sum(normalized_values) / len(normalized_values)
            prev_values = previous_map.get(key) or []
            recent_values = recent_map.get(key) or []
            trend = "持平"
            if prev_values and recent_values:
                diff = (sum(recent_values) / len(recent_values)) - (sum(prev_values) / len(prev_values))
                if diff >= 5:
                    trend = "上升"
                elif diff <= -5:
                    trend = "下降"
            cards.append(
                schemas.StudentProfileDimension(
                    key=key,
                    label=label,
                    score=round(avg_score, 1),
                    full_score=100,
                    trend=trend,
                )
            )
        else:
            cards.append(
                schemas.StudentProfileDimension(
                    key=key,
                    label=label,
                    score=0,
                    full_score=100,
                    trend="待积累",
                )
            )
    return cards


def _build_scene_performance(history_rows: list[dict]) -> list[schemas.StudentProfileScenePerformance]:
    grouped: dict[str, list[float]] = {}
    for row in history_rows:
        label = str(row.get("scene_label") or "未分类场景").strip()
        total_score = row.get("total_score")
        if not isinstance(total_score, (int, float)):
            continue
        grouped.setdefault(label, []).append(float(total_score))

    results = []
    for label, scores in grouped.items():
        avg_score = sum(scores) / len(scores) if scores else None
        results.append(
            schemas.StudentProfileScenePerformance(
                label=label,
                session_count=len(scores),
                average_score=_round_score(avg_score),
                status=_scene_status(avg_score),
            )
        )
    results.sort(key=lambda item: ((item.average_score or 0), item.session_count))
    return results[:6]


def _build_issue_buckets(history_rows: list[dict]) -> tuple[list[schemas.StudentProfileIssue], list[schemas.StudentProfileIssue], list[schemas.StudentProfileIssue]]:
    overall_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    recent_counter: Counter[str] = Counter()
    recent_rows = history_rows[-5:]

    for row in history_rows:
        for label in row.get("missing_items") or []:
            clean = _normalize_issue_label(label)
            if not clean:
                continue
            overall_counter[clean] += 1
            if isinstance(row.get("total_score"), (int, float)) and float(row["total_score"]) < 60:
                risk_counter[clean] += 2
            if row.get("scene_label") and "高" in str(row.get("scene_label")):
                risk_counter[clean] += 1

    for row in recent_rows:
        for label in row.get("missing_items") or []:
            clean = _normalize_issue_label(label)
            if clean:
                recent_counter[clean] += 1

    def build_rows(counter: Counter[str], category: str, min_count: int = 1, boosted: bool = False) -> list[schemas.StudentProfileIssue]:
        rows: list[schemas.StudentProfileIssue] = []
        for label, count in counter.most_common():
            if count < min_count:
                continue
            rows.append(
                schemas.StudentProfileIssue(
                    label=label,
                    count=int(count),
                    severity=_issue_severity(int(count), boosted=boosted),
                    category=category or _issue_category(label),
                )
            )
        return rows[:5]

    high_frequency = build_rows(overall_counter, "", min_count=2)
    high_risk = build_rows(risk_counter, "", min_count=2, boosted=True)
    stubborn = build_rows(recent_counter, "", min_count=3)
    return high_frequency, high_risk, stubborn


def _build_suggestions(dimensions: list[schemas.StudentProfileDimension], high_frequency: list[schemas.StudentProfileIssue], stubborn: list[schemas.StudentProfileIssue]) -> list[str]:
    suggestions: list[str] = []
    weakest = sorted(dimensions, key=lambda item: item.score)[:2]
    for item in weakest:
        if item.score <= 0:
            continue
        if item.key == "information":
            suggestions.append("建议优先补练事实核验类场景，重点追问时间、地点、人物和经过。")
        elif item.key == "emotion":
            suggestions.append("建议增加情绪安抚训练，先稳住对方情绪再推进关键信息获取。")
        elif item.key == "procedure":
            suggestions.append("建议连续练习标准处置流程，先把开场、核实和收束动作练稳定。")
        elif item.key == "risk":
            suggestions.append("建议补练高压和风险识别场景，强化对受伤、安全和升级风险的判断。")
        else:
            suggestions.append("建议加强沟通表达训练，减少重复追问，提升推进效率。")

    if high_frequency:
        suggestions.append(f"当前最常见问题是“{high_frequency[0].label}”，建议安排专项复盘并连续跟踪。")
    if stubborn:
        suggestions.append(f"“{stubborn[0].label}”在最近训练中反复出现，建议教官重点盯防这一环节。")

    unique: list[str] = []
    for item in suggestions:
        if item not in unique:
            unique.append(item)
    return unique[:3]


def _build_trend_points(history_rows: list[dict]) -> list[schemas.StudentProfileTrendPoint]:
    points = []
    for row in history_rows[-6:]:
        total_score = row.get("total_score")
        if not isinstance(total_score, (int, float)):
            continue
        points.append(
            schemas.StudentProfileTrendPoint(
                session_id=int(row.get("session_id") or 0),
                score=round(float(total_score), 1),
                created_at=row.get("created_at"),
            )
        )
    return points


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

    user.last_login_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }


def _clean_optional_text(value: str | None, max_length: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > max_length:
        raise HTTPException(status_code=400, detail=f"字段长度不能超过 {max_length} 个字符")
    return text


@router.get("/me/settings", response_model=schemas.MySettingsResponse)
def get_my_settings(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    memberships = (
        db.query(models.TrainingClass.name)
        .join(models.ClassMembership, models.ClassMembership.class_id == models.TrainingClass.id)
        .filter(
            models.ClassMembership.user_id == current_user.id,
            models.ClassMembership.status == "active",
        )
        .order_by(models.TrainingClass.created_at.desc())
        .all()
    )
    return schemas.MySettingsResponse(
        user=schemas.User.model_validate(current_user),
        classes=[row[0] for row in memberships if row[0]],
    )


@router.put("/me/settings", response_model=schemas.MySettingsResponse)
def update_my_settings(
    payload: schemas.MySettingsProfile,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user.display_name = _clean_optional_text(payload.display_name, 80)
    current_user.real_name = _clean_optional_text(payload.real_name, 80)
    current_user.phone = _clean_optional_text(payload.phone, 30)
    current_user.email = _clean_optional_text(payload.email, 120)
    current_user.unit = _clean_optional_text(payload.unit, 120)
    current_user.department = _clean_optional_text(payload.department, 120)
    current_user.bio = _clean_optional_text(payload.bio, 300)
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return get_my_settings(db=db, current_user=current_user)


@router.post("/me/password")
def change_my_password(
    payload: schemas.ChangePasswordRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_password = payload.current_password or ""
    new_password = payload.new_password or ""
    if not verify_password(current_password, current_user.hashed_password or ""):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if len(new_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要 6 位")
    if verify_password(new_password, current_user.hashed_password or ""):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    current_user.hashed_password = hash_password(new_password.strip())
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()
    return {"success": True}


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


@router.get("/students/{student_id}/profile", response_model=schemas.AdminStudentProfile)
def get_student_profile(
    student_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    student = (
        db.query(models.User)
        .filter(models.User.id == student_id, models.User.role == "student")
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    rows = (
        db.query(
            models.TrainingSession.id,
            models.TrainingSession.status,
            models.TrainingSession.created_at,
            models.TrainingSession.evaluation_result,
            models.Scene.name,
            models.Scene.difficulty,
            models.Case.case_type,
        )
        .outerjoin(models.Scene, models.Scene.id == models.TrainingSession.scene_id)
        .outerjoin(models.Case, models.Case.id == models.Scene.case_id)
        .filter(models.TrainingSession.user_id == student.id)
        .order_by(models.TrainingSession.created_at.asc(), models.TrainingSession.id.asc())
        .all()
    )

    history_rows: list[dict] = []
    total_sessions = len(rows)
    finished_sessions = 0
    finished_scores: list[float] = []
    latest_training_at = rows[-1].created_at if rows else None

    for row in rows:
        payload = _safe_json_loads(row.evaluation_result, {})
        if not isinstance(payload, dict):
            payload = {}
        total_score = payload.get("total_score")
        if row.status == "finished" and isinstance(total_score, (int, float)):
            finished_sessions += 1
            finished_scores.append(float(total_score))
        dimension_scores = _extract_dimension_scores(payload)
        evaluation_meta = payload.get("evaluation_meta") if isinstance(payload.get("evaluation_meta"), dict) else {}
        stage_gap_summary = evaluation_meta.get("stage_gap_summary") if isinstance(evaluation_meta.get("stage_gap_summary"), dict) else {}
        missing_items = stage_gap_summary.get("missing") if isinstance(stage_gap_summary.get("missing"), list) else []
        scene_parts = [str(row.case_type or "").strip(), str(row.name or "").strip(), str(row.difficulty or "").strip()]
        scene_label = " / ".join([part for part in scene_parts if part]) or "未分类场景"
        history_rows.append(
            {
                "session_id": row.id,
                "status": row.status,
                "created_at": row.created_at,
                "total_score": float(total_score) if isinstance(total_score, (int, float)) else None,
                "dimension_scores": dimension_scores,
                "missing_items": [_normalize_issue_label(item) for item in missing_items if _normalize_issue_label(item)],
                "scene_label": scene_label,
            }
        )

    dimensions = _build_dimension_cards(history_rows)
    high_frequency, high_risk, stubborn = _build_issue_buckets(history_rows)
    suggestions = _build_suggestions(dimensions, high_frequency, stubborn)
    average_score = (sum(finished_scores) / len(finished_scores)) if finished_scores else None
    stats = {
        "total_sessions": total_sessions,
        "finished_sessions": finished_sessions,
        "average_score": average_score,
        "latest_training_at": latest_training_at,
        "finished_scores": finished_scores,
    }

    return schemas.AdminStudentProfile(
        student=schemas.User.model_validate(student),
        summary=_build_profile_summary(student, stats, dimensions, suggestions),
        dimensions=dimensions,
        scene_performance=_build_scene_performance(history_rows),
        high_frequency_issues=high_frequency,
        high_risk_issues=high_risk,
        stubborn_issues=stubborn,
        suggestions=suggestions,
        trend_points=_build_trend_points(history_rows),
    )


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
