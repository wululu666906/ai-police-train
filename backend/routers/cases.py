import json
import os
import re
import uuid
from collections import defaultdict
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import require_admin_user
from services.data_quality_service import build_data_quality_report, migrate_case_data_quality
from services.case_schema_service import (
    canonicalize_person_payload,
    migrate_structured_data_payload,
)
from services.document_extract_service import document_extract_service
from services.role_resolver import is_role_speakable
from services.training_view_service import ensure_scene_role_initial_state
from services.scene_role_service import audit_scene_roles, normalize_scene_roles
from services.scene_compact_service import build_scene_stages_from_compact, infer_training_focus
from services.stage_config_service import infer_scene_behavior_mode, normalize_stages
from services.case_knowledge_service import delete_case_from_knowledge, try_sync_case_to_knowledge
from services.case_intelligence_service import assess_source_quality, build_role_knowledge_view, normalize_case_intelligence
from services.training_compiler_service import build_observable_scoring_rules, build_training_tasks, compile_state_machine
from services.workflow_service import workflow_service
from services.case_pipeline_service import create_pipeline_job
from services.case_scene_contract_service import (
    build_case_quality_report,
    compile_case_scene_artifacts,
    unacknowledged_warnings,
)
from services.workflow_job_service import serialize_job
from services.case_knowledge_repository import bind_namespace
from services.object_storage_service import MEDIA_BUCKET, build_object_key, delete_media_assets, guess_content_type, object_storage, upsert_media_asset
from services.assessment_point_policy import (
    ASSESSMENT_POINTS_MAX_PER_SCENE,
    finalize_assessment_points,
    parse_points_for_scene_text,
)
from services.assessment_point_import_service import (
    apply_template_to_points,
    distribute_assessment_points_to_scenes,
    generate_assessment_points,
    list_builtin_templates,
    parse_text_to_assessment_points,
)
from services.ai_roles import list_ai_roles
from services.agent_case_service import generate_scenes_with_agent, parse_case_with_agent
from services.scene_bucket_service import BUCKET_LABELS, STANDARD_SCENE_NAMES

router = APIRouter(prefix="/cases", tags=["Cases"], dependencies=[Depends(require_admin_user)])


def _resolve_scene_stages(scene_data: dict, *, case_type: str = "", scene_name: str = "") -> list[dict]:
    name = str(scene_data.get("name") or scene_data.get("scene_name") or scene_name or "").strip()
    if scene_data.get("training_focus") or scene_data.get("assessment_points") is not None:
        compact = {
            "name": name,
            "training_focus": scene_data.get("training_focus"),
            "behavior_mode": scene_data.get("behavior_mode"),
            "difficulty": scene_data.get("difficulty"),
            "assessment_points": scene_data.get("assessment_points"),
            "stages": scene_data.get("stages"),
        }
        return build_scene_stages_from_compact(compact, case_type=case_type, scene_name=name)

    stages = scene_data.get("stages") or []
    if isinstance(stages, str):
        stages = _safe_json_loads(stages, [])
    return normalize_stages(stages, case_type=case_type, scene_name=name)


def _safe_json_loads(value, default):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _resolve_estimated_minutes(scene_data: dict) -> int | None:
    for key in ("estimated_minutes", "estimate_minutes", "duration_minutes", "training_minutes"):
        value = scene_data.get(key)
        if value in (None, ""):
            continue
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            continue
        return minutes if minutes > 0 else None
    return None


def _normalize_opening_config(value, role_by_name: dict[str, models.Role] | None = None) -> str:
    raw = _safe_json_loads(value, {})
    raw = raw if isinstance(raw, dict) else {}
    role_by_name = role_by_name or {}
    speaker_ids: list[int] = []
    for item in raw.get("speaker_role_ids") or []:
        try:
            role_id = int(item)
        except (TypeError, ValueError):
            continue
        if role_id > 0 and role_id not in speaker_ids:
            speaker_ids.append(role_id)
    for name in raw.get("speaker_names") or []:
        role = role_by_name.get(str(name or "").strip())
        if role and role.id not in speaker_ids:
            speaker_ids.append(role.id)

    preset_turns = []
    for item in raw.get("preset_turns") or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role_id = item.get("speaker_role_id")
        if not role_id and item.get("speaker_name") in role_by_name:
            role_id = role_by_name[item["speaker_name"]].id
        try:
            role_id = int(role_id) if role_id else None
        except (TypeError, ValueError):
            role_id = None
        preset_turns.append({"speaker_role_id": role_id, "content": content[:500]})

    config = {
        "schema_version": 1,
        "enabled": raw.get("enabled") is not False,
        "mode": "preset" if raw.get("mode") == "preset" else "dynamic",
        "speaker_role_ids": speaker_ids[:3],
        "director_note": str(raw.get("director_note") or "").strip()[:1000],
        "preset_turns": preset_turns[:9],
    }
    return json.dumps(config, ensure_ascii=False)


def _published_case_title(case_data: dict) -> str:
    wrapper = re.compile(r"^(第[一二三四五六七八九十百零\d]+[章节编]|目录|正文|裁判要旨|审理经过|案件材料|案情介绍|文书正文)$")

    def valid(value) -> str:
        lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
        return next((line[:100] for line in lines if not wrapper.fullmatch(line)), "")

    manual = valid(case_data.get("title"))
    if manual:
        return manual
    ai_title = valid(case_data.get("case_name"))
    if ai_title:
        return ai_title
    persons = [item for item in case_data.get("persons") or [] if isinstance(item, dict)]
    first_person = valid((persons[0] if persons else {}).get("name"))
    case_type = valid(case_data.get("case_type"))
    if first_person or case_type:
        return f"{first_person}{case_type or '警情'}案"[:100]
    filename = os.path.splitext(str(case_data.get("source_file_name") or ""))[0]
    return valid(filename) or "未命名案件"


@router.post("/pipeline/text")
def create_text_pipeline(payload: dict = Body(...)):
    source_text = str(payload.get("source_text") or payload.get("text") or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="案件内容不能为空")
    job = create_pipeline_job(
        source_text=source_text,
        source_mode=str(payload.get("source_mode") or "plain_case"),
        source_meta=payload.get("source_meta") if isinstance(payload.get("source_meta"), dict) else None,
        force_rebuild=bool(payload.get("force_rebuild", True)),
    )
    return serialize_job(job, include_result=job.status == "completed")


@router.post("/pipeline/file")
async def create_file_pipeline(
    file: UploadFile = File(...),
    source_mode: str = Form("transcript_file"),
    force_rebuild: bool = Form(True),
    db: Session = Depends(database.get_db),
):
    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in document_extract_service.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF、DOCX、TXT、MD 文件")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空，请重新选择文件")
    if len(file_bytes) > document_extract_service.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 20MB")
    try:
        extraction = document_extract_service.recognize_file(filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件读取失败：{exc}") from exc

    stored = object_storage.put_bytes(
        bucket=MEDIA_BUCKET,
        object_key=build_object_key("case-source-files", filename),
        data=file_bytes,
        content_type=guess_content_type(filename, file.content_type),
    )
    upsert_media_asset(
        db,
        owner_type="case_upload",
        owner_key=stored.object_key,
        asset_kind="source_file",
        stored=stored,
        original_filename=filename,
        content_type=guess_content_type(filename, file.content_type),
    )
    db.commit()
    source_meta = extraction.as_source_meta(name=filename, extension=extension, size=len(file_bytes))
    source_meta.update({
        "ocr_method": extraction.method,
        "ocr_engine": extraction.engine,
        "ocr_warnings": extraction.warnings,
        "ocr_metadata": extraction.metadata,
        "source_asset_key": stored.object_key,
    })
    job = create_pipeline_job(
        source_text=extraction.text,
        source_mode=source_mode or "transcript_file",
        source_meta=source_meta,
        force_rebuild=force_rebuild,
    )
    return serialize_job(job, include_result=job.status == "completed")


@router.get("/pipeline/{job_id}")
def get_pipeline_job(job_id: str, db: Session = Depends(database.get_db)):
    job = db.query(models.CasePipelineJob).filter(models.CasePipelineJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="未找到案件整理任务")
    return serialize_job(job, include_result=True)


def _materialize_scene_stages_for_response(scene: models.Scene, *, case_type: str = "") -> None:
    """Upgrade legacy assessment content when serving cases to the admin UI."""
    scene.stages = json.dumps(
        normalize_stages(
            _safe_json_loads(scene.stages, []),
            case_type=case_type,
            scene_name=str(scene.name or "").strip(),
        ),
        ensure_ascii=False,
    )


def _materialize_case_scenes_for_response(case: models.Case) -> None:
    case_type = str(case.case_type or "").strip()
    for scene in case.scenes or []:
        _materialize_scene_stages_for_response(scene, case_type=case_type)


def _materialize_case_persons_for_response(case: models.Case) -> None:
    structured = _safe_json_loads(case.structured_data, {})
    if not isinstance(structured, dict):
        structured = {}

    persons = structured.get("persons")
    if isinstance(persons, list) and persons:
        return

    roles = [
        role
        for role in sorted(case.roles or [], key=lambda item: item.id or 0)
        if str(role.name or "").strip()
    ]
    if not roles:
        return

    structured["persons"] = [_role_to_person_payload(role) for role in roles]
    structured, _ = migrate_structured_data_payload(structured)
    case.structured_data = json.dumps(structured, ensure_ascii=False)


def _materialize_case_for_response(case: models.Case) -> None:
    _materialize_case_scenes_for_response(case)
    _materialize_case_persons_for_response(case)


def _ensure_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _serialize_role_list(value):
    return json.dumps(_ensure_list(value), ensure_ascii=False)


def _serialize_person_meta(value: dict | None):
    return json.dumps(value or {}, ensure_ascii=False)


def _person_meta_fields():
    return (
        "behavior_archetype",
        "opening_preset",
        "police_attitude",
        "scene_behavior_mode",
        "current_goal",
        "core_concern",
        "relationship_pressure",
        "surface_stance",
        "pressure_response",
        "trigger_points",
        "calming_points",
        "emotion_level",
        "cooperation_level",
        "risk_level",
        "clarity_level",
        "init_emotion",
        "init_trust",
        "init_risk",
        "init_expression_clarity",
        "known_key_points",
        "withheld_key_points",
        "conflict_core",
        "acceptable_outcomes",
        "no_go_topics",
        "trigger_sources",
        "concerned_targets",
        "taboo_actions",
        "escalation_actions",
        "deescalation_conditions",
        "impairment_state",
        "self_image",
        "current_need",
        "authority_attitude",
        "stress_response",
        "protected_targets",
        "feared_people",
        "conflict_targets",
        "feared_consequences",
        "trigger_topics",
        "coping_patterns",
        "public_mask",
        "private_drive",
        "knowledge_ledger",
        "role_memories",
        "unresolved_claims",
        "response_constraints",
        "persona_contract_version",
        "persona_source",
        "persona_autofill",
        "soul_profile",
        "persona_generation",
        "narrative_context",
    )


def _extract_person_meta(payload: dict | None, base_meta: dict | None = None):
    payload = payload or {}
    base_meta = base_meta or {}
    # V2 metadata is intentionally limited to source-backed role memory.  Old
    # fields may still exist in the database for migration, but are ignored on
    # every new save so they cannot re-enter the active template.
    source = {}
    for key in (
        "name", "role_type", "status", "source_verification", "persona_source", "current_goal",
        "source_kind", "synthetic_type", "knowledge_scope", "answer_limit",
    ):
        value = payload.get(key) if key in payload else base_meta.get(key)
        if value not in (None, ""):
            source[key] = str(value).strip()
    for key in ("role_memories", "knowledge_ledger", "role_event_ledger", "unresolved_claims", "response_constraints", "source_refs", "narrative_context"):
        value = payload.get(key) if key in payload else base_meta.get(key)
        source[key] = _ensure_list(value)
    soul_profile = payload.get("soul_profile") if "soul_profile" in payload else base_meta.get("soul_profile")
    if isinstance(soul_profile, dict):
        source["soul_profile"] = soul_profile
    persona_generation = payload.get("persona_generation") if "persona_generation" in payload else base_meta.get("persona_generation")
    if isinstance(persona_generation, dict):
        source["persona_generation"] = persona_generation
    source["role_template_version"] = "source_memory_v2"
    source["persona_contract_version"] = "source_memory_v2"
    source["persona_autofill"] = False
    canonical_result, _ = canonicalize_person_payload(source)
    for key in (
        "behavior_archetype", "opening_preset", "scene_behavior_mode",
        "init_emotion", "init_trust", "init_risk", "init_expression_clarity",
        "emotion_level", "cooperation_level", "risk_level", "clarity_level",
    ):
        value = payload.get(key) if key in payload else base_meta.get(key)
        if value not in (None, ""):
            canonical_result[key] = value
    return canonical_result


def _get_case_person_meta(case: models.Case | None, role_name: str):
    structured = _safe_json_loads(case.structured_data if case else None, {})
    if not isinstance(structured, dict):
        return {}
    persons = structured.get("persons") or []
    if not isinstance(persons, list):
        return {}

    role_name = workflow_service._normalize_person_name(role_name)
    for person in persons:
        person_name = workflow_service._normalize_person_name((person or {}).get("name"))
        if person_name != role_name:
            continue
        return {field: (person or {}).get(field) for field in _person_meta_fields()}
    return {}


def _get_role_person_meta(role: models.Role | None):
    parsed = _safe_json_loads(getattr(role, "persona_meta", None), {})
    return parsed if isinstance(parsed, dict) else {}


def _role_to_person_payload(role: models.Role):
    meta = _get_role_person_meta(role)
    return {
        "name": role.name,
        "role": role.role_type or "相关人员",
        "role_type": role.role_type or "相关人员",
        "status": role.status or "正常",
        "role_memories": meta.get("role_memories") if isinstance(meta.get("role_memories"), list) else [],
        "knowledge_ledger": meta.get("knowledge_ledger") if isinstance(meta.get("knowledge_ledger"), list) else [],
        "unresolved_claims": meta.get("unresolved_claims") if isinstance(meta.get("unresolved_claims"), list) else [],
        "response_constraints": meta.get("response_constraints") if isinstance(meta.get("response_constraints"), list) else [],
        "source_verification": meta.get("source_verification") or "",
        "source_refs": meta.get("source_refs") if isinstance(meta.get("source_refs"), list) else [],
        "role_template_version": "source_memory_v2",
        "persona_contract_version": "source_memory_v2",
        "persona_autofill": False,
        "soul_profile": meta.get("soul_profile") if isinstance(meta.get("soul_profile"), dict) else {},
        "persona_generation": meta.get("persona_generation") if isinstance(meta.get("persona_generation"), dict) else {},
        "current_goal": meta.get("current_goal") or "",
        "init_emotion": role.init_emotion,
        "init_trust": role.init_trust,
        "init_risk": role.init_risk,
        "init_expression_clarity": role.init_expression_clarity,
    }


def _build_scene_role_map(scenes_data: list[dict] | None):
    mapping = {}
    for scene in scenes_data or []:
        if not isinstance(scene, dict):
            continue
        scene_name = str(scene.get("scene_name") or scene.get("name") or "").strip()
        if not scene_name:
            continue
        role_names = []
        seen = set()
        for item in scene.get("roles") or scene.get("role_names") or []:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            role_names.append(name)
        primary_role_name = str(scene.get("primary_role_name") or "").strip()
        mapping[scene_name] = {
            "role_names": role_names,
            "primary_role_name": primary_role_name or (role_names[0] if role_names else ""),
        }
    return mapping


def _standardize_case_structured_people(structured: dict) -> dict:
    payload = dict(structured or {})
    persons = workflow_service.standardize_person_records(payload.get("persons"))
    payload["persons"] = persons
    return payload


def _canonicalize_scene_role_payloads(scenes_data: list[dict] | None, persons: list[dict]) -> list[dict]:
    normalized_scenes: list[dict] = []
    for scene in scenes_data or []:
        if not isinstance(scene, dict):
            continue
        scene_payload = dict(scene)
        roles = scene_payload.get("roles") or scene_payload.get("role_names") or []
        canonical_roles = workflow_service.canonicalize_role_names(roles, persons)
        scene_payload["roles"] = canonical_roles
        scene_payload["role_names"] = canonical_roles
        primary_role_name = workflow_service.canonicalize_role_name(scene_payload.get("primary_role_name"), persons)
        if primary_role_name in canonical_roles:
            scene_payload["primary_role_name"] = primary_role_name
        elif canonical_roles:
            scene_payload["primary_role_name"] = canonical_roles[0]
        normalized_scenes.append(scene_payload)
    return normalized_scenes


def _sync_case_person(case: models.Case, role: models.Role, old_name: str | None = None, extra_meta: dict | None = None):
    structured = _safe_json_loads(case.structured_data, {})
    if not isinstance(structured, dict):
        structured = {}

    persons = structured.get("persons") or []
    if not isinstance(persons, list):
        persons = []

    new_person_payload = _role_to_person_payload(role)
    canonical_meta, _ = canonicalize_person_payload(extra_meta or {})
    new_person_payload.update(canonical_meta)
    replaced = False
    for index, person in enumerate(persons):
        person_name = str((person or {}).get("name") or "").strip()
        if person_name == role.name or (old_name and person_name == old_name):
            persons[index] = new_person_payload
            replaced = True
            break

    if not replaced:
        persons.append(new_person_payload)

    structured["persons"] = persons
    structured, _ = migrate_structured_data_payload(structured)
    case.structured_data = json.dumps(structured, ensure_ascii=False)


def _normalize_person_role_type(person: dict | None) -> str:
    person = person or {}
    explicit_role_type = str(person.get("role_type") or "").strip()
    if explicit_role_type:
        return explicit_role_type
    return workflow_service._guess_role_type(person.get("role"))


def _normalize_person_interaction_style(person: dict | None) -> str:
    person = person or {}
    return str(person.get("interaction_style") or "配合型").strip() or "配合型"


def _upsert_case_roles_from_structured_persons(db: Session, case: models.Case):
    structured = _safe_json_loads(case.structured_data, {})
    if not isinstance(structured, dict):
        return

    persons = structured.get("persons") or []
    if not isinstance(persons, list):
        return

    existing_roles = {
        str(role.name or "").strip(): role
        for role in db.query(models.Role).filter(models.Role.case_id == case.id).all()
        if str(role.name or "").strip()
    }

    # Track person_id counter for stable IDs across batches
    max_existing_id = 0
    for role in existing_roles.values():
        if role.person_id and role.person_id.startswith(f"P{case.id}_"):
            try:
                num = int(role.person_id.split("_")[1])
                max_existing_id = max(max_existing_id, num)
            except (ValueError, IndexError):
                pass

    changed = False
    person_id_counter = max_existing_id + 1
    for person in persons:
        if not isinstance(person, dict):
            continue
        person = workflow_service._clean_person(person)

        person_name = str(person.get("name") or "").strip()
        if not person_name:
            continue

        # Skip invalid person names (non-person tokens, place names, etc.)
        if not workflow_service._is_valid_person_name(person_name):
            continue

        role = existing_roles.get(person_name)
        role_type = _normalize_person_role_type(person)
        interaction_style = ""
        role_meta = _extract_person_meta(person)

        if role is None:
            # Generate a stable person_id for cross-scene tracking
            person_id = f"P{case.id}_{person_id_counter:04d}"
            person_id_counter += 1

            role = models.Role(
                case_id=case.id,
                name=person_name,
                person_id=person_id,
                role_type=role_type or "相关人员",
                interaction_style=interaction_style,
                personality="",
                speaking_style="",
                init_emotion=person.get("init_emotion", 50),
                init_trust=person.get("init_trust", 30),
                init_risk=person.get("init_risk", 50),
                init_expression_clarity=person.get("init_expression_clarity", 50),
                status=str(person.get("status") or "正常").strip(),
                hidden_truths=json.dumps(person.get("hidden_truths") or person.get("facts_hidden") or person.get("withheld_key_points") or [], ensure_ascii=False),
                knows_facts=json.dumps(person.get("knows_facts") or person.get("facts_known") or person.get("known_key_points") or [], ensure_ascii=False),
                does_not_know="[]",
                iq_level="",
                eq_level="",
                lying_ability="",
                weakness="",
                persona_meta=_serialize_person_meta(role_meta),
            )
            db.add(role)
            existing_roles[person_name] = role
            changed = True
            continue

        role.role_type = role_type or role.role_type or "相关人员"
        role.interaction_style = ""
        role.personality = ""
        role.speaking_style = ""
        role.init_emotion = person.get("init_emotion", role.init_emotion)
        role.init_trust = person.get("init_trust", role.init_trust)
        role.init_risk = person.get("init_risk", role.init_risk)
        role.init_expression_clarity = person.get("init_expression_clarity", role.init_expression_clarity)
        role.status = str(person.get("status") or role.status or "正常").strip()
        role.knows_facts = "[]"
        role.does_not_know = "[]"
        role.hidden_truths = "[]"
        role.iq_level = ""
        role.eq_level = ""
        role.lying_ability = ""
        role.weakness = ""
        role.persona_meta = _serialize_person_meta(role_meta)
        changed = True

    if changed:
        db.flush()


def _enforce_case_quality_gate(case_info: dict, scenes: list[dict], acknowledgements) -> dict:
    report = build_case_quality_report(case_info, scenes)
    if report["blocking_issues"]:
        raise HTTPException(
            status_code=422,
            detail={"code": "CASE_QUALITY_BLOCKED", "issues": report["blocking_issues"], "quality_report": report},
        )
    pending = unacknowledged_warnings(report, acknowledgements)
    if pending:
        raise HTTPException(
            status_code=422,
            detail={"code": "CASE_QUALITY_ACK_REQUIRED", "issues": pending, "quality_report": report},
        )
    return report


def _sync_role_compatibility_scene(db: Session, case_id: int) -> None:
    roles = db.query(models.Role).filter(models.Role.case_id == case_id).all()
    for role in roles:
        links = (
            db.query(models.SceneRole)
            .filter(models.SceneRole.role_id == role.id)
            .order_by(models.SceneRole.is_primary.desc(), models.SceneRole.scene_id.asc())
            .all()
        )
        role.scene_id = links[0].scene_id if links else None


def _compile_persisted_case_artifacts(db: Session, db_case: models.Case, structured: dict) -> dict:
    roles_by_id = {
        role.id: role for role in db.query(models.Role).filter(models.Role.case_id == db_case.id).all()
    }
    scene_rows = db.query(models.Scene).filter(models.Scene.case_id == db_case.id).order_by(models.Scene.id.asc()).all()
    scene_payloads = []
    for scene in scene_rows:
        links = (
            db.query(models.SceneRole)
            .filter(models.SceneRole.scene_id == scene.id)
            .order_by(models.SceneRole.id.asc())
            .all()
        )
        role_names = [roles_by_id[link.role_id].name for link in links if link.role_id in roles_by_id]
        primary = next((roles_by_id[link.role_id].name for link in links if link.is_primary and link.role_id in roles_by_id), "")
        scene_payloads.append({
            "id": scene.id,
            "scene_ref": f"db:{scene.id}",
            "scene_name": scene.name,
            "scene_description": scene.description,
            "difficulty": scene.difficulty,
            "dispatch_brief": scene.dispatch_brief,
            "first_impression": scene.first_impression,
            "stages": _safe_json_loads(scene.stages, []),
            "roles": role_names,
            "role_names": role_names,
            "primary_role_name": primary,
        })
    derived = compile_case_scene_artifacts(structured, scene_payloads)
    for key, value in derived.items():
        if key != "scenes":
            structured[key] = value
    structured["quality_report"] = build_case_quality_report(structured, derived["scenes"])
    return structured


def _remove_legacy_empty_roles_not_in_source(db: Session, case: models.Case, source_person_names: set[str]) -> list[str]:
    """Remove only empty legacy templates that a source rebuild has replaced."""
    removed_names = []
    for role in db.query(models.Role).filter(models.Role.case_id == case.id).all():
        role_name = str(role.name or "").strip()
        if not role_name or role_name in source_person_names:
            continue
        meta = _get_role_person_meta(role)
        if str(meta.get("role_template_version") or "").strip() == "source_memory_v2":
            continue
        if _ensure_list(meta.get("role_memories")) or _ensure_list(meta.get("knowledge_ledger")):
            continue
        db.query(models.SceneRole).filter(models.SceneRole.role_id == role.id).delete()
        db.delete(role)
        removed_names.append(role_name)
    return removed_names


def _remove_case_person(case: models.Case, role_name: str):
    structured = _safe_json_loads(case.structured_data, {})
    if not isinstance(structured, dict):
        return

    persons = structured.get("persons") or []
    if not isinstance(persons, list):
        persons = []

    structured["persons"] = [
        person
        for person in persons
        if str((person or {}).get("name") or "").strip() != str(role_name or "").strip()
    ]
    case.structured_data = json.dumps(structured, ensure_ascii=False)


def _delete_optional_table_rows(db: Session, table_name: str, column_name: str, values: list[int]) -> None:
    ids = [int(value) for value in values if int(value or 0) > 0]
    if not ids or not inspect(db.get_bind()).has_table(table_name):
        return
    statement = text(f'DELETE FROM "{table_name}" WHERE "{column_name}" IN :ids').bindparams(
        bindparam("ids", expanding=True)
    )
    db.execute(statement, {"ids": ids})


def _delete_case_dependencies(db: Session, case: models.Case) -> None:
    scene_ids = [scene.id for scene in case.scenes or [] if scene.id is not None]
    role_ids = [role.id for role in case.roles or [] if role.id is not None]

    if role_ids:
        db.query(models.Message).filter(models.Message.speaker_role_id.in_(role_ids)).update(
            {models.Message.speaker_role_id: None},
            synchronize_session=False,
        )
        db.query(models.SceneRole).filter(models.SceneRole.role_id.in_(role_ids)).delete(synchronize_session=False)

    if scene_ids:
        session_ids = [
            row.id
            for row in db.query(models.TrainingSession.id)
            .filter(models.TrainingSession.scene_id.in_(scene_ids))
            .all()
        ]
        if session_ids:
            artifact_ids = [
                row[0]
                for row in db.query(models.TrainingSessionArtifact.id)
                .filter(models.TrainingSessionArtifact.session_id.in_(session_ids))
                .all()
            ]
            for artifact_id in artifact_ids:
                delete_media_assets(db, owner_type="training_session_artifact", owner_key=artifact_id)
            _delete_optional_table_rows(db, "face_verification_sessions", "session_id", session_ids)
            _delete_optional_table_rows(db, "multimodal_events", "session_id", session_ids)
            _delete_optional_table_rows(db, "multimodal_session_metrics", "session_id", session_ids)
            db.query(models.AssignmentSubmission).filter(
                models.AssignmentSubmission.training_session_id.in_(session_ids)
            ).update({models.AssignmentSubmission.training_session_id: None}, synchronize_session=False)
            db.query(models.FaceVerificationEvent).filter(
                models.FaceVerificationEvent.session_id.in_(session_ids)
            ).update({models.FaceVerificationEvent.session_id: None}, synchronize_session=False)
            db.query(models.Message).filter(models.Message.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(models.TrainingSessionArtifact).filter(
                models.TrainingSessionArtifact.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(
                synchronize_session=False
            )

        db.query(models.TrainingAssignmentScene).filter(
            models.TrainingAssignmentScene.scene_id.in_(scene_ids)
        ).delete(synchronize_session=False)
        db.query(models.SceneRole).filter(models.SceneRole.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    db.query(models.AssignmentSubmission).filter(models.AssignmentSubmission.case_id == case.id).delete(
        synchronize_session=False
    )
    db.query(models.TrainingAssignmentCase).filter(models.TrainingAssignmentCase.case_id == case.id).delete(
        synchronize_session=False
    )
    db.query(models.TrainingAssignmentScene).filter(models.TrainingAssignmentScene.case_id == case.id).delete(
        synchronize_session=False
    )
    db.query(models.TrainingVideo).filter(models.TrainingVideo.case_id == case.id).update(
        {models.TrainingVideo.case_id: None},
        synchronize_session=False,
    )
    db.query(models.AIWorkflowRun).filter(models.AIWorkflowRun.case_id == case.id).update(
        {models.AIWorkflowRun.case_id: None},
        synchronize_session=False,
    )
    db.query(models.CaseStoryVersion).filter(models.CaseStoryVersion.case_id == case.id).update(
        {models.CaseStoryVersion.case_id: None},
        synchronize_session=False,
    )
    db.query(models.OpsIssueRecord).filter(models.OpsIssueRecord.case_id == case.id).update(
        {models.OpsIssueRecord.case_id: None},
        synchronize_session=False,
    )


def _apply_role_scene_links(
    db: Session,
    role: models.Role,
    scene_ids: list[int],
    primary_scene_id: int | None = None,
):
    db.query(models.SceneRole).filter(models.SceneRole.role_id == role.id).delete()

    unique_scene_ids = []
    seen_ids = set()
    for scene_id in scene_ids or []:
        try:
            normalized_id = int(scene_id)
        except (TypeError, ValueError):
            continue
        if normalized_id in seen_ids:
            continue
        seen_ids.add(normalized_id)
        unique_scene_ids.append(normalized_id)

    if not unique_scene_ids:
        role.scene_id = None
        return

    valid_scene_ids = {
        scene.id
        for scene in db.query(models.Scene)
        .filter(models.Scene.case_id == role.case_id, models.Scene.id.in_(unique_scene_ids))
        .all()
    }
    if len(valid_scene_ids) != len(unique_scene_ids):
        raise HTTPException(status_code=400, detail="存在不属于当前案件的场景，无法分配角色")

    if primary_scene_id is not None:
        try:
            primary_scene_id = int(primary_scene_id)
        except (TypeError, ValueError):
            primary_scene_id = None

    if primary_scene_id is not None and primary_scene_id not in valid_scene_ids:
        raise HTTPException(status_code=400, detail="主对话场景必须属于当前角色已分配的场景")
    if primary_scene_id is not None and not is_role_speakable(role):
        raise HTTPException(status_code=400, detail="死亡、昏迷或重伤无法交流角色不能设为主对话角色")

    role.scene_id = primary_scene_id or unique_scene_ids[0]
    for scene_id in unique_scene_ids:
        is_primary = primary_scene_id is not None and scene_id == primary_scene_id
        if is_primary:
            db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene_id).update({"is_primary": False})
        db.add(models.SceneRole(scene_id=scene_id, role_id=role.id, is_primary=is_primary))


@router.get("/", response_model=List[schemas.Case])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    cases = db.query(models.Case).offset(skip).limit(limit).all()
    for case in cases:
        _materialize_case_for_response(case)
    return cases


@router.get("/all/roles")
def read_all_roles(db: Session = Depends(database.get_db)):
    roles = db.query(models.Role).order_by(models.Role.id.asc()).all()
    if not roles:
        return []

    role_ids = [role.id for role in roles]
    case_ids = sorted({role.case_id for role in roles if role.case_id is not None})

    scene_links_by_role_id: dict[int, list[models.SceneRole]] = defaultdict(list)
    for row in db.query(models.SceneRole).filter(models.SceneRole.role_id.in_(role_ids)).all():
        scene_links_by_role_id[row.role_id].append(row)

    case_meta_by_case_id: dict[int, dict[str, dict]] = {}
    case_title_by_case_id: dict[int, str] = {}
    if case_ids:
        db_cases = db.query(models.Case).filter(models.Case.id.in_(case_ids)).all()
        for db_case in db_cases:
            case_title_by_case_id[db_case.id] = db_case.title or "公共角色模板"
            structured = _safe_json_loads(db_case.structured_data, {})
            persons = structured.get("persons") if isinstance(structured, dict) else []
            if not isinstance(persons, list):
                persons = []
            case_meta_by_case_id[db_case.id] = {
                str((person or {}).get("name") or "").strip(): {
                    field: (person or {}).get(field) for field in _person_meta_fields()
                }
                for person in persons
                if str((person or {}).get("name") or "").strip()
            }

    result = []
    for role in roles:
        scene_links = scene_links_by_role_id.get(role.id, [])
        case_meta = case_meta_by_case_id.get(role.case_id or -1, {}).get(role.name, {})
        person_meta = _extract_person_meta({}, case_meta) if role.case_id else _get_role_person_meta(role)
        base_payload = {
            "id": role.id,
            "name": role.name,
            "role_type": role.role_type,
            "interaction_style": getattr(role, "interaction_style", None) or "配合型",
            "personality": role.personality,
            "speaking_style": role.speaking_style,
            "init_emotion": role.init_emotion,
            "init_trust": role.init_trust,
            "init_risk": role.init_risk,
            "init_expression_clarity": role.init_expression_clarity,
            "status": role.status,
            "iq_level": role.iq_level,
            "eq_level": role.eq_level,
            "lying_ability": role.lying_ability,
            "weakness": role.weakness,
            "knows_facts": _ensure_list(role.knows_facts),
            "does_not_know": _ensure_list(role.does_not_know),
            "hidden_truths": _ensure_list(role.hidden_truths),
            "case_id": role.case_id,
            "case_title": case_title_by_case_id.get(role.case_id or -1, "公共角色模板"),
            "scene_ids": [row.scene_id for row in scene_links],
            "primary_scene_id": next((row.scene_id for row in scene_links if row.is_primary), None),
            "is_public": role.case_id is None,
        }
        result.append({**person_meta, **base_payload})
    return result


def _case_background_preview(case: models.Case, limit: int = 300) -> str:
    """Return list-safe background text without sending a whole case payload."""
    structured = _safe_json_loads(case.structured_data, {})
    candidate = (
        case.background
        or structured.get("case_background")
        or structured.get("transcript_summary")
        or case.original_content
        or ""
    )
    return re.sub(r"\s+", " ", str(candidate)).strip()[:limit]


def _serialize_admin_role(db: Session, role: models.Role) -> dict:
    scene_links = db.query(models.SceneRole).filter(models.SceneRole.role_id == role.id).all()
    case_title = "公共角色模板"
    case_meta = {}
    if role.case_id is not None:
        db_case = db.query(models.Case).filter(models.Case.id == role.case_id).first()
        if db_case:
            case_title = db_case.title or "未命名案件"
            structured = _safe_json_loads(db_case.structured_data, {})
            persons = structured.get("persons") if isinstance(structured, dict) else []
            if isinstance(persons, list):
                person = next(
                    (
                        item
                        for item in persons
                        if str((item or {}).get("name") or "").strip() == role.name
                    ),
                    None,
                )
                case_meta = _extract_person_meta({}, person or {})

    person_meta = case_meta if role.case_id else _get_role_person_meta(role)
    base_payload = {
        "id": role.id,
        "name": role.name,
        "role_type": role.role_type,
        "interaction_style": getattr(role, "interaction_style", None) or "配合型",
        "personality": role.personality,
        "speaking_style": role.speaking_style,
        "init_emotion": role.init_emotion,
        "init_trust": role.init_trust,
        "init_risk": role.init_risk,
        "init_expression_clarity": role.init_expression_clarity,
        "status": role.status,
        "iq_level": role.iq_level,
        "eq_level": role.eq_level,
        "lying_ability": role.lying_ability,
        "weakness": role.weakness,
        "knows_facts": _ensure_list(role.knows_facts),
        "does_not_know": _ensure_list(role.does_not_know),
        "hidden_truths": _ensure_list(role.hidden_truths),
        "case_id": role.case_id,
        "case_title": case_title,
        "scene_ids": [row.scene_id for row in scene_links],
        "primary_scene_id": next((row.scene_id for row in scene_links if row.is_primary), None),
        "is_public": role.case_id is None,
    }
    return {**person_meta, **base_payload}


@router.get("/role-case-options")
def read_role_case_options(db: Session = Depends(database.get_db)):
    cases = db.query(models.Case).order_by(models.Case.created_at.desc()).all()
    return [
        {
            "id": case.id,
            "title": case.title,
            "case_type": case.case_type,
            "background": _case_background_preview(case),
            "scenes": [
                {
                    "id": scene.id,
                    "name": scene.name,
                    "behavior_mode": infer_scene_behavior_mode(scene.name, case.case_type or "", scene.stages),
                    "training_focus": infer_training_focus(
                        scene.name or "",
                        behavior_mode=infer_scene_behavior_mode(scene.name, case.case_type or "", scene.stages),
                        stages=_safe_json_loads(scene.stages, []),
                    ),
                }
                for scene in sorted(case.scenes or [], key=lambda item: item.id)
            ],
        }
        for case in cases
    ]


@router.get("/roles/{role_id}")
def read_role(role_id: int, db: Session = Depends(database.get_db)):
    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _serialize_admin_role(db, role)


@router.post("/roles")
def create_role(payload: dict = Body(...), db: Session = Depends(database.get_db)):
    case_id = payload.get("case_id")
    raw_role_name = str(payload.get("name") or "").strip()
    role_name = workflow_service._normalize_person_name(raw_role_name)
    if case_id is None and raw_role_name:
        role_name = raw_role_name
    if not role_name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")
    if case_id is not None and not workflow_service._is_valid_person_name(role_name):
        raise HTTPException(status_code=400, detail="角色名称必须是明确人物姓名，不能使用地名、身份称谓或案情词汇")

    scene_ids = payload.get("scene_ids") or []
    primary_scene_id = payload.get("primary_scene_id")

    db_case = None
    if case_id is not None:
        db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
        if not db_case:
            raise HTTPException(status_code=404, detail="目标案件不存在")

    duplicate_query = db.query(models.Role).filter(models.Role.name == role_name)
    if db_case is None:
        duplicate_query = duplicate_query.filter(models.Role.case_id.is_(None))
    else:
        duplicate_query = duplicate_query.filter(models.Role.case_id == db_case.id)
    if duplicate_query.first():
        raise HTTPException(status_code=400, detail="同一范围内已存在同名角色")

    public_role = db_case is None
    public_meta, _ = canonicalize_person_payload(payload) if public_role else ({}, [])
    db_role = models.Role(
        case_id=db_case.id if db_case else None,
        name=role_name,
        role_type=payload.get("role_type") or "相关人员",
        interaction_style=(payload.get("interaction_style") or "配合型") if public_role else "",
        personality=(payload.get("personality") or "") if public_role else "",
        speaking_style=(payload.get("speaking_style") or "") if public_role else "",
        init_emotion=payload.get("init_emotion", 50),
        init_trust=payload.get("init_trust", 30),
        init_risk=payload.get("init_risk", 50),
        init_expression_clarity=payload.get("init_expression_clarity", 50),
        status=payload.get("status") or "正常",
        iq_level=(payload.get("iq_level") or "") if public_role else "",
        eq_level=(payload.get("eq_level") or "") if public_role else "",
        lying_ability=(payload.get("lying_ability") or "") if public_role else "",
        weakness=(payload.get("weakness") or "") if public_role else "",
        knows_facts=_serialize_role_list(payload.get("knows_facts")) if public_role else "[]",
        does_not_know=_serialize_role_list(payload.get("does_not_know")) if public_role else "[]",
        hidden_truths=_serialize_role_list(payload.get("hidden_truths")) if public_role else "[]",
        persona_meta=_serialize_person_meta(public_meta if public_role else _extract_person_meta(payload)),
    )
    db.add(db_role)
    db.flush()

    if db_case:
        _sync_case_person(db_case, db_role, extra_meta=_extract_person_meta(payload))
        _apply_role_scene_links(db, db_role, scene_ids=scene_ids, primary_scene_id=primary_scene_id)

    db.commit()
    if db_case:
        db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
    return {"message": "角色创建成功", "id": db_role.id}


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: dict = Body(...), db: Session = Depends(database.get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="角色不存在")

    old_name = db_role.name
    raw_new_name = str(payload.get("name") or db_role.name or "").strip()
    new_name = workflow_service._normalize_person_name(raw_new_name)
    if db_role.case_id is None and raw_new_name:
        new_name = raw_new_name
    if not new_name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")
    if db_role.case_id is not None and not workflow_service._is_valid_person_name(new_name):
        raise HTTPException(status_code=400, detail="角色名称必须是明确人物姓名，不能使用地名、身份称谓或案情词汇")

    duplicate_query = db.query(models.Role).filter(models.Role.id != role_id, models.Role.name == new_name)
    if db_role.case_id is None:
        duplicate_query = duplicate_query.filter(models.Role.case_id.is_(None))
    else:
        duplicate_query = duplicate_query.filter(models.Role.case_id == db_role.case_id)
    if duplicate_query.first():
        raise HTTPException(status_code=400, detail="同一范围内已存在同名角色")

    db_role.name = new_name
    db_role.role_type = payload.get("role_type") or db_role.role_type
    public_role = db_role.case_id is None
    db_role.interaction_style = (payload.get("interaction_style") or db_role.interaction_style or "配合型") if public_role else ""
    db_role.personality = (payload.get("personality") or db_role.personality or "") if public_role else ""
    db_role.speaking_style = (payload.get("speaking_style") or db_role.speaking_style or "") if public_role else ""
    db_role.init_emotion = payload.get("init_emotion", db_role.init_emotion)
    db_role.init_trust = payload.get("init_trust", db_role.init_trust)
    db_role.init_risk = payload.get("init_risk", db_role.init_risk)
    db_role.init_expression_clarity = payload.get("init_expression_clarity", db_role.init_expression_clarity)
    db_role.status = payload.get("status") or db_role.status
    db_role.iq_level = (payload.get("iq_level") or db_role.iq_level or "") if public_role else ""
    db_role.eq_level = (payload.get("eq_level") or db_role.eq_level or "") if public_role else ""
    db_role.lying_ability = (payload.get("lying_ability") or db_role.lying_ability or "") if public_role else ""
    db_role.weakness = (payload.get("weakness") or db_role.weakness or "") if public_role else ""
    db_role.knows_facts = _serialize_role_list(payload.get("knows_facts")) if public_role else "[]"
    db_role.does_not_know = _serialize_role_list(payload.get("does_not_know")) if public_role else "[]"
    db_role.hidden_truths = _serialize_role_list(payload.get("hidden_truths")) if public_role else "[]"

    if db_role.case_id:
        db_case = db.query(models.Case).filter(models.Case.id == db_role.case_id).first()
        if db_case:
            existing_meta = _get_case_person_meta(db_case, old_name) or _get_case_person_meta(db_case, new_name)
            _sync_case_person(db_case, db_role, old_name=old_name, extra_meta=_extract_person_meta(payload, existing_meta))
        _apply_role_scene_links(
            db,
            db_role,
            scene_ids=payload.get("scene_ids") or [],
            primary_scene_id=payload.get("primary_scene_id"),
        )
    else:
        existing_meta = _get_role_person_meta(db_role)
        public_payload = {**existing_meta, **payload}
        public_meta, _ = canonicalize_person_payload(public_payload)
        db_role.persona_meta = _serialize_person_meta(public_meta)

    db.commit()
    if db_role.case_id:
        db.refresh(db_role)
        db_case = db.query(models.Case).filter(models.Case.id == db_role.case_id).first()
        if db_case:
            try_sync_case_to_knowledge(db_case)
    return {"message": "角色更新成功"}


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(database.get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="角色不存在")

    case_id = db_role.case_id
    if db_role.case_id:
        db_case = db.query(models.Case).filter(models.Case.id == db_role.case_id).first()
        if db_case:
            _remove_case_person(db_case, db_role.name)

    db.query(models.SceneRole).filter(models.SceneRole.role_id == db_role.id).delete()
    db.delete(db_role)
    db.commit()
    if case_id:
        db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
        if db_case:
            try_sync_case_to_knowledge(db_case)
    return {"message": "角色删除成功"}


@router.post("/parse")
def parse_case(payload: dict = Body(...)):
    text = payload.get("text")
    source_mode = payload.get("source_mode") or "plain_case"
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    try:
        return parse_case_with_agent(text, workflow_id=f"case-parse-{uuid.uuid4().hex}", source_mode=source_mode)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI parsing failed: {exc}") from exc


@router.post("/parse-file")
async def parse_case_file(
    file: UploadFile = File(...),
    source_mode: str = Form("transcript_file"),
    db: Session = Depends(database.get_db),
):
    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in document_extract_service.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF、DOCX、TXT、MD 文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空，请重新选择文件")
    if len(file_bytes) > document_extract_service.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 20MB")

    try:
        extraction = document_extract_service.recognize_file(filename, file_bytes)
        extracted_text = extraction.text
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {exc}") from exc

    try:
        result = parse_case_with_agent(extracted_text, workflow_id=f"case-file-{uuid.uuid4().hex}", source_mode=source_mode)
        stored = object_storage.put_bytes(
            bucket=MEDIA_BUCKET,
            object_key=build_object_key("case-source-files", filename),
            data=file_bytes,
            content_type=guess_content_type(filename, file.content_type),
        )
        asset = upsert_media_asset(
            db,
            owner_type="case_upload",
            owner_key=stored.object_key,
            asset_kind="source_file",
            stored=stored,
            original_filename=filename,
            content_type=guess_content_type(filename, file.content_type),
        )
        db.commit()
        result["ocr_method"] = extraction.method
        result["ocr_engine"] = extraction.engine
        result["ocr_warnings"] = extraction.warnings
        result["ocr_metadata"] = extraction.metadata
        result["extracted_text_full"] = extracted_text
        result["extracted_text_preview"] = extraction.preview
        result["source_asset_id"] = asset.id
        result["source_asset_key"] = asset.object_key
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI file parsing failed: {exc}") from exc



@router.get("/assessment-point-templates")
def get_assessment_point_templates():
    return {"templates": list_builtin_templates()}


@router.post("/assessment-points/parse-text")
def parse_assessment_points_text(payload: dict = Body(...)):
    text = str(payload.get("text") or payload.get("source_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    case_type = str(payload.get("case_type") or "").strip()
    scene_name = str(payload.get("scene_name") or "").strip()
    scene_index = int(payload.get("scene_index") or 0)
    scene_count = max(1, int(payload.get("scene_count") or 1))
    if scene_name:
        points, warnings = parse_points_for_scene_text(
            text,
            scene_name=scene_name,
            scene_index=scene_index,
            scene_count=scene_count,
            case_type=case_type,
        )
    else:
        raw = parse_text_to_assessment_points(text)
        points, warnings = finalize_assessment_points(raw, case_type=case_type, scene_name=scene_name)
    return {
        "points": points,
        "count": len(points),
        "mode": "replace",
        "max_per_scene": ASSESSMENT_POINTS_MAX_PER_SCENE,
        "warnings": warnings,
        "message": f"已解析 {len(points)} 条考察点",
    }


@router.post("/assessment-points/parse-file")
async def parse_assessment_points_file(
    file: UploadFile = File(...),
    case_type: str = Form(""),
    scene_name: str = Form(""),
    scene_index: int = Form(0),
    scene_count: int = Form(1),
    db: Session = Depends(database.get_db),
):
    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in document_extract_service.ALLOWED_EXTENSIONS and extension not in {".txt", ".json"}:
        raise HTTPException(status_code=400, detail="支持 TXT、JSON、MD、PDF、DOCX")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(file_bytes) > document_extract_service.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过 20MB")

    if extension in {".txt", ".json"}:
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("gbk", errors="ignore")
    else:
        try:
            extracted_text = document_extract_service.extract_text(filename, file_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    clean_scene_name = scene_name.strip()
    clean_case_type = case_type.strip()
    if clean_scene_name:
        points, warnings = parse_points_for_scene_text(
            extracted_text,
            scene_name=clean_scene_name,
            scene_index=scene_index,
            scene_count=max(1, scene_count),
            case_type=clean_case_type,
        )
    else:
        raw = parse_text_to_assessment_points(extracted_text)
        points, warnings = finalize_assessment_points(raw, case_type=clean_case_type, scene_name=clean_scene_name)
    stored = object_storage.put_bytes(
        bucket=MEDIA_BUCKET,
        object_key=build_object_key("case-source-files", filename),
        data=file_bytes,
        content_type=guess_content_type(filename, file.content_type),
    )
    asset = upsert_media_asset(
        db,
        owner_type="case_upload",
        owner_key=stored.object_key,
        asset_kind="source_file",
        stored=stored,
        original_filename=filename,
        content_type=guess_content_type(filename, file.content_type),
    )
    db.commit()
    return {
        "points": points,
        "count": len(points),
        "extracted_chars": len(extracted_text),
        "extracted_text": extracted_text[:8000],
        "filename": filename,
        "source_asset_id": asset.id,
        "source_asset_key": asset.object_key,
        "mode": "replace",
        "max_per_scene": ASSESSMENT_POINTS_MAX_PER_SCENE,
        "warnings": warnings,
        "message": f"已从「{filename}」解析 {len(points)} 条考察点",
    }


@router.get("/ai-roles")
def get_ai_roles_catalog():
    return {"roles": list_ai_roles()}



@router.get("/assessment-points/scene-naming-rules")
def get_assessment_scene_naming_rules():
    return {
        "standard_names": STANDARD_SCENE_NAMES,
        "bucket_labels": BUCKET_LABELS,
        "naming_hint": "场景名须含关键词：接警/现场/询问（或接处警、初查、讯问等），系统才能自动分派考察点。",
    }


@router.post("/assessment-points/distribute")
def distribute_assessment_points_api(payload: dict = Body(...)):
    case_info = payload.get("case_info") if isinstance(payload.get("case_info"), dict) else {}
    scenes = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
    if not scenes:
        raise HTTPException(status_code=400, detail="scenes 不能为空")

    try:
        result = distribute_assessment_points_to_scenes(
            case_info,
            scenes,
            source_text=str(payload.get("source_text") or "").strip(),
            extra_hint=str(payload.get("extra_hint") or "").strip(),
            use_llm=bool(payload.get("use_llm", True)),
            rename_scenes=bool(payload.get("rename_scenes", True)),
            reference_text=str(payload.get("reference_text") or "").strip(),
        )
        result["officer_role"] = "考察点生成"
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"分场景考察点生成失败: {exc}") from exc


@router.post("/assessment-points/generate")
def generate_assessment_points_api(payload: dict = Body(...)):
    case_info = payload.get("case_info") if isinstance(payload.get("case_info"), dict) else {}
    scene_info = payload.get("scene_info") if isinstance(payload.get("scene_info"), dict) else {}
    if not case_info and not scene_info:
        raise HTTPException(status_code=400, detail="case_info 或 scene_info 至少提供一项")

    try:
        return generate_assessment_points(
            case_info,
            scene_info,
            source_text=str(payload.get("source_text") or "").strip(),
            template_key=str(payload.get("template_key") or "").strip(),
            extra_hint=str(payload.get("extra_hint") or "").strip(),
            use_llm=bool(payload.get("use_llm", True)),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"考察点生成失败: {exc}") from exc



@router.post("/generate-scenes")
def generate_scenes(payload: dict = Body(...)):
    case_info = payload.get("case_info")
    if not case_info:
        raise HTTPException(status_code=400, detail="Case info is required")
    scene_generation_strategy = payload.get("scene_generation_strategy") or "case_driven"
    try:
        return generate_scenes_with_agent(case_info, workflow_id=f"scene-build-{uuid.uuid4().hex}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI scene generation failed: {exc}") from exc


@router.get("/scene-role-audit")
def get_scene_role_audit(case_id: int | None = None, db: Session = Depends(database.get_db)):
    return audit_scene_roles(db, case_id=case_id)


@router.get("/data-quality-report")
def get_data_quality_report(db: Session = Depends(database.get_db)):
    return build_data_quality_report(db)


@router.get("/{case_id}/intelligence-review")
def get_case_intelligence_review(case_id: int, db: Session = Depends(database.get_db)):
    """Admin review payload for provenance, role boundaries and compiled tasks."""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="案件不存在")
    structured = _safe_json_loads(db_case.structured_data, {})
    intelligence = normalize_case_intelligence(structured)
    scenes = [
        {"name": scene.name, "description": scene.description, "stages": _resolve_scene_stages({"stages": scene.stages}, case_type=db_case.case_type or "", scene_name=scene.name or "")}
        for scene in db_case.scenes or []
    ]
    role_views = []
    for role in db_case.roles or []:
        meta = _safe_json_loads(role.persona_meta, {})
        role_views.append(build_role_knowledge_view(
            structured,
            role_name=role.name or "相关人员",
            role_payload={
                **(meta if isinstance(meta, dict) else {}),
                "knows_facts": _safe_json_loads(role.knows_facts, []),
                "hidden_truths": _safe_json_loads(role.hidden_truths, []),
                "does_not_know": _safe_json_loads(role.does_not_know, []),
            },
        ))
    tasks = build_training_tasks({**structured, "case_intelligence": intelligence}, scenes)
    return {
        "case_id": case_id,
        "case_intelligence": intelligence,
        "source_quality": structured.get("source_quality") or assess_source_quality(db_case.original_content or db_case.background or ""),
        "role_knowledge_views": role_views,
        "training_tasks": tasks,
        "state_machine": compile_state_machine(tasks),
        "observable_scoring_rules": build_observable_scoring_rules(tasks),
    }


@router.post("/{case_id}/intelligence-migrate")
def migrate_case_intelligence(case_id: int, payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    """Non-destructive per-case migration; preview unless apply=true is explicit."""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="案件不存在")
    current = _safe_json_loads(db_case.structured_data, {})
    migrated, warnings = migrate_structured_data_payload(current)
    changed = migrated != current
    if bool(payload.get("apply")) and changed:
        db_case.structured_data = json.dumps(migrated, ensure_ascii=False)
        db.commit()
    return {"case_id": case_id, "changed": changed, "applied": bool(payload.get("apply")) and changed, "warnings": warnings, "preview": migrated}


@router.post("/intelligence-migrate-batch")
def migrate_case_intelligence_batch(payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    """Batch migration with dry-run by default; avoids implicit historical rewrites."""
    limit = max(1, min(int(payload.get("limit") or 100), 500))
    apply = bool(payload.get("apply"))
    rows = db.query(models.Case).order_by(models.Case.id.asc()).limit(limit).all()
    changed_ids: list[int] = []
    warnings_by_case: dict[int, list[str]] = {}
    for db_case in rows:
        current = _safe_json_loads(db_case.structured_data, {})
        migrated, warnings = migrate_structured_data_payload(current)
        if warnings:
            warnings_by_case[db_case.id] = warnings
        if migrated != current:
            changed_ids.append(db_case.id)
            if apply:
                db_case.structured_data = json.dumps(migrated, ensure_ascii=False)
    if apply and changed_ids:
        db.commit()
        for case_id in changed_ids:
            db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
            if db_case:
                try_sync_case_to_knowledge(db_case)
    return {
        "scanned": len(rows),
        "changed_count": len(changed_ids),
        "changed_case_ids": changed_ids,
        "applied": apply,
        "warnings_by_case": warnings_by_case,
    }


@router.get("/intelligence-rollout-metrics")
def get_case_intelligence_rollout_metrics(db: Session = Depends(database.get_db)):
    """Read-only rollout metrics for deciding whether v2 can become default."""
    rows = db.query(models.Case).all()
    metrics = {
        "total_cases": len(rows),
        "narrative_document_cases": 0,
        "intelligence_cases": 0,
        "role_ledger_cases": 0,
        "compiled_training_cases": 0,
        "source_quality": {"high": 0, "medium": 0, "low": 0},
    }
    for db_case in rows:
        structured = _safe_json_loads(db_case.structured_data, {})
        if isinstance(structured.get("narrative_document"), dict) and structured["narrative_document"].get("content"):
            metrics["narrative_document_cases"] += 1
        intelligence = structured.get("case_intelligence")
        if isinstance(intelligence, dict) and intelligence.get("schema_version") == 2:
            metrics["intelligence_cases"] += 1
        if any(build_role_knowledge_view(structured, role_name=role.name or "相关人员").get("ledger") for role in db_case.roles or []):
            metrics["role_ledger_cases"] += 1
        if structured.get("training_tasks") or structured.get("observable_scoring_rules"):
            metrics["compiled_training_cases"] += 1
        quality = structured.get("source_quality") or assess_source_quality(db_case.original_content or db_case.background or "")
        grade = str(quality.get("grade") or "low")
        metrics["source_quality"][grade if grade in metrics["source_quality"] else "low"] += 1
    total = metrics["total_cases"] or 1
    metrics["coverage"] = {
        key: round(metrics[key] / total, 4)
        for key in ("narrative_document_cases", "intelligence_cases", "role_ledger_cases", "compiled_training_cases")
    }
    workflow_runs = db.query(models.AIWorkflowRun).order_by(models.AIWorkflowRun.id.desc()).limit(500).all()
    durations: list[int] = []
    fallback_count = 0
    failed_count = 0
    switched_count = 0
    for run in workflow_runs:
        fallback_count += int(bool(run.used_rule_fallback))
        failed_count += int(run.status in {"failed", "fallback"})
        switched_count += int(bool(run.switched_provider))
        trace = _safe_json_loads(run.trace_json, {})
        for attempt in trace.get("attempts") or []:
            if isinstance(attempt, dict) and isinstance(attempt.get("duration_ms"), (int, float)):
                durations.append(int(attempt["duration_ms"]))
    run_total = len(workflow_runs) or 1
    metrics["workflow_quality"] = {
        "sample_size": len(workflow_runs),
        "rule_fallback_rate": round(fallback_count / run_total, 4),
        "failed_or_fallback_rate": round(failed_count / run_total, 4),
        "provider_switch_rate": round(switched_count / run_total, 4),
        "average_attempt_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "p95_attempt_duration_ms": sorted(durations)[max(0, int(len(durations) * 0.95) - 1)] if durations else None,
    }
    return metrics


@router.post("/data-quality-repair")
def repair_data_quality(payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    case_id = payload.get("case_id")
    repair_result = migrate_case_data_quality(
        db,
        case_id=case_id,
        apply=str(payload.get("mode") or "dry_run").strip().lower() == "apply",
        backup_dir=payload.get("backup_dir"),
    )
    report = build_data_quality_report(db)
    return {
        **repair_result,
        "report": report,
    }


@router.post("/scene-role-repair")
def repair_scene_roles(payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    case_id = payload.get("case_id")
    repair_result = normalize_scene_roles(db, case_id=case_id)
    audit_result = audit_scene_roles(db, case_id=case_id)
    return {
        **repair_result,
        "audit": audit_result,
    }


@router.post("/full-create", response_model=schemas.Case)
def full_create_case(payload: dict = Body(...), db: Session = Depends(database.get_db)):
    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []
    acknowledgements = payload.get("quality_acknowledgements") or []

    try:
        case_title = _published_case_title(case_data)
        original_content = case_data.get("original_content") or case_data.get("rawText") or ""
        background = case_data.get("background") or case_data.get("case_background") or "暂无案件背景"
        normalized_case_type = workflow_service.normalize_case_type(
            text=original_content,
            ai_case_type=case_data.get("case_type") or ""
        )

        standardized_persons = workflow_service.standardize_person_records(case_data.get("persons") or [])
        case_data = {**case_data, "persons": standardized_persons}
        scenes_data = _canonicalize_scene_role_payloads(scenes_data, standardized_persons)
        derived = compile_case_scene_artifacts(case_data, scenes_data)
        scenes_data = derived["scenes"]
        quality_report = _enforce_case_quality_gate(case_data, scenes_data, acknowledgements)

        structured_data_to_save = {
            "fact_sheet": case_data.get("fact_sheet", {}),
            "full_narrative": case_data.get("full_narrative", ""),
            "criminal_process": case_data.get("criminal_process", ""),
            "rawText": original_content,
            "original_content": original_content,
            "source_mode": case_data.get("source_mode"),
            "source_file_name": case_data.get("source_file_name"),
            "source_file_type": case_data.get("source_file_type"),
            "source_file_size": case_data.get("source_file_size"),
            "extracted_text_preview": case_data.get("extracted_text_preview", ""),
            "transcript_summary": case_data.get("transcript_summary", ""),
            "case_tags": case_data.get("case_tags", []),
            "evidence_points": case_data.get("evidence_points", []),
            "inconsistencies": case_data.get("inconsistencies", []),
            "parse_warnings": case_data.get("parse_warnings", []),
            "scene_blueprints": case_data.get("scene_blueprints", []),
            "ai_workflows": case_data.get("ai_workflows", []),
            "scene_scripts": [
                {
                    "scene_name": item.get("scene_name"),
                    "fact_ids": item.get("fact_ids", []),
                    "supplement_ids": item.get("supplement_ids", []),
                    "script_markdown": item.get("script_markdown", ""),
                }
                for item in scenes_data if isinstance(item, dict)
            ],
            **case_data,
            "case_type": normalized_case_type,
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
        }
        structured_data_to_save = _standardize_case_structured_people(structured_data_to_save)
        structured_data_to_save, _ = migrate_structured_data_payload(structured_data_to_save)

        db_case = models.Case(
            title=case_title,
            case_type=normalized_case_type or "其他",
            background=background,
            original_content=original_content,
            structured_data=json.dumps(structured_data_to_save, ensure_ascii=False),
        )
        db.add(db_case)
        db.flush()
        source_asset_id = case_data.get("source_asset_id")
        source_asset_key = str(case_data.get("source_asset_key") or "").strip()
        source_asset = None
        if source_asset_id:
            try:
                source_asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == int(source_asset_id)).first()
            except Exception:
                source_asset = None
        if source_asset is None and source_asset_key:
            source_asset = (
                db.query(models.MediaAsset)
                .filter(
                    models.MediaAsset.owner_type == "case_upload",
                    models.MediaAsset.object_key == source_asset_key,
                )
                .first()
            )
        if source_asset:
            source_asset.owner_type = "case"
            source_asset.owner_key = str(db_case.id)
            source_asset.asset_kind = "source_file"
            db.add(source_asset)

        # Parse/scene AI runs are created before an administrator publishes the
        # case. Attach their correlation IDs now so the maintainer can trace a
        # stored case back to its evidence/worldview generation history.
        workflow_items = case_data.get("ai_workflows") if isinstance(case_data.get("ai_workflows"), list) else []
        correlation_ids = {
            str(item.get("correlation_id") or "").strip()
            for item in workflow_items if isinstance(item, dict) and str(item.get("correlation_id") or "").strip()
        }
        if correlation_ids:
            db.query(models.AIWorkflowRun).filter(models.AIWorkflowRun.correlation_id.in_(correlation_ids)).update(
                {models.AIWorkflowRun.case_id: db_case.id}, synchronize_session=False
            )
            db.query(models.CaseStoryVersion).filter(models.CaseStoryVersion.correlation_id.in_(correlation_ids)).update(
                {models.CaseStoryVersion.case_id: db_case.id}, synchronize_session=False
            )

        persons_data = structured_data_to_save.get("persons") or []
        created_roles = {}

        for person in persons_data:
            if not isinstance(person, dict):
                continue
            person = workflow_service._clean_person(person)
            role_name = person.get("name")
            if not role_name:
                continue

            db_role = models.Role(
                case_id=db_case.id,
                name=role_name,
                role_type=person.get("role_type") or "相关人员",
                interaction_style=person.get("interaction_style") or "",
                personality=person.get("personality") or "",
                speaking_style=person.get("speaking_style") or "自然口语",
                init_emotion=person.get("init_emotion", 50),
                init_trust=person.get("init_trust", 30),
                init_risk=person.get("init_risk", 50),
                init_expression_clarity=person.get("init_expression_clarity", 50),
                status=person.get("status") or "正常",
                hidden_truths=json.dumps(person.get("hidden_truths") or person.get("facts_hidden") or person.get("withheld_key_points") or [], ensure_ascii=False),
                knows_facts=json.dumps(person.get("knows_facts") or person.get("facts_known") or person.get("known_key_points") or [], ensure_ascii=False),
                does_not_know=json.dumps(person.get("does_not_know") or person.get("cannot_answer") or [], ensure_ascii=False),
                iq_level="",
                eq_level="",
                lying_ability="",
                weakness="",
                persona_meta=_serialize_person_meta(_extract_person_meta(person)),
            )
            db.add(db_role)
            db.flush()
            created_roles[role_name] = db_role

        for scene_data in scenes_data:
            scene_name = scene_data.get("scene_name") or "未命名场景"
            normalized_stages = _resolve_scene_stages(
                scene_data,
                case_type=normalized_case_type or case_data.get("case_type") or "",
                scene_name=scene_name,
            )
            db_scene = models.Scene(
                case_id=db_case.id,
                name=scene_name,
                description=scene_data.get("scene_description") or "",
                difficulty=scene_data.get("difficulty") or "中等",
                estimated_minutes=_resolve_estimated_minutes(scene_data),
                opening_config=_normalize_opening_config(scene_data.get("opening_config"), created_roles),
                dispatch_brief=scene_data.get("dispatch_brief") or "暂无接警信息",
                first_impression=scene_data.get("first_impression") or "暂无现场第一印象描述",
                stages=json.dumps(normalized_stages, ensure_ascii=False),
            )
            db.add(db_scene)
            db.flush()

            linked_role_ids = set()
            scene_role_configs = {
                str(item.get("name") or ""): item
                for item in scene_data.get("scene_roles") or [] if isinstance(item, dict)
            }
            requested_primary_role_name = workflow_service.canonicalize_role_name(scene_data.get("primary_role_name"), persons_data)
            selected_roles = []

            for role_name in scene_data.get("roles") or []:
                role = created_roles.get(role_name)
                if not role or role.id in linked_role_ids:
                    continue

                linked_role_ids.add(role.id)
                selected_roles.append(role)

            primary_role = next((role for role in selected_roles if role.name == requested_primary_role_name), None)
            if primary_role and not is_role_speakable(primary_role):
                primary_role = None
            if primary_role is None:
                primary_role = next((role for role in selected_roles if is_role_speakable(role)), None)

            for role in selected_roles:
                link = models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=bool(primary_role and role.id == primary_role.id))
                db.add(link)
                ensure_scene_role_initial_state(link, role, db_case, db_scene, source="generated_profile")
                role_config = scene_role_configs.get(role.name) or {}
                if role_config.get("initial_state"):
                    link.initial_state = json.dumps({**role_config["initial_state"], "source": "case_import_harness"}, ensure_ascii=False)
                link.participation_config = json.dumps({
                    "present": role_config.get("present") is not False,
                    "interaction_purpose": role_config.get("interaction_purpose") or "",
                    "can_initiate": bool(role_config.get("can_initiate", False)),
                    "can_interrupt": bool(role_config.get("can_interrupt", False)),
                    "relevant_fact_ids": role_config.get("relevant_fact_ids") or [],
                }, ensure_ascii=False)

        db.flush()
        _sync_role_compatibility_scene(db, db_case.id)
        structured_data_to_save = _compile_persisted_case_artifacts(db, db_case, structured_data_to_save)
        db_case.structured_data = json.dumps(structured_data_to_save, ensure_ascii=False)

        db.commit()
        db.refresh(db_case)
        knowledge_namespace = str(structured_data_to_save.get("knowledge_namespace") or "").strip()
        if knowledge_namespace:
            bound_namespace = bind_namespace(knowledge_namespace, db_case.id)
            structured_data_to_save["knowledge_namespace"] = bound_namespace
            db_case.structured_data = json.dumps(structured_data_to_save, ensure_ascii=False)
            db.commit()
            db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
        return db_case
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print(f"Full create failed: {exc}")
        raise HTTPException(status_code=500, detail=f"保存案件失败: {str(exc)}")


@router.post("/{case_id}/rebuild-role-memories", response_model=schemas.Case)
def rebuild_case_role_memories(case_id: int, payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    """Re-run the source-first role workflow for a legacy saved case."""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    source_text = str(db_case.original_content or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="案件没有可用于回填的原始文本")

    previous = _safe_json_loads(db_case.structured_data, {})
    if not isinstance(previous, dict):
        previous = {}
    source_mode = str(previous.get("source_mode") or "plain_case").strip() or "plain_case"

    try:
        parsed = workflow_service.parse_case_text_with_rule_fallback(source_text, source_mode=source_mode)
        parsed_persons = workflow_service.standardize_person_records(parsed.get("persons") or [])
        if not parsed_persons:
            raise ValueError("原文解析未提取到可用人物，未覆盖原有角色")

        # Preserve editorial settings/scenes. The source workflow owns facts and roles.
        structured = {
            **previous,
            **parsed,
            "case_name": db_case.title,
            "case_type": db_case.case_type,
            "case_background": db_case.background,
            "rawText": source_text,
            "original_content": source_text,
            "persons": parsed_persons,
        }
        structured = _standardize_case_structured_people(structured)
        structured, _ = migrate_structured_data_payload(structured)
        db_case.structured_data = json.dumps(structured, ensure_ascii=False)
        _upsert_case_roles_from_structured_persons(db, db_case)

        if bool(payload.get("replace_legacy_roles", True)):
            source_names = {
                str(person.get("name") or "").strip()
                for person in structured.get("persons") or []
                if isinstance(person, dict) and str(person.get("name") or "").strip()
            }
            _remove_legacy_empty_roles_not_in_source(db, db_case, source_names)

        db.commit()
        db.refresh(db_case)
        knowledge_namespace = str(structured.get("knowledge_namespace") or "").strip()
        if knowledge_namespace:
            bound_namespace = bind_namespace(knowledge_namespace, db_case.id)
            structured["knowledge_namespace"] = bound_namespace
            db_case.structured_data = json.dumps(structured, ensure_ascii=False)
            db.commit()
            db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
        _materialize_case_for_response(db_case)
        return db_case
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"人物线回填失败: {exc}") from exc


@router.put("/{case_id}", response_model=schemas.Case)
def update_case(case_id: int, payload: dict = Body(...), db: Session = Depends(database.get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []
    acknowledgements = payload.get("quality_acknowledgements") or []

    try:
        if "title" in case_data:
            db_case.title = case_data.get("title") or db_case.title
        if "case_type" in case_data:
            db_case.case_type = workflow_service.normalize_case_type(
                text=case_data.get("original_content") or db_case.original_content or "",
                ai_case_type=case_data.get("case_type") or db_case.case_type or ""
            )
        if "background" in case_data:
            db_case.background = case_data.get("background") or ""
        if "original_content" in case_data:
            db_case.original_content = case_data.get("original_content") or ""

        structured_data = _safe_json_loads(db_case.structured_data, {})
        if not isinstance(structured_data, dict):
            structured_data = {}

        if "title" in case_data:
            structured_data["case_name"] = db_case.title
        if "case_type" in case_data:
            structured_data["case_type"] = db_case.case_type
        if "background" in case_data:
            structured_data["case_background"] = db_case.background
        if "original_content" in case_data:
            structured_data["rawText"] = db_case.original_content
            structured_data["original_content"] = db_case.original_content

        incoming_structured_data = _safe_json_loads(case_data.get("structured_data"), None)
        if isinstance(incoming_structured_data, dict):
            structured_data.update(incoming_structured_data)

        structured_data = _standardize_case_structured_people(structured_data)
        structured_data, _ = migrate_structured_data_payload(structured_data)
        db_case.structured_data = json.dumps(structured_data, ensure_ascii=False)
        _upsert_case_roles_from_structured_persons(db, db_case)
        structured_data = _safe_json_loads(db_case.structured_data, {})
        scene_persons = structured_data.get("persons") if isinstance(structured_data, dict) else []
        scenes_data = _canonicalize_scene_role_payloads(scenes_data, scene_persons if isinstance(scene_persons, list) else [])
        if scenes_data:
            candidate = compile_case_scene_artifacts(structured_data, scenes_data)
            _enforce_case_quality_gate(structured_data, candidate["scenes"], acknowledgements)

        scene_map = {scene.id: scene for scene in db_case.scenes}
        role_map = {
            str(role.name or "").strip(): role
            for role in db.query(models.Role).filter(models.Role.case_id == db_case.id).all()
            if str(role.name or "").strip()
        }
        for scene_data in scenes_data:
            scene_id = scene_data.get("id")
            db_scene = scene_map.get(scene_id)
            if not db_scene:
                continue

            if "name" in scene_data:
                db_scene.name = scene_data.get("name") or db_scene.name
            if "description" in scene_data:
                db_scene.description = scene_data.get("description") or ""
            if "difficulty" in scene_data:
                db_scene.difficulty = scene_data.get("difficulty") or "中等"
            if any(key in scene_data for key in ("estimated_minutes", "estimate_minutes", "duration_minutes", "training_minutes")):
                db_scene.estimated_minutes = _resolve_estimated_minutes(scene_data)
            if "opening_config" in scene_data:
                db_scene.opening_config = _normalize_opening_config(scene_data.get("opening_config"), role_map)
            if "dispatch_brief" in scene_data:
                db_scene.dispatch_brief = scene_data.get("dispatch_brief") or ""
            if "first_impression" in scene_data:
                db_scene.first_impression = scene_data.get("first_impression") or ""
            if "stages" in scene_data or scene_data.get("training_focus") or scene_data.get("assessment_points") is not None:
                stages = _resolve_scene_stages(
                    scene_data,
                    case_type=db_case.case_type or "",
                    scene_name=db_scene.name or "",
                )
                db_scene.stages = json.dumps(stages, ensure_ascii=False)

            incoming_role_names = scene_data.get("role_names")
            scene_role_configs = {
                str(item.get("name") or ""): item
                for item in scene_data.get("scene_roles") or [] if isinstance(item, dict)
            }
            primary_role_name = workflow_service.canonicalize_role_name(scene_data.get("primary_role_name"), scene_persons)
            if isinstance(incoming_role_names, list):
                role_names = []
                seen_role_names = set()
                for item in incoming_role_names:
                    name = workflow_service.canonicalize_role_name(item, scene_persons)
                    if not name or name in seen_role_names:
                        continue
                    seen_role_names.add(name)
                    role_names.append(name)

                selected_roles = [role_map[name] for name in role_names if name in role_map]
                db.query(models.SceneRole).filter(models.SceneRole.scene_id == db_scene.id).delete()
                speakable_roles = [role for role in selected_roles if is_role_speakable(role)]
                if selected_roles and not speakable_roles:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "CASE_QUALITY_BLOCKED",
                            "issues": [{"id": f"NON_SPEAKABLE_PRIMARY_ROLE:db:{db_scene.id}", "code": "NON_SPEAKABLE_PRIMARY_ROLE", "message": f"{db_scene.name} 没有可设为主对话人的可交流角色", "scene_ref": f"db:{db_scene.id}"}],
                        },
                    )
                primary_role = next((role for role in speakable_roles if role.name == primary_role_name), speakable_roles[0] if speakable_roles else None)
                for role in selected_roles:
                    link = models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=bool(primary_role and role.id == primary_role.id))
                    db.add(link)
                    ensure_scene_role_initial_state(link, role, db_case, db_scene, source="generated_profile")
                    role_config = scene_role_configs.get(role.name) or {}
                    if role_config.get("initial_state"):
                        link.initial_state = json.dumps({**role_config["initial_state"], "source": "case_import_harness"}, ensure_ascii=False)
                    link.participation_config = json.dumps({
                        "present": role_config.get("present") is not False,
                        "interaction_purpose": role_config.get("interaction_purpose") or "",
                        "can_initiate": bool(role_config.get("can_initiate", False)),
                        "can_interrupt": bool(role_config.get("can_interrupt", False)),
                        "relevant_fact_ids": role_config.get("relevant_fact_ids") or [],
                    }, ensure_ascii=False)

            for link in db.query(models.SceneRole).filter(models.SceneRole.scene_id == db_scene.id).all():
                linked_role = next((item for item in role_map.values() if item.id == link.role_id), None)
                if linked_role:
                    role_config = scene_role_configs.get(linked_role.name) or {}
                    if role_config.get("initial_state"):
                        link.initial_state = json.dumps({**role_config["initial_state"], "source": "case_import_harness"}, ensure_ascii=False)
                        link.participation_config = json.dumps({
                            "present": role_config.get("present") is not False,
                            "interaction_purpose": role_config.get("interaction_purpose") or "",
                            "can_initiate": bool(role_config.get("can_initiate", False)),
                            "can_interrupt": bool(role_config.get("can_interrupt", False)),
                            "relevant_fact_ids": role_config.get("relevant_fact_ids") or [],
                        }, ensure_ascii=False)
                    else:
                        ensure_scene_role_initial_state(link, linked_role, db_case, db_scene, source="edited_profile")

        db.flush()
        _sync_role_compatibility_scene(db, db_case.id)
        structured_data = _compile_persisted_case_artifacts(db, db_case, structured_data)
        structured_data = _standardize_case_structured_people(structured_data)
        structured_data, _ = migrate_structured_data_payload(structured_data)
        db_case.structured_data = json.dumps(structured_data, ensure_ascii=False)
        db.commit()
        db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
        _materialize_case_for_response(db_case)
        return db_case
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print(f"Update case failed: {exc}")
        raise HTTPException(status_code=500, detail=f"更新案件失败: {str(exc)}")


@router.get("/{case_id}", response_model=schemas.Case)
def read_case(case_id: int, db: Session = Depends(database.get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    _materialize_case_for_response(case)
    return case


@router.delete("/{case_id}")
def delete_case(case_id: int, db: Session = Depends(database.get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        delete_case_from_knowledge(case_id)
    except Exception as exc:
        print(f"Case knowledge delete failed for case {case_id}: {exc}")
    try:
        _delete_case_dependencies(db, case)
        delete_media_assets(db, owner_type="case", owner_key=case.id)
        db.delete(case)
        db.commit()
        return {"message": "Case deleted"}
    except Exception as exc:
        db.rollback()
        print(f"Delete case failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Delete case failed: {str(exc)}") from exc
