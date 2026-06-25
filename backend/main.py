import json
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

import database
import models
from routers import auth, cases, classes, dashboard, face, knowledge, multimodal, speech, student, training, videos, video_training
from services.multimodal_service import warmup_deepface_async

# 不在启动时强制初始化数据库，因为项目已经提供 init_db.py。
# models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI虚拟警情模拟训练平台 - API", version="1.0.0")


def ensure_default_users():
    db = database.SessionLocal()
    try:
        users = db.query(models.User).all()
        updated = False
        for user in users:
            if user.hashed_password and not user.hashed_password.startswith("$pbkdf2-sha256$"):
                user.hashed_password = auth.hash_password(user.hashed_password)
                updated = True

        default_accounts = [
            ("admin", "admin"),
            ("student001", "student"),
            ("student002", "student"),
            ("student003", "student"),
            ("student004", "student"),
            ("student005", "student"),
        ]
        existing_usernames = {user.username for user in users}
        for username, role in default_accounts:
            if username not in existing_usernames:
                db.add(
                    models.User(
                        username=username,
                        hashed_password=auth.hash_password("123456"),
                        role=role,
                    )
                )
                updated = True

        if updated:
            db.commit()
    finally:
        db.close()


def ensure_message_schema_compatibility():
    engine = database.engine
    try:
        inspector = inspect(engine)
        if "messages" not in inspector.get_table_names():
            return

        message_columns = {column["name"] for column in inspector.get_columns("messages")}
        statements = []
        if "speaker_role_id" not in message_columns:
            statements.append("ALTER TABLE messages ADD COLUMN speaker_role_id INTEGER")
        if "speaker_name" not in message_columns:
            statements.append("ALTER TABLE messages ADD COLUMN speaker_name VARCHAR(50)")

        if not statements:
            return

        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    except Exception as error:
        print(f"Message schema compatibility check failed: {error}")


def ensure_role_schema_compatibility():
    engine = database.engine
    try:
        inspector = inspect(engine)
        if "roles" not in inspector.get_table_names():
            return

        role_columns = {column["name"] for column in inspector.get_columns("roles")}
        statements = []
        if "person_id" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN person_id VARCHAR(50)")
        if "interaction_style" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN interaction_style VARCHAR(20) DEFAULT '配合型'")
        if "persona_meta" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN persona_meta TEXT DEFAULT '{}'")

        if not statements:
            return

        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    except Exception as error:
        print(f"Role schema compatibility check failed: {error}")


def ensure_classroom_schema_compatibility():
    try:
        for table in (
            models.TrainingClass.__table__,
            models.ClassMembership.__table__,
            models.TrainingAssignment.__table__,
            models.TrainingAssignmentCase.__table__,
            models.AssignmentSubmission.__table__,
            models.AssignmentStudentOverride.__table__,
            models.ClassAnnouncement.__table__,
        ):
            table.create(bind=database.engine, checkfirst=True)
    except Exception as error:
        print(f"Classroom schema compatibility check failed: {error}")


def ensure_video_schema_compatibility():
    try:
        for table in (
            models.TrainingVideo.__table__,
            models.VideoNode.__table__,
            models.VideoTrainingSession.__table__,
            models.VideoNodeResult.__table__,
        ):
            table.create(bind=database.engine, checkfirst=True)
    except Exception as error:
        print(f"Video schema compatibility check failed: {error}")


def ensure_face_schema_compatibility():
    try:
        for table in (
            models.FaceProfile.__table__,
            models.FaceVerificationEvent.__table__,
        ):
            table.create(bind=database.engine, checkfirst=True)

        inspector = inspect(database.engine)
        table_columns = {
            table_name: {column["name"] for column in inspector.get_columns(table_name)}
            for table_name in ("face_profiles", "face_verification_events")
            if table_name in inspector.get_table_names()
        }
        statements = []
        profile_columns = table_columns.get("face_profiles", set())
        for column_name in ("embeddings_json", "sample_images_json", "quality_json"):
            if column_name not in profile_columns:
                statements.append(f"ALTER TABLE face_profiles ADD COLUMN {column_name} TEXT")

        event_columns = table_columns.get("face_verification_events", set())
        event_text_columns = ("reason_code", "quality_json", "liveness_json", "abnormal_level")
        for column_name in event_text_columns:
            if column_name not in event_columns:
                column_type = "VARCHAR(60)" if column_name == "reason_code" else ("VARCHAR(20)" if column_name == "abnormal_level" else "TEXT")
                statements.append(f"ALTER TABLE face_verification_events ADD COLUMN {column_name} {column_type}")

        if statements:
            with database.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
    except Exception as error:
        print(f"Face schema compatibility check failed: {error}")


def ensure_multimodal_schema_compatibility():
    try:
        for table in (
            models.MultimodalSessionMetric.__table__,
            models.MultimodalEvent.__table__,
        ):
            table.create(bind=database.engine, checkfirst=True)
        metric_columns = inspect(database.engine).get_columns("multimodal_session_metrics")
        existing = {column["name"] for column in metric_columns}
        column_defs = {
            "face_score": "INTEGER",
            "attention_score": "INTEGER",
            "final_score": "INTEGER",
            "adapter_status_json": "TEXT",
        }
        statements = [
            f"ALTER TABLE multimodal_session_metrics ADD COLUMN {name} {column_type}"
            for name, column_type in column_defs.items()
            if name not in existing
        ]
        if statements:
            with database.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
    except Exception as error:
        print(f"Multimodal schema compatibility check failed: {error}")


def ensure_training_session_schema_compatibility():
    try:
        inspector = inspect(database.engine)
        if "training_sessions" not in inspector.get_table_names():
            return

        existing = {column["name"] for column in inspector.get_columns("training_sessions")}
        statements = []
        if "training_started_at" not in existing:
            statements.append("ALTER TABLE training_sessions ADD COLUMN training_started_at DATETIME")
        if "training_finished_at" not in existing:
            statements.append("ALTER TABLE training_sessions ADD COLUMN training_finished_at DATETIME")

        if statements:
            with database.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
        _backfill_training_session_timer_fields()
    except Exception as error:
        print(f"Training session schema compatibility check failed: {error}")


def _parse_training_timer_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(normalized, pattern)
                except ValueError:
                    continue
    return None


def _timer_iso(value):
    parsed = _parse_training_timer_datetime(value)
    if not parsed:
        return None
    if parsed.tzinfo:
        return parsed.isoformat()
    return f"{parsed.isoformat()}+00:00"


def _backfill_training_session_timer_fields():
    db = database.SessionLocal()
    try:
        sessions = (
            db.query(models.TrainingSession)
            .filter(
                (models.TrainingSession.training_started_at.is_(None))
                | (models.TrainingSession.training_finished_at.is_(None))
                | (models.TrainingSession.evaluation_result.isnot(None))
            )
            .all()
        )
        changed = False
        for session in sessions:
            report = {}
            if session.evaluation_result:
                try:
                    report = json.loads(session.evaluation_result)
                except Exception:
                    report = {}
            meta = report.get("evaluation_meta") if isinstance(report, dict) else {}
            header = meta.get("report_header") if isinstance(meta, dict) else {}
            if not isinstance(header, dict):
                header = {}

            first_message = (
                db.query(models.Message.created_at)
                .filter(models.Message.session_id == session.id)
                .order_by(models.Message.created_at.asc())
                .first()
            )
            last_message = (
                db.query(models.Message.created_at)
                .filter(models.Message.session_id == session.id)
                .order_by(models.Message.created_at.desc())
                .first()
            )
            first_message_at = first_message[0] if first_message else None
            last_message_at = last_message[0] if last_message else None
            started_at = (
                session.training_started_at
                or _parse_training_timer_datetime(header.get("training_started_at"))
                or _parse_training_timer_datetime(header.get("created_at"))
                or session.created_at
                or first_message_at
            )
            finished_at = (
                session.training_finished_at
                or _parse_training_timer_datetime(header.get("training_finished_at"))
                or _parse_training_timer_datetime(header.get("finished_at"))
                or _parse_training_timer_datetime(report.get("evaluated_at") if isinstance(report, dict) else None)
                or last_message_at
                or started_at
            )

            if session.training_started_at is None and started_at:
                session.training_started_at = started_at
                changed = True
            if session.status == "finished" and session.training_finished_at is None and finished_at:
                session.training_finished_at = finished_at
                changed = True

            if isinstance(report, dict) and session.status == "finished":
                if "evaluation_meta" not in report or not isinstance(report.get("evaluation_meta"), dict):
                    report["evaluation_meta"] = {}
                header = report["evaluation_meta"].get("report_header")
                if not isinstance(header, dict):
                    header = {}
                duration_seconds = None
                if started_at and finished_at:
                    duration_seconds = max(0, int((finished_at - started_at).total_seconds()))
                next_header = {
                    **header,
                    "created_at": _timer_iso(session.created_at),
                    "training_started_at": _timer_iso(started_at),
                    "finished_at": _timer_iso(finished_at),
                    "training_finished_at": _timer_iso(finished_at),
                    "duration_seconds": duration_seconds,
                }
                report["evaluation_meta"]["report_header"] = next_header
                report["evaluated_at"] = _timer_iso(finished_at)
                next_json = json.dumps(report, ensure_ascii=False)
                if next_json != session.evaluation_result:
                    session.evaluation_result = next_json
                    changed = True

        if changed:
            db.commit()
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 部署到云服务器时可改为真实域名白名单。
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(training.router)
app.include_router(dashboard.router)
app.include_router(knowledge.router)
app.include_router(student.router)
app.include_router(speech.router)
app.include_router(classes.router)
app.include_router(videos.router)
app.include_router(video_training.router)
app.include_router(face.router)
app.include_router(multimodal.router)

# 兼容 Docker 静态前端的 /api 前缀调用（frontend/.env.production 默认 VITE_API_URL=/api）
app.include_router(auth.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(speech.router, prefix="/api")
app.include_router(classes.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(video_training.router, prefix="/api")
app.include_router(face.router, prefix="/api")
app.include_router(multimodal.router, prefix="/api")


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


@app.get("/api/healthz")
def health_check_api():
    return {"status": "ok"}

# 像素风头像静态文件
_avatars_dir = os.path.join(os.path.dirname(__file__), "static", "avatars")
if os.path.exists(_avatars_dir):
    app.mount("/avatars", StaticFiles(directory=_avatars_dir), name="avatars")

# 视频实训静态文件（上传后的视频/封面）
_videos_dir = os.path.join(os.path.dirname(__file__), "static", "videos")
os.makedirs(_videos_dir, exist_ok=True)
app.mount("/static/videos", StaticFiles(directory=_videos_dir), name="videos_static")

_thumbnails_dir = os.path.join(os.path.dirname(__file__), "static", "thumbnails")
os.makedirs(_thumbnails_dir, exist_ok=True)
app.mount("/static/thumbnails", StaticFiles(directory=_thumbnails_dir), name="thumbnails_static")

_face_profiles_dir = os.path.join(os.path.dirname(__file__), "static", "face_profiles")
os.makedirs(_face_profiles_dir, exist_ok=True)
app.mount("/static/face-profiles", StaticFiles(directory=_face_profiles_dir), name="face_profiles_static")

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


def _frontend_index_path() -> str:
    return os.path.join(frontend_dist, "index.html")


def _is_browser_navigation(request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept


@app.middleware("http")
async def serve_spa_routes_before_api_prefixes(request, call_next):
    path = request.url.path
    if (
        request.method == "GET"
        and _is_browser_navigation(request)
        and path.startswith(("/admin", "/student"))
        and not path.startswith("/api/")
    ):
        index_path = _frontend_index_path()
        if os.path.exists(index_path):
            return FileResponse(index_path)
    return await call_next(request)

if os.path.exists(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/favicon.svg")
    def serve_favicon():
        return FileResponse(os.path.join(frontend_dist, "favicon.svg"))

    @app.get("/icons.svg")
    def serve_icons():
        return FileResponse(os.path.join(frontend_dist, "icons.svg"))


@app.on_event("startup")
def on_startup():
    ensure_message_schema_compatibility()
    ensure_role_schema_compatibility()
    ensure_training_session_schema_compatibility()
    ensure_classroom_schema_compatibility()
    ensure_video_schema_compatibility()
    ensure_face_schema_compatibility()
    ensure_multimodal_schema_compatibility()
    ensure_default_users()
    warmup_deepface_async()


@app.get("/{catchall:path}")
def serve_vue_app(catchall: str):
    index_path = _frontend_index_path()
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI虚拟警情模拟训练平台后端已启动（前端尚未构建）。"}
