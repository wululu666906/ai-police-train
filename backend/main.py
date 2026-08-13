import os

# 在所有依赖 import 之前抑制 TensorFlow Lite / PaddlePaddle INFO 日志
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")

import json
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

import database
import models
from env_loader import load_backend_env
from routers import auth, cases, classes, dashboard, face, knowledge, ops, speech, student, student_imports, training, videos, video_training
from services.face_service import warmup_face_engine_async
from services.object_storage_service import LOCAL_OBJECT_ROOT
from services.video_playback_service import schedule_existing_videos
from services.case_pipeline_service import resume_pending_jobs

load_backend_env()

# 不在启动时强制初始化数据库，因为项目已经提供 init_db.py。
# models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI虚拟警情模拟训练平台 - API", version="1.0.0")


@app.exception_handler(Exception)
async def unhandled_exception_to_chinese_response(_: Request, error: Exception):
    """Prevent framework/dependency errors from being displayed in English."""
    print(f"Unhandled server error: {error}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器处理请求时发生异常，请稍后重试。"},
    )


def ensure_default_users():
    # Demo accounts with known passwords must never be created implicitly in a
    # deployed environment.  Existing accounts are left untouched; this flag
    # is only for an explicitly requested local demo setup.
    if os.getenv("SEED_DEMO_ACCOUNTS", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    db = database.SessionLocal()
    try:
        users = db.query(models.User).all()
        updated = False
        for user in users:
            if user.hashed_password and not user.hashed_password.startswith("$pbkdf2-sha256$"):
                user.hashed_password = auth.hash_password(user.hashed_password)
                updated = True

        default_accounts = [
            ("maintainer", "maintainer"),
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
        # Older project databases predate this table.  Returning early here
        # leaves every student-case request failing when it aggregates message
        # activity, so create the table first and only then add newer columns.
        models.Message.__table__.create(bind=engine, checkfirst=True)
        inspector = inspect(engine)
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
        # The scene-to-role mapping was absent from early databases.  Create
        # both tables before inspecting columns so old installations can load
        # scene role data instead of failing at query time.
        models.Role.__table__.create(bind=engine, checkfirst=True)
        models.SceneRole.__table__.create(bind=engine, checkfirst=True)
        inspector = inspect(engine)
        role_columns = {column["name"] for column in inspector.get_columns("roles")}
        scene_role_columns = {column["name"] for column in inspector.get_columns("scene_roles")}
        statements = []
        if "person_id" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN person_id VARCHAR(50)")
        if "interaction_style" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN interaction_style VARCHAR(20) DEFAULT '配合型'")
        if "persona_meta" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN persona_meta TEXT DEFAULT '{}'")
        if "init_risk" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN init_risk INTEGER DEFAULT 50")
        if "init_expression_clarity" not in role_columns:
            statements.append("ALTER TABLE roles ADD COLUMN init_expression_clarity INTEGER DEFAULT 50")
        if "initial_state" not in scene_role_columns:
            statements.append("ALTER TABLE scene_roles ADD COLUMN initial_state TEXT DEFAULT '{}'")

        if not statements:
            return

        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    except Exception as error:
        print(f"Role schema compatibility check failed: {error}")


def ensure_user_schema_compatibility():
    engine = database.engine
    try:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            return

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        column_defs = {
            "avatar_url": "VARCHAR(300)",
            "display_name": "VARCHAR(80)",
            "real_name": "VARCHAR(80)",
            "gender": "VARCHAR(20)",
            "phone": "VARCHAR(30)",
            "email": "VARCHAR(120)",
            "unit": "VARCHAR(120)",
            "department": "VARCHAR(120)",
            "account_group": "VARCHAR(80)",
            "bio": "TEXT",
            "last_login_at": "DATETIME",
            "updated_at": "DATETIME",
        }
        statements = [
            f"ALTER TABLE users ADD COLUMN {name} {column_type}"
            for name, column_type in column_defs.items()
            if name not in user_columns
        ]

        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
    except Exception as error:
        print(f"User schema compatibility check failed: {error}")


def ensure_account_group_schema_compatibility():
    try:
        models.AccountGroup.__table__.create(bind=database.engine, checkfirst=True)
    except Exception as error:
        print(f"Account group schema compatibility check failed: {error}")


def ensure_classroom_schema_compatibility():
    try:
        for table in (
            models.TrainingClass.__table__,
            models.ClassMembership.__table__,
            models.TrainingAssignment.__table__,
            models.TrainingAssignmentCase.__table__,
            models.TrainingAssignmentScene.__table__,
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
            models.VideoTrainingArtifact.__table__,
        ):
            table.create(bind=database.engine, checkfirst=True)
        # 为已存在的 training_videos 表补充 briefing 列
        from sqlalchemy import inspect, text
        inspector = inspect(database.engine)
        if "training_videos" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("training_videos")}
            statements = []
            with database.engine.begin() as conn:
                if "briefing" not in cols:
                    statements.append("ALTER TABLE training_videos ADD COLUMN briefing TEXT")
                # Video hall serializes these fields for every video.  They
                # were introduced after existing local databases were created.
                if "scenario_type" not in cols:
                    statements.append("ALTER TABLE training_videos ADD COLUMN scenario_type VARCHAR(50)")
                if "difficulty" not in cols:
                    statements.append("ALTER TABLE training_videos ADD COLUMN difficulty VARCHAR(20) DEFAULT 'normal'")
                for statement in statements:
                    conn.execute(text(statement))
        if "video_training_sessions" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("video_training_sessions")}
            statements = []
            if "evaluation_status" not in cols:
                statements.append("ALTER TABLE video_training_sessions ADD COLUMN evaluation_status VARCHAR(20) DEFAULT 'pending'")
            if "evaluation_result" not in cols:
                statements.append("ALTER TABLE video_training_sessions ADD COLUMN evaluation_result TEXT")
            if "evaluation_error" not in cols:
                statements.append("ALTER TABLE video_training_sessions ADD COLUMN evaluation_error TEXT")
            if "evaluation_started_at" not in cols:
                statements.append("ALTER TABLE video_training_sessions ADD COLUMN evaluation_started_at DATETIME")
            if "evaluation_completed_at" not in cols:
                statements.append("ALTER TABLE video_training_sessions ADD COLUMN evaluation_completed_at DATETIME")
            with database.engine.begin() as conn:
                for statement in statements:
                    conn.execute(text(statement))
        if "video_node_results" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("video_node_results")}
            statements = []
            if "evidence_payload" not in cols:
                statements.append("ALTER TABLE video_node_results ADD COLUMN evidence_payload TEXT")
            if "assessment_payload" not in cols:
                statements.append("ALTER TABLE video_node_results ADD COLUMN assessment_payload TEXT")
            with database.engine.begin() as conn:
                for statement in statements:
                    conn.execute(text(statement))
        if "training_session_artifacts" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("training_session_artifacts")}
            statements = []
            if "artifact_type" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN artifact_type VARCHAR(30) DEFAULT 'screenshot'")
            if "file_path" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN file_path VARCHAR(500)")
            if "mime_type" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN mime_type VARCHAR(120)")
            if "file_size" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN file_size INTEGER")
            if "duration_seconds" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN duration_seconds INTEGER")
            with database.engine.begin() as conn:
                for statement in statements:
                    conn.execute(text(statement))
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
        if "video_session_id" not in event_columns:
            statements.append("ALTER TABLE face_verification_events ADD COLUMN video_session_id INTEGER")

        if statements:
            with database.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
    except Exception as error:
        print(f"Face schema compatibility check failed: {error}")


def ensure_training_session_schema_compatibility():
    try:
        models.TrainingSessionArtifact.__table__.create(bind=database.engine, checkfirst=True)
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
        if "training_session_artifacts" in inspector.get_table_names():
            cols = {column["name"] for column in inspector.get_columns("training_session_artifacts")}
            statements = []
            if "artifact_type" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN artifact_type VARCHAR(30) DEFAULT 'screenshot'")
            if "file_path" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN file_path VARCHAR(500)")
            if "mime_type" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN mime_type VARCHAR(120)")
            if "file_size" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN file_size INTEGER")
            if "duration_seconds" not in cols:
                statements.append("ALTER TABLE training_session_artifacts ADD COLUMN duration_seconds INTEGER")
            if statements:
                with database.engine.begin() as connection:
                    for statement in statements:
                        connection.execute(text(statement))
        _backfill_training_session_timer_fields()
    except Exception as error:
        print(f"Training session schema compatibility check failed: {error}")


def ensure_scene_schema_compatibility():
    try:
        models.Scene.__table__.create(bind=database.engine, checkfirst=True)
        inspector = inspect(database.engine)
        if "scenes" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("scenes")}
        statements = []
        if "estimated_minutes" not in existing:
            statements.append("ALTER TABLE scenes ADD COLUMN estimated_minutes INTEGER")
        if "opening_config" not in existing:
            statements.append("ALTER TABLE scenes ADD COLUMN opening_config TEXT DEFAULT '{}'")
        if statements:
            with database.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
    except Exception as error:
        print(f"Scene schema compatibility check failed: {error}")


def backfill_role_state_defaults():
    db = database.SessionLocal()
    try:
        from services.training_view_service import backfill_role_initial_states

        backfill_role_initial_states(db)
    except Exception as error:
        db.rollback()
        print(f"Role state backfill failed: {error}")
    finally:
        db.close()


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


_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
if _cors_origins_env:
    cors_allow_origins = [item.strip() for item in _cors_origins_env.split(",") if item.strip()]
else:
    cors_allow_origins = [
        "http://localhost:5556",
        "http://127.0.0.1:5556",
        "http://localhost:6670",
        "http://127.0.0.1:6670",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
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
app.include_router(classes.router)
app.include_router(videos.router)
app.include_router(video_training.router)
app.include_router(face.router)
app.include_router(speech.router)
app.include_router(ops.router)
app.include_router(student_imports.router)

# 兼容 Docker 静态前端的 /api 前缀调用（frontend/.env.production 默认 VITE_API_URL=/api）
app.include_router(auth.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(classes.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(video_training.router, prefix="/api")
app.include_router(face.router, prefix="/api")
app.include_router(speech.router, prefix="/api")
app.include_router(ops.router, prefix="/api")
app.include_router(student_imports.router, prefix="/api")


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


@app.get("/api/healthz")
def health_check_api():
    return {"status": "ok"}


def ensure_ops_audit_schema_compatibility():
    try:
        models.OpsAuditLog.__table__.create(bind=database.engine, checkfirst=True)
        models.SpeechUsageLog.__table__.create(bind=database.engine, checkfirst=True)
        models.AIWorkflowRun.__table__.create(bind=database.engine, checkfirst=True)
        models.CaseStoryVersion.__table__.create(bind=database.engine, checkfirst=True)
        models.OpsIssueRecord.__table__.create(bind=database.engine, checkfirst=True)
    except Exception as error:
        print(f"Ops audit/speech usage schema compatibility check failed: {error}")


def ensure_performance_indexes():
    indexed_models = (
        models.TrainingSession,
        models.TrainingSessionArtifact,
        models.Message,
        models.VideoTrainingSession,
        models.VideoNodeResult,
    )
    try:
        for model in indexed_models:
            for index in model.__table__.indexes:
                if index.name and index.name.startswith("ix_perf_"):
                    index.create(bind=database.engine, checkfirst=True)
    except Exception as error:
        print(f"Performance index compatibility check failed: {error}")


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

_profile_avatars_dir = os.path.join(os.path.dirname(__file__), "static", "profile_avatars")
os.makedirs(_profile_avatars_dir, exist_ok=True)
app.mount("/static/profile-avatars", StaticFiles(directory=_profile_avatars_dir), name="profile_avatars_static")

_session_media_dir = os.path.join(os.path.dirname(__file__), "static", "session_media")
os.makedirs(_session_media_dir, exist_ok=True)
app.mount("/static/session_media", StaticFiles(directory=_session_media_dir), name="session_media_static")

os.makedirs(LOCAL_OBJECT_ROOT, exist_ok=True)
app.mount("/object-storage", StaticFiles(directory=str(LOCAL_OBJECT_ROOT)), name="object_storage_static")

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


def _frontend_index_path() -> str:
    return os.path.join(frontend_dist, "index.html")


def _frontend_index_response() -> FileResponse:
    response = FileResponse(_frontend_index_path())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _is_browser_navigation(request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept


@app.middleware("http")
async def serve_spa_routes_before_api_prefixes(request, call_next):
    path = request.url.path
    if (
        request.method == "GET"
        and _is_browser_navigation(request)
        and path.startswith(("/admin", "/student", "/ops"))
        and not path.startswith("/api/")
    ):
        index_path = _frontend_index_path()
        if os.path.exists(index_path):
            return _frontend_index_response()
    return await call_next(request)


@app.middleware("http")
async def apply_frontend_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith(("/admin", "/student", "/ops", "/assets/")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

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
    # The project has no standalone migration module.  Create tables from the
    # current metadata, then run the compatibility helpers below for columns
    # added to existing SQLite installations.
    models.Base.metadata.create_all(bind=database.engine)
    ensure_user_schema_compatibility()
    ensure_message_schema_compatibility()
    ensure_role_schema_compatibility()
    ensure_scene_schema_compatibility()
    backfill_role_state_defaults()
    ensure_training_session_schema_compatibility()
    ensure_classroom_schema_compatibility()
    ensure_video_schema_compatibility()
    ensure_face_schema_compatibility()
    ensure_account_group_schema_compatibility()
    ensure_ops_audit_schema_compatibility()
    ensure_performance_indexes()
    ensure_default_users()
    schedule_existing_videos()
    resume_pending_jobs()
    if os.getenv("FACE_ENGINE_WARMUP", "0").strip().lower() in {"1", "true", "yes", "on"}:
        warmup_face_engine_async()


@app.get("/{catchall:path}")
def serve_vue_app(catchall: str):
    first_segment = (catchall.split("/", 1)[0] if catchall else "").strip()
    api_like_prefixes = {
        "api",
        "auth",
        "cases",
        "training",
        "dashboard",
        "knowledge",
        "student",
        "classes",
        "videos",
        "video-training",
        "face",
        "speech",
        "ops",
        "student-imports",
        "static",
    }
    if first_segment in api_like_prefixes:
        raise HTTPException(status_code=404, detail="Not Found")

    index_path = _frontend_index_path()
    if os.path.exists(index_path):
        return _frontend_index_response()
    return {"message": "AI虚拟警情模拟训练平台后端已启动（前端尚未构建）。"}
