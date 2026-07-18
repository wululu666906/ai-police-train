"""
数据库迁移脚本：为视频实训简化方案添加新字段

TrainingVideo 新增：scenario_type, difficulty
VideoNode 新增：node_interaction_type, ai_instructor_hint, choice_options, correct_answer

运行方式：python migrate_video_nodes.py
"""
import sqlite3
import os

from database import SQLALCHEMY_DATABASE_URL


def resolve_db_path() -> str:
    """Keep the standalone migration aligned with the application's SQLite URL."""
    prefix = "sqlite:///"
    if not SQLALCHEMY_DATABASE_URL.startswith(prefix):
        raise RuntimeError("migrate_video_nodes.py only supports SQLite DATABASE_URL values")
    return SQLALCHEMY_DATABASE_URL.removeprefix(prefix)


DB_PATH = resolve_db_path()


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}, skipping migration (init_db will create it).")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- TrainingVideo 新字段 ---
    if not column_exists(cursor, "training_videos", "scenario_type"):
        cursor.execute("ALTER TABLE training_videos ADD COLUMN scenario_type VARCHAR(50)")
        print("Added: training_videos.scenario_type")

    if not column_exists(cursor, "training_videos", "difficulty"):
        cursor.execute("ALTER TABLE training_videos ADD COLUMN difficulty VARCHAR(20) DEFAULT 'normal'")
        print("Added: training_videos.difficulty")

    # --- VideoNode 新字段 ---
    if not column_exists(cursor, "video_nodes", "node_interaction_type"):
        cursor.execute("ALTER TABLE video_nodes ADD COLUMN node_interaction_type VARCHAR(30) DEFAULT 'voice_qa'")
        print("Added: video_nodes.node_interaction_type")

    if not column_exists(cursor, "video_nodes", "ai_instructor_hint"):
        cursor.execute("ALTER TABLE video_nodes ADD COLUMN ai_instructor_hint TEXT")
        print("Added: video_nodes.ai_instructor_hint")

    if not column_exists(cursor, "video_nodes", "choice_options"):
        cursor.execute("ALTER TABLE video_nodes ADD COLUMN choice_options TEXT")
        print("Added: video_nodes.choice_options")

    if not column_exists(cursor, "video_nodes", "correct_answer"):
        cursor.execute("ALTER TABLE video_nodes ADD COLUMN correct_answer VARCHAR(200)")
        print("Added: video_nodes.correct_answer")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()
