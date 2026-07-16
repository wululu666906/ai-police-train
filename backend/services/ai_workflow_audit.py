"""Persistence helpers for evidence-first case AI workflows.

Only operational metadata and source offsets are persisted here. Raw case text
continues to live in the case/file record and is never copied to the ops queue.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import database
import models


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def redact_error(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"sk-[A-Za-z0-9_.-]+", "sk-***", text)
    return text[:1000]


def record_workflow_run(
    *,
    correlation_id: str,
    stage: str,
    trace: dict[str, Any] | None = None,
    status: str = "success",
    used_rule_fallback: bool = False,
    error_code: str = "",
    error_summary: str = "",
    case_id: int | None = None,
) -> int | None:
    db = database.SessionLocal()
    try:
        payload = trace or {}
        attempts = payload.get("attempts") if isinstance(payload, dict) else []
        run = models.AIWorkflowRun(
            correlation_id=correlation_id,
            case_id=case_id,
            stage=stage,
            status=status,
            primary_provider=str(payload.get("primary_provider") or "") if isinstance(payload, dict) else "",
            final_provider=str(payload.get("final_provider") or "") if isinstance(payload, dict) else "",
            model=str((attempts[-1] if isinstance(attempts, list) and attempts else {}).get("model") or ""),
            attempt_count=len(attempts) if isinstance(attempts, list) else 0,
            switched_provider=bool(payload.get("switched_provider")) if isinstance(payload, dict) else False,
            used_rule_fallback=used_rule_fallback,
            error_code=str(error_code or "")[:80] or None,
            error_summary=redact_error(error_summary) or None,
            trace_json=_safe_json(payload),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    except Exception as exc:
        db.rollback()
        print(f"AI workflow audit persistence failed: {redact_error(exc)}")
        return None
    finally:
        db.close()


def record_issue(
    *,
    category: str,
    title: str,
    detail: str = "",
    severity: str = "warning",
    source: str = "ai_workflow",
    case_id: int | None = None,
    workflow_run_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db = database.SessionLocal()
    try:
        db.add(models.OpsIssueRecord(
            category=category,
            severity=severity,
            source=source,
            case_id=case_id,
            workflow_run_id=workflow_run_id,
            title=title[:240],
            detail=redact_error(detail),
            metadata_json=_safe_json(metadata or {}),
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Ops issue persistence failed: {redact_error(exc)}")
    finally:
        db.close()


def save_story_version(
    *,
    correlation_id: str,
    story: dict[str, Any],
    source_mode: str,
    case_id: int | None = None,
) -> int | None:
    db = database.SessionLocal()
    try:
        item = models.CaseStoryVersion(
            correlation_id=correlation_id,
            case_id=case_id,
            source_mode=source_mode,
            story_json=_safe_json(story),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id
    except Exception as exc:
        db.rollback()
        print(f"Case story persistence failed: {redact_error(exc)}")
        return None
    finally:
        db.close()
