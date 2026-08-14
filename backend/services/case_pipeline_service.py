"""Bounded asynchronous workflow for case import, personas and scenes."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import database
import models
from .scene_design_service import compile_scene_lifecycles
from .case_scene_contract_service import build_case_quality_report, compile_case_scene_artifacts
from .workflow_job_service import update_job
from .agent_case_service import generate_scenes_with_agent, parse_case_with_agent
from .case_source_compaction_service import compact_case_source, compact_role_memories
from .case_knowledge_repository import store_case_knowledge, upsert_node


_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(os.getenv("CASE_PIPELINE_WORKERS", "1"))),
    thread_name_prefix="case-pipeline",
)
_SCHEDULED: set[str] = set()
_LOCK = threading.Lock()


def _pipeline_version() -> str:
    configured = os.getenv("CASE_PIPELINE_VERSION", "case-pipeline-v11-narrative-story")
    return f"{configured}|ai-workflow=case-import-harness|cache-v3"


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_refs(item: dict[str, Any], source_text: str, content: str) -> list[dict[str, Any]]:
    proposed = item.get("source_refs")
    if isinstance(proposed, list):
        valid = [ref for ref in proposed if isinstance(ref, dict)]
        if valid:
            return valid
    position = source_text.find(content)
    if position >= 0:
        return [{"source_id": "complete-story", "start": position, "end": position + len(content), "summary": content[:180]}]
    return [{"source_id": "complete-story", "start": 0, "end": len(source_text), "summary": content[:180]}] if source_text else []


def _fact_cards_from_case(case_info: dict[str, Any]) -> list[dict[str, Any]]:
    story_world = case_info.get("story_world") if isinstance(case_info.get("story_world"), dict) else {}
    source_cards = [item for item in _items(story_world.get("fact_cards") or story_world.get("facts")) if isinstance(item, dict)]
    if not source_cards:
        for index, fact in enumerate(_items(case_info.get("key_facts")), start=1):
            content = _text(fact)
            if content:
                source_cards.append({"id": f"F{index}", "content": content, "fact_type": "事实", "status": "claimed"})
    if not source_cards:
        claims = ((case_info.get("case_intelligence") or {}).get("claims") or []) if isinstance(case_info.get("case_intelligence"), dict) else []
        for index, claim in enumerate(claims, start=1):
            if not isinstance(claim, dict):
                continue
            content = _text(claim.get("statement"))
            if content:
                source_cards.append({
                    "id": _text(claim.get("claim_id")) or f"F{index}",
                    "content": content,
                    "fact_type": _text(claim.get("claim_type")) or "事实",
                    "status": _text(claim.get("verification_status")) or "claimed",
                    "source_refs": claim.get("source_refs") or [],
                })

    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_text = _text(case_info.get("complete_story") or case_info.get("original_content") or case_info.get("rawText"))
    for index, item in enumerate(source_cards, start=1):
        content = _text(item.get("content"))
        if not content or content in seen:
            continue
        seen.add(content)
        cards.append({
            "id": _text(item.get("id") or item.get("fact_id") or item.get("claim_id")) or f"F{len(cards) + 1}",
            "content": content,
            "fact_type": _text(item.get("fact_type")) or "事实",
            "status": _text(item.get("status")) or "claimed",
            "source_refs": _source_refs(item, source_text, content),
        })
    return cards


def _build_story_world_payload(case_info: dict[str, Any], story_graph: dict[str, Any]) -> dict[str, Any]:
    """Worldview is a carrier for storage/rendering, not a business processor."""
    return {
        "schema_version": "story_world_v8_carrier",
        "role": "storage_metrics_rendering_only",
        "processing_policy": "business_logic_uses_complete_story_structured_facts_and_role_memories",
        "complete_story": story_graph.get("complete_story") or case_info.get("complete_story") or "",
        "facts": _fact_cards_from_case(case_info),
        "fact_cards": _fact_cards_from_case(case_info),
        "roles": [
            {
                "name": person.get("name"),
                "role_type": person.get("role_type") or person.get("role"),
                "status": person.get("status"),
                "role_memories": person.get("role_memories") if isinstance(person.get("role_memories"), list) else [],
                "knowledge_ledger": person.get("knowledge_ledger") if isinstance(person.get("knowledge_ledger"), list) else [],
            }
            for person in _items(case_info.get("persons"))
            if isinstance(person, dict) and _text(person.get("name"))
        ],
        "metrics": {
            "fact_count": len(_fact_cards_from_case(case_info)),
            "role_count": len([person for person in _items(case_info.get("persons")) if isinstance(person, dict) and _text(person.get("name"))]),
            "memory_count": sum(len(_items(person.get("role_memories"))) for person in _items(case_info.get("persons")) if isinstance(person, dict)),
        },
    }


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
    pipeline_started = time.perf_counter()
    stage_started = pipeline_started
    stage_timings_ms: dict[str, int] = {}

    def finish_stage(stage: str) -> None:
        nonlocal stage_started
        now = time.perf_counter()
        elapsed_ms = round((now - stage_started) * 1000)
        stage_timings_ms[stage] = elapsed_ms
        stage_started = now
        print(f"[case-pipeline-timing] job_id={job_id} stage={stage} elapsed_ms={elapsed_ms}")

    db = database.SessionLocal()
    try:
        job = db.query(models.CasePipelineJob).filter(models.CasePipelineJob.id == job_id).first()
        if not job or job.status == "cancelled":
            return
        request = json.loads(job.request_json or "{}")
    finally:
        db.close()

    try:
        source_mode = _text(request.get("source_mode")) or "plain_case"
        update_job(job_id, status="running", stage="cleaning", progress=10, status_message="正在清洗案件原文", started_at=datetime.utcnow(), error_message=None)
        text = str(request.get("source_text") or "").strip()
        if not text:
            raise ValueError("案件内容为空")

        compacted_source = compact_case_source(text)
        namespace = f"case-source:{job.input_hash}"
        finish_stage("source_compaction")

        update_job(job_id, stage="story", progress=25, status_message="正在生成完整案件剧情")
        story_trace = {"attempts": [], "engine": "agent-workflow-v2-flowchart"}
        story_metadata = story_trace.get("story_metadata") if isinstance(story_trace.get("story_metadata"), dict) else {}

        update_job(job_id, stage="facts", progress=45, status_message="正在解析事实、提取人物并生成角色记忆")
        case_info = parse_case_with_agent(text, workflow_id=f"case-pipeline-{job_id}", source_mode=source_mode)
        complete_story = str(case_info.get("complete_story") or compacted_source["training_text"])
        if story_metadata.get("case_name"):
            case_info["case_name"] = story_metadata["case_name"]
        if story_metadata.get("case_type"):
            case_info["case_type"] = story_metadata["case_type"]
        if story_metadata.get("case_background"):
            case_info["case_background"] = story_metadata["case_background"]
        if story_trace.get("error"):
            warnings = case_info.get("parse_warnings") if isinstance(case_info.get("parse_warnings"), list) else []
            warnings.append(f"完整剧情模型不可用，已使用清洗后的案件正文继续抽取：{story_trace['error']}")
            case_info["parse_warnings"] = list(dict.fromkeys(warnings))
        finish_stage("complete_story_generation")
        finish_stage("structured_facts_roles_memories")

        update_job(job_id, stage="roles", progress=58, status_message="正在核对新后端角色记忆与信息来源")
        case_info["persons"] = compact_role_memories(case_info.get("persons") or [])
        finish_stage("role_memory_validation")

        update_job(job_id, stage="world", progress=68, status_message="正在构建案件故事世界")
        case_info["complete_story"] = complete_story
        case_info["full_narrative"] = complete_story
        case_info["narrative_document"] = {
            "schema_version": 6,
            "format": "word",
            "content": complete_story,
            "role": "complete_case_story",
            "policy": "flowchart_step_c",
        }
        case_info["story_documents"] = {
            "narrative": {"title": "案件完整故事剧情", "format": "word", "content": complete_story}
        }
        case_info.pop("event_story", None)
        case_info.pop("case_reconstruction", None)
        story_graph = {"complete_story": complete_story}
        case_info["original_content"] = text
        case_info["rawText"] = text
        upsert_node(namespace, "excluded-appendix", "source_appendix", compacted_source["excluded_appendix"])
        case_info["source_compaction"] = {
            key: value for key, value in compacted_source.items()
            if key not in {"training_text", "excluded_appendix"}
        }
        original_chars = int(compacted_source.get("original_chars") or len(text))
        training_chars = int(compacted_source.get("training_chars") or len(compacted_source["training_text"]))
        import_quality = case_info.get("case_import_quality") if isinstance(case_info.get("case_import_quality"), dict) else {}
        story_quality = import_quality.get("story") if isinstance(import_quality.get("story"), dict) else {}
        case_info["story_material_audit"] = {
            "original_chars": original_chars,
            "training_chars": training_chars,
            "excluded_appendix_count": len(compacted_source.get("excluded_appendix") or []),
            "compaction_ratio": round(training_chars / max(original_chars, 1), 4),
            "large_document": original_chars >= int(os.getenv("CASE_LARGE_DOCUMENT_CHARS", "50000")),
            "possible_truncation": training_chars < original_chars * 0.65 and original_chars >= int(os.getenv("CASE_TRUNCATION_AUDIT_CHARS", "20000")),
            "complete_story_chars": len(complete_story),
            "complete_story_ratio": story_quality.get("compression_ratio"),
            "complete_story_sufficient": story_quality.get("sufficient", False),
            "complete_story_repaired": story_quality.get("repaired", False),
            "complete_story_fallback": story_quality.get("fallback", ""),
        }
        case_info["knowledge_namespace"] = namespace
        case_info["story_world"] = _build_story_world_payload(case_info, story_graph)
        case_info["knowledge_manifest"] = store_case_knowledge(namespace, case_info)
        finish_stage("story_world_carrier")
        parse_ai_workflow = case_info.get("parse_ai_workflow") or case_info.get("ai_workflow") or {}

        update_job(job_id, stage="scenes", progress=82, status_message="正在生成场景蓝图")
        scene_context = dict(case_info)
        scene_context["story_world"] = case_info.get("story_world") or {}
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
        scene_result = generate_scenes_with_agent(scene_context, workflow_id=f"case-pipeline-{job_id}-scenes")
        scenes = compile_scene_lifecycles(case_info, scene_result.get("scenes") or [])
        finish_stage("scene_blueprints_and_scripts")

        update_job(job_id, stage="validating", progress=92, status_message="正在检查角色边界和训练闭环")
        case_info["scene_generation_mode"] = scene_result.get("scene_generation_mode") or ""
        case_info["scene_generation_warning"] = scene_result.get("scene_generation_warning") or ""
        case_info["parse_ai_workflow"] = parse_ai_workflow
        case_info["scene_ai_workflow"] = scene_result.get("ai_workflow") or {}
        case_info["ai_workflows"] = [
            item for item in (parse_ai_workflow, scene_result.get("ai_workflow") or {})
            if isinstance(item, dict) and item
        ]
        derived = compile_case_scene_artifacts(case_info, scenes)
        scenes = derived["scenes"]
        quality_report = build_case_quality_report(case_info, scenes)
        finish_stage("boundary_validation")
        stage_timings_ms["total"] = round((time.perf_counter() - pipeline_started) * 1000)
        print(
            f"[case-pipeline-timing] job_id={job_id} stage=total "
            f"elapsed_ms={stage_timings_ms['total']}"
        )
        persisted_case_info = dict(case_info)
        persisted_case_info.pop("source_sections", None)
        if persisted_case_info.get("full_narrative") == persisted_case_info.get("complete_story"):
            persisted_case_info.pop("full_narrative", None)
        persisted_case_info["story_world"] = _build_story_world_payload(case_info, story_graph)
        result = {
            "case_info": {
                **persisted_case_info,
                "scene_generation_mode": scene_result.get("scene_generation_mode") or "",
                "scene_generation_warning": scene_result.get("scene_generation_warning") or "",
                "parse_ai_workflow": parse_ai_workflow,
                "scene_ai_workflow": scene_result.get("ai_workflow") or {},
                "ai_workflows": [
                    item for item in (parse_ai_workflow, scene_result.get("ai_workflow") or {})
                    if isinstance(item, dict) and item
                ],
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
            "pipeline_timings_ms": stage_timings_ms,
            "parse_ai_workflow": parse_ai_workflow,
            "scene_ai_workflow": scene_result.get("ai_workflow") or {},
            "ai_workflow": scene_result.get("ai_workflow") or {},
            "ai_workflows": [
                item for item in (parse_ai_workflow, scene_result.get("ai_workflow") or {})
                if isinstance(item, dict) and item
            ],
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
        total_elapsed_ms = round((time.perf_counter() - pipeline_started) * 1000)
        print(
            f"[case-pipeline-timing] job_id={job_id} stage=failed "
            f"elapsed_ms={total_elapsed_ms} error={str(exc)[:240]}"
        )
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
