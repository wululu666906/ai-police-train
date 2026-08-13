from datetime import datetime, timedelta
import os
from collections import Counter
import json
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import database
import models
from routers.auth import require_admin_user
from services.rag_service import rag_service
from services.training_runtime_service import load_runtime_state

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_admin_user)])


class _TimedCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._values: dict[tuple, tuple[float, object]] = {}

    def get(self, key: tuple):
        now = monotonic()
        with self._lock:
            cached = self._values.get(key)
            if cached and now - cached[0] < self.ttl_seconds:
                return cached[1]
            if cached:
                self._values.pop(key, None)
        return None

    def set(self, key: tuple, value):
        with self._lock:
            self._values[key] = (monotonic(), value)


_dashboard_cache = _TimedCache(ttl_seconds=30)


def _get_rag_count() -> int:
    try:
        current_count = rag_service.collection.count()
        if current_count:
            return current_count
        if not os.path.exists("./chroma_db"):
            return 0
        import chromadb

        client = chromadb.PersistentClient(path="./chroma_db")
        try:
            collection = client.get_collection("legal_knowledge")
            return collection.count()
        except Exception:
            return 0
    except Exception as error:
        print(f"RAG stats error: {error}")
        return 0


def _safe_json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


@router.get("/stats")
def get_stats(db: Session = Depends(database.get_db)):
    cached = _dashboard_cache.get(("stats",))
    if cached is not None:
        return cached

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    seven_days_ago = today_start - timedelta(days=6)

    case_count = db.query(models.Case).count()
    role_count = db.query(models.Role).count()
    session_count = db.query(models.TrainingSession).count()
    student_count = db.query(models.User).filter(models.User.role == "student").count()
    active_session_count = db.query(models.TrainingSession).filter(models.TrainingSession.status == "active").count()
    finished_session_count = db.query(models.TrainingSession).filter(models.TrainingSession.status == "finished").count()
    today_session_count = (
        db.query(models.TrainingSession)
        .filter(models.TrainingSession.created_at >= today_start)
        .count()
    )
    rag_count = _get_rag_count()

    recent_sessions = (
        db.query(models.TrainingSession.created_at)
        .filter(models.TrainingSession.created_at >= seven_days_ago)
        .all()
    )
    finished_reports = (
        db.query(models.TrainingSession.evaluation_result)
        .filter(
            models.TrainingSession.status == "finished",
            models.TrainingSession.evaluation_result.isnot(None),
        )
        .all()
    )
    day_buckets = {}
    for offset in range(7):
        day = seven_days_ago + timedelta(days=offset)
        day_key = day.strftime("%Y-%m-%d")
        day_buckets[day_key] = {
            "label": day.strftime("%m-%d"),
            "count": 0,
        }

    for (created_at,) in recent_sessions:
        if not created_at:
            continue
        day_key = created_at.strftime("%Y-%m-%d")
        if day_key in day_buckets:
            day_buckets[day_key]["count"] += 1

    trend = list(day_buckets.values())
    peak_daily_sessions = max((item["count"] for item in trend), default=0)
    avg_daily_sessions = round(sum(item["count"] for item in trend) / 7, 1)
    completion_rate = round((finished_session_count / session_count) * 100, 1) if session_count else 0.0
    active_rate = round((active_session_count / session_count) * 100, 1) if session_count else 0.0

    missing_counter = Counter()
    scene_gap_counter = Counter()
    total_gap_reports = 0
    for (evaluation_result,) in finished_reports:
        payload = _safe_json_loads(evaluation_result, {})
        meta = payload.get("evaluation_meta") if isinstance(payload, dict) else {}
        summary = meta.get("stage_gap_summary") if isinstance(meta, dict) else {}
        if not isinstance(summary, dict):
            continue
        total_gap_reports += 1
        scene_type = str(summary.get("scene_type") or "通用").strip() or "通用"
        missing_items = summary.get("missing") if isinstance(summary.get("missing"), list) else []
        clean_missing = [str(item).strip() for item in missing_items if str(item).strip()]
        if clean_missing:
            scene_gap_counter[scene_type] += 1
        for item in clean_missing:
            missing_counter[item] += 1

    stage_gap_top_missing = [
        {"label": label, "count": count}
        for label, count in missing_counter.most_common(5)
    ]
    stage_gap_scene_risk = [
        {"scene_type": scene_type, "count": count}
        for scene_type, count in scene_gap_counter.most_common(4)
    ]

    result = {
        "cases": case_count,
        "roles": role_count,
        "sessions": session_count,
        "students": student_count,
        "rag": rag_count,
        "today_sessions": today_session_count,
        "active_sessions": active_session_count,
        "finished_sessions": finished_session_count,
        "completion_rate": completion_rate,
        "active_rate": active_rate,
        "peak_daily_sessions": peak_daily_sessions,
        "avg_daily_sessions": avg_daily_sessions,
        "stage_gap_reports": total_gap_reports,
        "stage_gap_top_missing": stage_gap_top_missing,
        "stage_gap_scene_risk": stage_gap_scene_risk,
        "trend": trend,
        "updated_at": now.isoformat(),
    }
    _dashboard_cache.set(("stats",), result)
    return result


@router.get("/state-calibration")
def get_state_calibration(
    scene_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(database.get_db),
):
    limit = max(1, min(500, int(limit or 100)))
    cache_key = ("state-calibration", scene_id, limit)
    cached = _dashboard_cache.get(cache_key)
    if cached is not None:
        return cached

    query = db.query(models.TrainingSession).order_by(models.TrainingSession.created_at.desc())
    if scene_id is not None:
        query = query.filter(models.TrainingSession.scene_id == scene_id)
    sessions = query.limit(limit).all()
    result = {"status": "removed", "sessions": len(sessions), "message": "旧状态影响链路已删除"}
    _dashboard_cache.set(cache_key, result)
    return result
