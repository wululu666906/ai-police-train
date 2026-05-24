import argparse
import json
import sqlite3
from pathlib import Path

from database import SQLALCHEMY_DATABASE_URL


QUESTION_MARK_THRESHOLD = 3
DEFAULT_PLACEHOLDER_TEXT = "[历史消息因早期编码问题无法恢复]"


def looks_like_placeholder_message(content: str | None) -> bool:
    text = (content or "").strip()
    return len(text) >= QUESTION_MARK_THRESHOLD and set(text) == {"?"}


def parse_args():
    parser = argparse.ArgumentParser(description="Preview or clean orphan training sessions and placeholder messages.")
    parser.add_argument("--apply", action="store_true", help="Apply the cleanup to the database.")
    parser.add_argument("--report", help="Write a JSON report to the given file path.")
    parser.add_argument("--limit", type=int, default=20, help="Preview at most this many records per bucket.")
    parser.add_argument(
        "--placeholder-text",
        default=DEFAULT_PLACEHOLDER_TEXT,
        help="Replacement text for placeholder user messages when --apply is used.",
    )
    return parser.parse_args()


def write_report(report_path: str | None, payload: dict) -> None:
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_sqlite_db_path() -> str:
    prefix = "sqlite:///"
    if not SQLALCHEMY_DATABASE_URL.startswith(prefix):
        raise RuntimeError(f"cleanup_history_artifacts.py only supports SQLite, got: {SQLALCHEMY_DATABASE_URL}")
    return SQLALCHEMY_DATABASE_URL.replace(prefix, "", 1)


def fetch_orphan_sessions(cursor: sqlite3.Cursor) -> list[dict]:
    rows = cursor.execute(
        """
        select ts.id, ts.user_id, ts.scene_id, ts.status, ts.created_at
        from training_sessions ts
        left join scenes s on s.id = ts.scene_id
        where s.id is null
        order by ts.id asc
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "scene_id": row[2],
            "status": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def fetch_placeholder_messages(cursor: sqlite3.Cursor) -> list[dict]:
    rows = cursor.execute(
        """
        select id, session_id, role, content, created_at
        from messages
        where role = 'user'
        order by id asc
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "session_id": row[1],
            "role": row[2],
            "content": row[3],
            "created_at": row[4],
        }
        for row in rows
        if looks_like_placeholder_message(row[3])
    ]


def main():
    args = parse_args()
    db_path = get_sqlite_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        orphan_sessions = fetch_orphan_sessions(cursor)
        placeholder_messages = fetch_placeholder_messages(cursor)

        report = {
            "mode": "apply" if args.apply else "dry-run",
            "database": db_path,
            "orphan_session_count_before": len(orphan_sessions),
            "placeholder_message_count_before": len(placeholder_messages),
            "orphan_session_preview": orphan_sessions[: max(args.limit, 0)],
            "placeholder_message_preview": placeholder_messages[: max(args.limit, 0)],
        }

        if args.apply:
            orphan_session_ids = [session["id"] for session in orphan_sessions]
            if orphan_session_ids:
                placeholders = ",".join("?" for _ in orphan_session_ids)
                cursor.execute(
                    f"delete from messages where session_id in ({placeholders})",
                    orphan_session_ids,
                )
                cursor.execute(
                    f"delete from training_sessions where id in ({placeholders})",
                    orphan_session_ids,
                )

            for message in placeholder_messages:
                cursor.execute(
                    "update messages set content = ? where id = ?",
                    (args.placeholder_text, message["id"]),
                )

            conn.commit()
            report["orphan_session_count_after"] = len(fetch_orphan_sessions(cursor))
            report["placeholder_message_count_after"] = len(fetch_placeholder_messages(cursor))
        else:
            conn.rollback()

        print(f"Cleanup mode: {report['mode']}")
        print(f"Database: {report['database']}")
        print(f"Orphan sessions before: {report['orphan_session_count_before']}")
        if "orphan_session_count_after" in report:
            print(f"Orphan sessions after: {report['orphan_session_count_after']}")
        print(f"Placeholder messages before: {report['placeholder_message_count_before']}")
        if "placeholder_message_count_after" in report:
            print(f"Placeholder messages after: {report['placeholder_message_count_after']}")
        if report["orphan_session_preview"]:
            print("Orphan session preview:")
            for item in report["orphan_session_preview"]:
                print(f"  session#{item['id']} user={item['user_id']} scene={item['scene_id']} status={item['status']}")
        if report["placeholder_message_preview"]:
            print("Placeholder message preview:")
            for item in report["placeholder_message_preview"]:
                print(f"  message#{item['id']} session={item['session_id']} content={item['content']}")

        write_report(args.report, report)
        if args.report:
            print(f"Report written to: {args.report}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
