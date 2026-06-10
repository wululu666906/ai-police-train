"""Delete all cases and related training data (scenes, roles, sessions, messages)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import database
import models


def purge_all_cases() -> dict[str, int]:
    db = database.SessionLocal()
    try:
        msg_count = db.query(models.Message).delete()
        session_count = db.query(models.TrainingSession).delete()
        scene_role_count = db.query(models.SceneRole).delete()
        role_count = db.query(models.Role).delete()
        scene_count = db.query(models.Scene).delete()
        case_count = db.query(models.Case).delete()
        db.commit()
        return {
            "cases": case_count,
            "scenes": scene_count,
            "roles": role_count,
            "scene_roles": scene_role_count,
            "training_sessions": session_count,
            "messages": msg_count,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    stats = purge_all_cases()
    print("已清空案件及相关数据：")
    for key, value in stats.items():
        print(f"  {key}: {value}")
