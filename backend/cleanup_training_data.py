import argparse
import json
from pathlib import Path

from database import SessionLocal
import models
from services.text_repair import repair_payload, repair_text


def clamp_score(value: int | None, default: int) -> int:
    try:
        numeric = int(value if value is not None else default)
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(100, numeric))


def build_change(bucket: str, record_id: int, field_name: str, before, after) -> dict:
    return {
        "bucket": bucket,
        "id": record_id,
        "field": field_name,
        "before": before,
        "after": after,
    }


def update_field(model_obj, field_name: str, next_value, bucket: str, changes: list[dict], apply_changes: bool) -> bool:
    current = getattr(model_obj, field_name, None)
    if current == next_value:
        return False
    changes.append(build_change(bucket, model_obj.id, field_name, current, next_value))
    if apply_changes:
        setattr(model_obj, field_name, next_value)
    return True


def update_text_field(model_obj, field_name: str, bucket: str, changes: list[dict], apply_changes: bool) -> bool:
    current = getattr(model_obj, field_name, None)
    repaired = repair_text(current)
    return update_field(model_obj, field_name, repaired, bucket, changes, apply_changes)


def clean_json_text(model_obj, field_name: str, bucket: str, changes: list[dict], apply_changes: bool) -> bool:
    current = getattr(model_obj, field_name, None)
    if not current:
        return False
    try:
        parsed = json.loads(current)
    except Exception:
        repaired = repair_text(current)
        return update_field(model_obj, field_name, repaired, bucket, changes, apply_changes)

    repaired_payload = repair_payload(parsed)
    repaired_json = json.dumps(repaired_payload, ensure_ascii=False)
    return update_field(model_obj, field_name, repaired_json, bucket, changes, apply_changes)


def collect_changes(apply_changes: bool) -> tuple[dict[str, int], list[dict]]:
    db = SessionLocal()
    stats = {
        "cases": 0,
        "scenes": 0,
        "roles": 0,
        "messages": 0,
        "sessions": 0,
    }
    changes: list[dict] = []

    try:
        for case in db.query(models.Case).all():
            changed = False
            for field_name in ("title", "case_type", "background", "original_content"):
                changed = update_text_field(case, field_name, "cases", changes, apply_changes) or changed
            changed = clean_json_text(case, "structured_data", "cases", changes, apply_changes) or changed
            if changed:
                stats["cases"] += 1

        for scene in db.query(models.Scene).all():
            changed = False
            for field_name in ("name", "description", "difficulty", "dispatch_brief", "first_impression"):
                changed = update_text_field(scene, field_name, "scenes", changes, apply_changes) or changed
            changed = clean_json_text(scene, "stages", "scenes", changes, apply_changes) or changed
            if changed:
                stats["scenes"] += 1

        for role in db.query(models.Role).all():
            changed = False
            for field_name in (
                "name",
                "role_type",
                "personality",
                "speaking_style",
                "status",
                "iq_level",
                "eq_level",
                "lying_ability",
                "weakness",
            ):
                changed = update_text_field(role, field_name, "roles", changes, apply_changes) or changed
            for field_name in ("knows_facts", "does_not_know", "hidden_truths"):
                changed = clean_json_text(role, field_name, "roles", changes, apply_changes) or changed
            if changed:
                stats["roles"] += 1

        for message in db.query(models.Message).all():
            changed = False
            changed = update_text_field(message, "content", "messages", changes, apply_changes) or changed
            changed = update_text_field(message, "inner_thought", "messages", changes, apply_changes) or changed
            if changed:
                stats["messages"] += 1

        for session in db.query(models.TrainingSession).all():
            changed = False
            changed = update_field(
                session,
                "current_emotion",
                clamp_score(session.current_emotion, 50),
                "sessions",
                changes,
                apply_changes,
            ) or changed
            changed = update_field(
                session,
                "current_trust",
                clamp_score(session.current_trust, 30),
                "sessions",
                changes,
                apply_changes,
            ) or changed
            next_status = session.status if session.status in ("active", "finished") else "active"
            changed = update_field(session, "status", next_status, "sessions", changes, apply_changes) or changed
            changed = clean_json_text(session, "revealed_info", "sessions", changes, apply_changes) or changed
            changed = clean_json_text(session, "evaluation_result", "sessions", changes, apply_changes) or changed
            if changed:
                stats["sessions"] += 1

        if apply_changes:
            db.commit()
        else:
            db.rollback()
        return stats, changes
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def write_report(report_path: str | None, payload: dict) -> None:
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Clean and normalize training data.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    parser.add_argument("--report", help="Write a JSON report to the given file path.")
    parser.add_argument("--limit", type=int, default=20, help="Preview at most this many field-level changes.")
    return parser.parse_args()


def main():
    args = parse_args()
    stats, changes = collect_changes(apply_changes=args.apply)
    payload = {
        "mode": "apply" if args.apply else "dry-run",
        "stats": stats,
        "change_count": len(changes),
        "preview": changes[: max(args.limit, 0)],
    }

    print(f"Cleanup mode: {payload['mode']}")
    print("Affected records:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print(f"Field changes: {len(changes)}")

    if payload["preview"]:
      print("Preview:")
      for item in payload["preview"]:
          print(f"  [{item['bucket']}#{item['id']}] {item['field']}: {item['before']} -> {item['after']}")
    else:
      print("Preview: no pending changes")

    write_report(args.report, payload)
    if args.report:
        print(f"Report written to: {args.report}")


if __name__ == "__main__":
    main()
