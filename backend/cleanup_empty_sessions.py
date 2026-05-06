import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import case, func

from database import SessionLocal
import models


def get_empty_sessions(db, min_age_hours: int):
    cutoff = datetime.now() - timedelta(hours=max(min_age_hours, 0))
    rows = (
        db.query(
            models.TrainingSession.id,
            models.TrainingSession.user_id,
            models.TrainingSession.scene_id,
            models.TrainingSession.status,
            models.TrainingSession.created_at,
            func.sum(case((models.Message.role == "user", 1), else_=0)).label("user_message_count"),
            func.sum(case((models.Message.role.in_(("assistant", "ai")), 1), else_=0)).label("assistant_message_count"),
        )
        .outerjoin(models.Message, models.Message.session_id == models.TrainingSession.id)
        .group_by(models.TrainingSession.id)
        .having(func.sum(case((models.Message.role == "user", 1), else_=0)) == 0)
        .having(func.sum(case((models.Message.role.in_(("assistant", "ai")), 1), else_=0)) == 0)
        .filter(models.TrainingSession.created_at <= cutoff)
        .order_by(models.TrainingSession.created_at.asc())
        .all()
    )
    return [
        {
            "session_id": row.id,
            "user_id": row.user_id,
            "scene_id": row.scene_id,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def write_report(report_path: str | None, payload: dict) -> None:
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Preview or cleanup empty training sessions.")
    parser.add_argument("--apply", action="store_true", help="Delete matched empty sessions.")
    parser.add_argument("--report", help="Write a JSON report to the given path.")
    parser.add_argument("--limit", type=int, default=20, help="Preview at most this many sessions.")
    parser.add_argument("--min-age-hours", type=int, default=24, help="Only process empty sessions older than this many hours.")
    return parser.parse_args()


def main():
    args = parse_args()
    db = SessionLocal()
    try:
        empty_sessions = get_empty_sessions(db, args.min_age_hours)
        preview = empty_sessions[: max(args.limit, 0)]
        payload = {
            "mode": "apply" if args.apply else "dry-run",
            "min_age_hours": args.min_age_hours,
            "empty_session_count": len(empty_sessions),
            "preview": preview,
        }

        print(f"Empty-session cleanup mode: {payload['mode']}")
        print(f"Min age hours: {args.min_age_hours}")
        print(f"Matched sessions: {len(empty_sessions)}")
        if preview:
            print("Preview:")
            for item in preview:
                print(
                    f"  session#{item['session_id']} user={item['user_id']} scene={item['scene_id']} "
                    f"status={item['status']} created_at={item['created_at']}"
                )
        else:
            print("Preview: no matched empty sessions")

        if args.apply and empty_sessions:
            matched_ids = [item["session_id"] for item in empty_sessions]
            db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(matched_ids)).delete(
                synchronize_session=False
            )
            db.commit()
            print(f"Deleted sessions: {len(matched_ids)}")
        else:
            db.rollback()

        write_report(args.report, payload)
        if args.report:
            print(f"Report written to: {args.report}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
