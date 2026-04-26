import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# 强制使用绝对路径锁定数据库，防止因启动目录不同导致数据库偏移
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "ai_police.db")
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite 特有配置，PostgreSQL 不需要 check_same_thread
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
