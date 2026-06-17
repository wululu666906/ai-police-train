import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

import database
import models
from routers import auth, cases, classes, dashboard, knowledge, speech, student, training, videos, video_training

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
        # 为已存在的 training_videos 表补充 briefing 列
        from sqlalchemy import inspect, text
        inspector = inspect(database.engine)
        if "training_videos" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("training_videos")}
            with database.engine.begin() as conn:
                if "briefing" not in cols:
                    conn.execute(text("ALTER TABLE training_videos ADD COLUMN briefing TEXT"))
    except Exception as error:
        print(f"Video schema compatibility check failed: {error}")


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
    ensure_classroom_schema_compatibility()
    ensure_video_schema_compatibility()
    ensure_default_users()


@app.get("/{catchall:path}")
def serve_vue_app(catchall: str):
    index_path = _frontend_index_path()
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI虚拟警情模拟训练平台后端已启动（前端尚未构建）。"}
