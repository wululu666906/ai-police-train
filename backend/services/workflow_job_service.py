"""Persistence helpers for case pipeline jobs."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import database
import models


def serialize_job(job: models.CasePipelineJob, *, include_result: bool = True) -> dict[str, Any]:
    result = None
    if include_result and job.result_json:
        try:
            result = json.loads(job.result_json)
        except Exception:
            result = None
    return {
        "id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress": int(job.progress or 0),
        "message": job.status_message or "",
        "result": result,
        "error": job.error_message or "",
        "cache_hit": bool(getattr(job, "_cache_hit", False)),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def update_job(job_id: str, **values: Any) -> None:
    db = database.SessionLocal()
    try:
        job = db.query(models.CasePipelineJob).filter(models.CasePipelineJob.id == job_id).first()
        if not job:
            return
        for key, value in values.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
