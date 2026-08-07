"""Bounded asynchronous workflow for case import, personas and scenes."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import database
import models
from .persona_soul_service import enrich_personas
from .scene_design_service import compile_scene_lifecycles
from .case_scene_contract_service import build_case_quality_report, compile_case_scene_artifacts
from .workflow_job_service import update_job
from .workflow_service import workflow_service
from .case_source_compaction_service import compact_case_source, compact_role_memories
from .case_role_reconciliation_service import reconcile_case_roles
from .case_story_reconstruction_service import generate_case_narrative, reconstruct_story_document
from .case_knowledge_repository import store_case_knowledge, upsert_node


_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(os.getenv("CASE_PIPELINE_WORKERS", "1"))),
    thread_name_prefix="case-pipeline",
)
_SCHEDULED: set[str] = set()
_LOCK = threading.Lock()


def _pipeline_version() -> str:
    configured = os.getenv("CASE_PIPELINE_VERSION", "case-pipeline-v7-role-reconciliation")
    story_provider = os.getenv("CASE_STORY_PROVIDER", "deepseek")
    story_model = os.getenv("CASE_STORY_MODEL", "")
    fallback = os.getenv("CASE_STORY_ALLOW_PROVIDER_FALLBACK", "0")
    return f"{configured}|story={story_provider}:{story_model}|fallback={fallback}|cache-v2"


def _hash_payload(source_text: str, source_mode: str) -> str:
    pipeline_version = _pipeline_version()
    raw = f"{pipeline_version}\0{source_mode}\0{source_text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def _result_is_reusable(result_json: str | None) -> bool:
    text = str(result_json or "")
    if not text:
        return False
    bad_markers = (
        "Error code: 402",
        "Insufficient Balance",
        "Balance 不足",
        "余额不足",
        "额度不足",
        "invalid_request_error",
        "完整剧情专家模型不可用",
        "规则兜底解析",
        "\"used_rule_fallback\": true",
        "块 ",
        " / paragraph / body",
        " / 段落 / 正文",
        "docx_xml_text",
    )
    return not any(marker in text for marker in bad_markers)


def _run(job_id: str) -> None:
    db = database.SessionLocal()
    try:
        job = db.query(models.CasePipelineJob).filter(models.CasePipelineJob.id == job_id).first()
        if not job or job.status == "cancelled":
            return
        request = json.loads(job.request_json or "{}")
    finally:
        db.close()

    try:
        update_job(job_id, status="running", stage="extracting", progress=8, status_message="正在读取案件内容", started_at=datetime.utcnow(), error_message=None)
        text = str(request.get("source_text") or "").strip()
        if not text:
            raise ValueError("案件内容为空")

        compacted_source = compact_case_source(text)
        namespace = f"case-source:{job.input_hash}"
        update_job(job_id, stage="facts", progress=18, status_message="正在并行整理人物来源与创作完整剧情")

        def build_case_state() -> dict[str, Any]:
            return workflow_service.parse_case_for_training(
                compacted_source["training_text"],
                source_mode=str(request.get("source_mode") or "plain_case"),
                source_meta=request.get("source_meta") if isinstance(request.get("source_meta"), dict) else None,
            )

        def build_story_draft() -> tuple[str, dict[str, Any]]:
            try:
                return generate_case_narrative(compacted_source["training_text"])
            except Exception as exc:
                return "", {"attempts": getattr(exc, "trace", []), "error": str(exc)[:500]}

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="case-import-core") as executor:
            case_future = executor.submit(build_case_state)
            story_future = executor.submit(build_story_draft)
            case_info = case_future.result()
            story_draft, story_trace = story_future.result()
        if not story_draft and story_trace.get("error"):
            warnings = case_info.get("parse_warnings") if isinstance(case_info.get("parse_warnings"), list) else []
            warnings.append(f"完整剧情专家模型不可用，已保留来源事件版本：{story_trace['error']}")
            case_info["parse_warnings"] = list(dict.fromkeys(warnings))
        update_job(job_id, stage="story", progress=38, status_message="正在核对故事覆盖并生成完整事件明细")
        story_graph = reconstruct_story_document(
            case_info.get("case_reconstruction") or {},
            case_info.get("persons") or [],
            source_text=compacted_source["training_text"],
            use_model=False,
            narrative_override=story_draft,
            generation_trace=story_trace,
        )
        case_info["complete_story"] = story_graph["complete_story"]
        case_info["full_narrative"] = story_graph["complete_story"]
        case_info["narrative_document"] = {
            "schema_version": 5,
            "format": "word",
            "content": story_graph["complete_story"],
            "role": "deepseek_expert_case_narrative",
            "policy": "canonical_outcome_with_rich_main_and_side_branches",
        }
        case_info["story_documents"] = story_graph["story_documents"]
        case_info["event_story"] = story_graph["event_document"]
        case_info["story_world"] = {
            **(case_info.get("story_world") or {}),
            "complete_story": story_graph["complete_story"],
            "nodes": story_graph["nodes"],
            "coverage": story_graph["coverage"],
            "event_entries": story_graph["event_entries"],
            "story_generation": story_graph["generation_trace"],
        }
        case_info["original_content"] = text
        case_info["rawText"] = text
        upsert_node(namespace, "excluded-appendix", "source_appendix", compacted_source["excluded_appendix"])
        case_info["source_compaction"] = {
            key: value for key, value in compacted_source.items()
            if key not in {"training_text", "excluded_appendix"}
        }
        case_info["knowledge_namespace"] = namespace

        update_job(job_id, stage="roles", progress=48, status_message="正在核对完整剧情中的人物与来源记忆")
        case_info = reconcile_case_roles(
            case_info,
            source_text=compacted_source["training_text"],
            complete_story=story_graph["complete_story"],
        )
        case_info["persons"] = compact_role_memories(case_info.get("persons") or [])
        case_info["knowledge_manifest"] = store_case_knowledge(namespace, case_info)

        update_job(job_id, stage="personas", progress=55, status_message="正在形成角色行为画像")
        case_info = enrich_personas(case_info, use_model=True)
        case_info["knowledge_manifest"] = store_case_knowledge(namespace, case_info)

        update_job(job_id, stage="scenes", progress=70, status_message="正在按时间、空间和在场人物设计训练场景")
        scene_context = dict(case_info)
        scene_context["story_world"] = {
            key: value for key, value in (case_info.get("story_world") or {}).items()
            if key not in {"person_cards", "complete_story", "source_sections"}
        }
        scene_context["persons"] = [
            {
                "name": person.get("name"),
                "role_type": person.get("role_type") or person.get("role"),
                "status": person.get("status"),
                "current_goal": person.get("current_goal"),
                "core_concern": person.get("core_concern"),
                "behavior_profile": person.get("behavior_profile") or person.get("personality"),
                "triggers": person.get("triggers") or person.get("trigger_points"),
                "calming_points": person.get("calming_points") or person.get("soothing_points"),
                "answer_boundaries": person.get("answer_boundaries") or person.get("does_not_know"),
                "role_memories": (person.get("role_memories") or [])[:12],
                "knowledge_node_id": f"role:{person.get('name')}",
                "role_memory_count": len(person.get("role_memories") or []),
            }
            for person in case_info.get("persons") or []
            if isinstance(person, dict) and person.get("role_memories")
        ]
        scene_result = workflow_service.generate_scenes(scene_context, scene_generation_strategy="case_driven")
        scenes = compile_scene_lifecycles(case_info, scene_result.get("scenes") or [])

        update_job(job_id, stage="validating", progress=92, status_message="正在检查角色边界和训练闭环")
        case_info["scene_generation_mode"] = scene_result.get("scene_generation_mode") or ""
        case_info["ai_workflow"] = scene_result.get("ai_workflow") or {}
        derived = compile_case_scene_artifacts(case_info, scenes)
        scenes = derived["scenes"]
        quality_report = build_case_quality_report(case_info, scenes)
        persisted_case_info = dict(case_info)
        persisted_case_info.pop("source_sections", None)
        if persisted_case_info.get("full_narrative") == persisted_case_info.get("complete_story"):
            persisted_case_info.pop("full_narrative", None)
        persisted_case_info["story_world"] = {
            key: value for key, value in (persisted_case_info.get("story_world") or {}).items()
            if key not in {"person_cards", "complete_story", "source_sections"}
        }
        result = {
            "case_info": {
                **persisted_case_info,
                "scene_generation_mode": scene_result.get("scene_generation_mode") or "",
                "scene_generation_warning": scene_result.get("scene_generation_warning") or "",
            },
            "scenes": scenes,
            "scene_generation_mode": scene_result.get("scene_generation_mode") or "",
            "scene_generation_warning": scene_result.get("scene_generation_warning") or "",
            "scene_blueprints": derived["scene_blueprints"],
            "scene_scripts": derived["scene_scripts"],
            "scene_role_map": derived["scene_role_map"],
            "training_tasks": derived["training_tasks"],
            "state_machine": derived["state_machine"],
            "observable_scoring_rules": derived["observable_scoring_rules"],
            "derived_artifact_version": derived["derived_artifact_version"],
            "derived_revision": derived["derived_revision"],
            "scene_contract_schema_version": derived["scene_contract_schema_version"],
            "quality_report": quality_report,
            "ai_workflow": scene_result.get("ai_workflow") or {},
        }
        update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            status_message="案件已整理完成",
            result_json=json.dumps(result, ensure_ascii=False),
            completed_at=datetime.utcnow(),
        )
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            stage="failed",
            status_message="未能完成案件整理",
            error_message=str(exc)[:1200],
            completed_at=datetime.utcnow(),
        )
    finally:
        with _LOCK:
            _SCHEDULED.discard(job_id)


def _schedule(job_id: str) -> None:
    with _LOCK:
        if job_id in _SCHEDULED:
            return
        _SCHEDULED.add(job_id)
    _EXECUTOR.submit(_run, job_id)


def create_pipeline_job(
    *,
    source_text: str,
    source_mode: str,
    source_meta: dict[str, Any] | None = None,
    force_rebuild: bool = True,
) -> models.CasePipelineJob:
    clean = str(source_text or "").strip()
    input_hash = _hash_payload(clean, source_mode)
    db = database.SessionLocal()
    try:
        if not force_rebuild:
            cached = (
                db.query(models.CasePipelineJob)
                .filter(models.CasePipelineJob.input_hash == input_hash, models.CasePipelineJob.status == "completed")
                .order_by(models.CasePipelineJob.completed_at.desc())
                .first()
            )
            if cached and _result_is_reusable(cached.result_json):
                setattr(cached, "_cache_hit", True)
                db.expunge(cached)
                return cached
        job = models.CasePipelineJob(
            id=uuid.uuid4().hex,
            input_hash=input_hash,
            status="queued",
            stage="queued",
            progress=0,
            status_message="等待整理",
            request_json=json.dumps({"source_text": clean, "source_mode": source_mode, "source_meta": source_meta or {}}, ensure_ascii=False),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        db.expunge(job)
    finally:
        db.close()
    _schedule(job.id)
    return job


def resume_pending_jobs() -> None:
    db = database.SessionLocal()
    try:
        jobs = db.query(models.CasePipelineJob).filter(models.CasePipelineJob.status.in_(["queued", "running"])).all()
        job_ids = [job.id for job in jobs]
        for job in jobs:
            job.status = "queued"
            job.status_message = "恢复案件整理"
        db.commit()
    finally:
        db.close()
    for job_id in job_ids:
        _schedule(job_id)
