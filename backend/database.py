import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# 锁定数据库根目录，避免因启动目录不同而连接到不同的 SQLite 文件。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "ai_police.db")


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
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
