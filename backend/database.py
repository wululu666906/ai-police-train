import os

from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from env_loader import load_backend_env

load_backend_env()

# 锁定数据库根目录，避免因启动目录不同而连接到不同的 SQLite 文件。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
DEFAULT_DB_PATH = os.path.join(DEFAULT_DATA_DIR, "ai_police.db")


def resolve_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    if not raw_url.startswith("sqlite:///"):
        return raw_url

    sqlite_path = raw_url.replace("sqlite:///", "", 1)
    if os.path.isabs(sqlite_path):
        return raw_url

    normalized_path = os.path.normpath(os.path.join(BASE_DIR, sqlite_path))
    return f"sqlite:///{normalized_path}"


SQLALCHEMY_DATABASE_URL = resolve_database_url()

# SQLite 特有配置；PostgreSQL 不需要 check_same_thread。
engine_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    sqlite_timeout = int(os.getenv("SQLITE_BUSY_TIMEOUT_SECONDS", "30"))
    engine_args["connect_args"] = {
        "check_same_thread": False,
        "timeout": sqlite_timeout,
    }

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_args)


if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"PRAGMA busy_timeout={int(os.getenv('SQLITE_BUSY_TIMEOUT_MS', '30000'))}")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
