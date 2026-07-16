import json
import os
from collections import defaultdict
from typing import List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import require_admin_user
from services.data_quality_service import build_data_quality_report, repair_person_alias_conflicts
from services.case_schema_service import (
    canonicalize_person_payload,
    migrate_structured_data_payload,
)
from services.document_extract_service import document_extract_service
from services.role_resolver import is_role_speakable
from services.scene_role_service import audit_scene_roles, normalize_scene_roles
from services.scene_compact_service import build_scene_stages_from_compact, infer_training_focus
from services.stage_config_service import infer_scene_behavior_mode, normalize_stages
from services.case_completion_service import complete_case_information, list_field_catalog
from services.case_knowledge_service import delete_case_from_knowledge, try_sync_case_to_knowledge
from services.workflow_service import workflow_service
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
from services.ai_roles import get_assessment_point_officer_prompts, list_ai_roles
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
    )


def _extract_person_meta(payload: dict | None, base_meta: dict | None = None):
    payload = payload or {}
    base_meta = base_meta or {}

    def _text_field(name: str):
        if name in payload:
            return str(payload.get(name) or "").strip()
        return str(base_meta.get(name) or "").strip()

    def _list_field(name: str):
        if name in payload:
            return _ensure_list(payload.get(name))
        return _ensure_list(base_meta.get(name))

    def _score_field(name: str):
        raw_value = payload.get(name) if name in payload else base_meta.get(name)
        if raw_value in (None, ""):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    result = {
        "behavior_archetype": _text_field("behavior_archetype"),
        "police_attitude": _text_field("police_attitude"),
        "scene_behavior_mode": _text_field("scene_behavior_mode"),
        "current_goal": _text_field("current_goal"),
        "core_concern": _text_field("core_concern"),
        "relationship_pressure": _list_field("relationship_pressure"),
        "surface_stance": _text_field("surface_stance"),
        "pressure_response": _text_field("pressure_response"),
        "trigger_points": _list_field("trigger_points"),
        "calming_points": _list_field("calming_points"),
        "emotion_level": _text_field("emotion_level"),
        "cooperation_level": _text_field("cooperation_level"),
        "risk_level": _text_field("risk_level"),
        "clarity_level": _text_field("clarity_level"),
        "init_risk": _score_field("init_risk"),
        "init_expression_clarity": _score_field("init_expression_clarity"),
        "known_key_points": _list_field("known_key_points"),
        "withheld_key_points": _list_field("withheld_key_points"),
        "conflict_core": _list_field("conflict_core"),
        "acceptable_outcomes": _list_field("acceptable_outcomes"),
        "no_go_topics": _list_field("no_go_topics"),
        "trigger_sources": _list_field("trigger_sources"),
        "concerned_targets": _list_field("concerned_targets"),
        "taboo_actions": _list_field("taboo_actions"),
        "escalation_actions": _list_field("escalation_actions"),
        "deescalation_conditions": _list_field("deescalation_conditions"),
        "impairment_state": _text_field("impairment_state"),
        "self_image": _text_field("self_image"),
        "current_need": _text_field("current_need"),
        "authority_attitude": _text_field("authority_attitude"),
        "stress_response": _text_field("stress_response"),
        "protected_targets": _list_field("protected_targets"),
        "feared_people": _list_field("feared_people"),
        "conflict_targets": _list_field("conflict_targets"),
        "feared_consequences": _list_field("feared_consequences"),
        "trigger_topics": _list_field("trigger_topics"),
        "coping_patterns": _list_field("coping_patterns"),
        "public_mask": _text_field("public_mask"),
        "private_drive": _text_field("private_drive"),
    }
    canonical_result, _ = canonicalize_person_payload(result)
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
    return {
        "name": role.name,
        "role": role.role_type or "相关人员",
        "role_type": role.role_type or "相关人员",
        "interaction_style": getattr(role, "interaction_style", None) or "配合型",
        "personality": role.personality or "普通人",
        "speaking_style": role.speaking_style or "常规",
        "init_emotion": role.init_emotion,
        "init_trust": role.init_trust,
        "status": role.status or "正常",
        "knows_facts": _ensure_list(role.knows_facts),
        "does_not_know": _ensure_list(role.does_not_know),
        "hidden_truths": _ensure_list(role.hidden_truths),
        "iq_level": role.iq_level or "中等",
        "eq_level": role.eq_level or "中等",
        "lying_ability": role.lying_ability or "一般",
        "weakness": role.weakness or "",
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
        if canonical_roles:
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
    newly_created_roles: list[models.Role] = []
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
        interaction_style = _normalize_person_interaction_style(person)

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
                personality=str(person.get("personality") or "待核实").strip(),
                speaking_style=str(person.get("speaking_style") or "常规").strip(),
                init_emotion=person.get("init_emotion", 50),
                init_trust=person.get("init_trust", 30),
                status=str(person.get("status") or "正常").strip(),
                hidden_truths=_serialize_role_list(person.get("hidden_truths")),
                knows_facts=_serialize_role_list(person.get("knows_facts")),
                does_not_know=_serialize_role_list(person.get("does_not_know")),
                iq_level=str(person.get("iq_level") or "中等").strip(),
                eq_level=str(person.get("eq_level") or "中等").strip(),
                lying_ability=str(person.get("lying_ability") or "一般").strip(),
                weakness=str(person.get("weakness") or "").strip(),
            )
            db.add(role)
            existing_roles[person_name] = role
            newly_created_roles.append(role)
            changed = True
            continue

        role.role_type = role_type or role.role_type or "相关人员"
        role.interaction_style = interaction_style or getattr(role, "interaction_style", None) or "配合型"
        role.personality = str(person.get("personality") or role.personality or "待核实").strip()
        role.speaking_style = str(person.get("speaking_style") or role.speaking_style or "常规").strip()
        role.init_emotion = person.get("init_emotion", role.init_emotion)
        role.init_trust = person.get("init_trust", role.init_trust)
        role.status = str(person.get("status") or role.status or "正常").strip()
        role.knows_facts = _serialize_role_list(person.get("knows_facts"))
        role.does_not_know = _serialize_role_list(person.get("does_not_know"))
        role.hidden_truths = _serialize_role_list(person.get("hidden_truths"))
        role.iq_level = str(person.get("iq_level") or role.iq_level or "中等").strip()
        role.eq_level = str(person.get("eq_level") or role.eq_level or "中等").strip()
        role.lying_ability = str(person.get("lying_ability") or role.lying_ability or "一般").strip()
        role.weakness = str(person.get("weakness") or role.weakness or "").strip()
        changed = True

    if changed:
        db.flush()
        default_scene = (
            db.query(models.Scene)
            .filter(models.Scene.case_id == case.id)
            .order_by(models.Scene.id.asc())
            .first()
        )
        if default_scene:
            for role in newly_created_roles:
                has_scene_link = (
                    db.query(models.SceneRole)
                    .filter(models.SceneRole.role_id == role.id)
                    .first()
                    is not None
                )
                if has_scene_link:
                    continue
                role.scene_id = role.scene_id or default_scene.id
                db.add(models.SceneRole(scene_id=default_scene.id, role_id=role.id, is_primary=False))


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
        _materialize_case_scenes_for_response(case)
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
        person_meta = _extract_person_meta({}, case_meta) if role.case_id else _extract_person_meta({}, _get_role_person_meta(role))
        base_payload = {
            "id": role.id,
            "name": role.name,
            "role_type": role.role_type,
            "interaction_style": getattr(role, "interaction_style", None) or "配合型",
            "personality": role.personality,
            "speaking_style": role.speaking_style,
            "init_emotion": role.init_emotion,
            "init_trust": role.init_trust,
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


@router.get("/role-case-options")
def read_role_case_options(db: Session = Depends(database.get_db)):
    cases = db.query(models.Case).order_by(models.Case.created_at.desc()).all()
    return [
        {
            "id": case.id,
            "title": case.title,
            "case_type": case.case_type,
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

    db_role = models.Role(
        case_id=db_case.id if db_case else None,
        name=role_name,
        role_type=payload.get("role_type") or "相关人员",
        interaction_style=payload.get("interaction_style") or "配合型",
        personality=payload.get("personality") or "普通人",
        speaking_style=payload.get("speaking_style") or "常规",
        init_emotion=payload.get("init_emotion", 50),
        init_trust=payload.get("init_trust", 30),
        status=payload.get("status") or "正常",
        iq_level=payload.get("iq_level") or "中等",
        eq_level=payload.get("eq_level") or "中等",
        lying_ability=payload.get("lying_ability") or "一般",
        weakness=payload.get("weakness") or "",
        knows_facts=_serialize_role_list(payload.get("knows_facts")),
        does_not_know=_serialize_role_list(payload.get("does_not_know")),
        hidden_truths=_serialize_role_list(payload.get("hidden_truths")),
        persona_meta=_serialize_person_meta(_extract_person_meta(payload)) if db_case is None else "{}",
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
    db_role.interaction_style = payload.get("interaction_style") or getattr(db_role, "interaction_style", None) or "配合型"
    db_role.personality = payload.get("personality") or db_role.personality
    db_role.speaking_style = payload.get("speaking_style") or db_role.speaking_style
    db_role.init_emotion = payload.get("init_emotion", db_role.init_emotion)
    db_role.init_trust = payload.get("init_trust", db_role.init_trust)
    db_role.status = payload.get("status") or db_role.status
    db_role.iq_level = payload.get("iq_level") or db_role.iq_level
    db_role.eq_level = payload.get("eq_level") or db_role.eq_level
    db_role.lying_ability = payload.get("lying_ability") or db_role.lying_ability
    db_role.weakness = payload.get("weakness") or db_role.weakness
    db_role.knows_facts = _serialize_role_list(payload.get("knows_facts"))
    db_role.does_not_know = _serialize_role_list(payload.get("does_not_know"))
    db_role.hidden_truths = _serialize_role_list(payload.get("hidden_truths"))

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
        db_role.persona_meta = _serialize_person_meta(_extract_person_meta(payload, existing_meta))

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
        return workflow_service.parse_case_text_with_rule_fallback(text, source_mode=source_mode)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI parsing failed: {exc}") from exc


@router.post("/parse-file")
async def parse_case_file(
    file: UploadFile = File(...),
    source_mode: str = Form("transcript_file"),
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
        result = workflow_service.parse_case_text_with_rule_fallback(
            extracted_text,
            source_mode=source_mode or "transcript_file",
            source_meta=extraction.as_source_meta(name=filename, extension=extension, size=len(file_bytes)),
        )
        result["ocr_method"] = extraction.method
        result["ocr_engine"] = extraction.engine
        result["ocr_warnings"] = extraction.warnings
        result["ocr_metadata"] = extraction.metadata
        result["extracted_text_full"] = extracted_text
        result["extracted_text_preview"] = extraction.preview
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI file parsing failed: {exc}") from exc


@router.get("/completion-catalog")
def get_completion_catalog():
    return list_field_catalog()


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
    return {
        "points": points,
        "count": len(points),
        "extracted_chars": len(extracted_text),
        "extracted_text": extracted_text[:8000],
        "filename": filename,
        "mode": "replace",
        "max_per_scene": ASSESSMENT_POINTS_MAX_PER_SCENE,
        "warnings": warnings,
        "message": f"已从「{filename}」解析 {len(points)} 条考察点",
    }


@router.get("/ai-roles")
def get_ai_roles_catalog():
    return {"roles": list_ai_roles()}


@router.get("/ai-roles/assessment-point-officer")
def get_assessment_point_officer_role(_user=Depends(require_admin_user)):
    """Return dedicated officer prompts for admin review (read-only)."""
    return get_assessment_point_officer_prompts()


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
        result["officer_role"] = "考察点编排专员"
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


@router.post("/{case_id}/ai-fill")
def ai_fill_case_by_id(case_id: int, payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    """按案件 ID 一键补齐：读取原文与结构化数据，返回补全建议（不自动保存）。"""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="案件不存在")

    source_text = db_case.original_content or db_case.background or ""
    if not str(source_text).strip():
        raise HTTPException(
            status_code=400,
            detail="该案件没有原始文本内容（original_content），无法进行 AI 补全。请先在案件编辑页填写原始案情文字。",
        )

    existing_case = _safe_json_loads(db_case.structured_data, {})
    if not existing_case.get("case_name") and db_case.title:
        existing_case["case_name"] = db_case.title
    if not existing_case.get("case_type") and db_case.case_type:
        existing_case["case_type"] = db_case.case_type
    if not existing_case.get("case_background") and db_case.background:
        existing_case["case_background"] = db_case.background

    mode = str(payload.get("mode") or "fill_gaps")
    if mode not in {"full", "fill_gaps", "targeted"}:
        mode = "fill_gaps"

    target_groups = payload.get("target_groups")
    if isinstance(target_groups, str):
        target_groups = [target_groups]
    if not isinstance(target_groups, list):
        target_groups = None

    include_scenes = bool(payload.get("include_scenes", True))
    scene_generation_strategy = payload.get("scene_generation_strategy") or "case_driven"

    try:
        result = complete_case_information(
            source_text=str(source_text),
            source_mode="plain_case",
            existing_case=existing_case,
            mode=mode,
            target_groups=target_groups,
            include_scenes=include_scenes,
            scene_generation_strategy=scene_generation_strategy,
        )
        result["case_id"] = case_id
        result["case_title"] = db_case.title
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 补全失败: {exc}") from exc


@router.post("/ai-complete")
def ai_complete_case(payload: dict = Body(...)):
    source_text = payload.get("source_text") or payload.get("text") or ""
    if not str(source_text).strip():
        raise HTTPException(status_code=400, detail="source_text is required")

    source_mode = payload.get("source_mode") or "plain_case"
    mode = payload.get("mode") or "fill_gaps"
    if mode not in {"full", "fill_gaps", "targeted"}:
        mode = "fill_gaps"

    target_groups = payload.get("target_groups")
    if isinstance(target_groups, str):
        target_groups = [target_groups]
    if not isinstance(target_groups, list):
        target_groups = None

    existing_case = payload.get("case_info") or payload.get("existing_case") or {}
    include_scenes = bool(payload.get("include_scenes", True))
    scene_generation_strategy = payload.get("scene_generation_strategy") or "case_driven"

    try:
        return complete_case_information(
            source_text=str(source_text),
            source_mode=source_mode,
            existing_case=existing_case if isinstance(existing_case, dict) else {},
            mode=mode,
            target_groups=target_groups,
            include_scenes=include_scenes,
            source_meta=payload.get("source_meta"),
            scene_generation_strategy=scene_generation_strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"案件信息补全失败: {exc}") from exc


@router.post("/generate-scenes")
def generate_scenes(payload: dict = Body(...)):
    case_info = payload.get("case_info")
    if not case_info:
        raise HTTPException(status_code=400, detail="Case info is required")
    scene_generation_strategy = payload.get("scene_generation_strategy") or "case_driven"
    try:
        return workflow_service.generate_scenes(case_info, scene_generation_strategy=scene_generation_strategy)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI scene generation failed: {exc}") from exc


@router.get("/scene-role-audit")
def get_scene_role_audit(case_id: int | None = None, db: Session = Depends(database.get_db)):
    return audit_scene_roles(db, case_id=case_id)


@router.get("/data-quality-report")
def get_data_quality_report(db: Session = Depends(database.get_db)):
    return build_data_quality_report(db)


@router.post("/data-quality-repair")
def repair_data_quality(payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    case_id = payload.get("case_id")
    repair_result = repair_person_alias_conflicts(db, case_id=case_id)
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

    try:
        case_title = case_data.get("title") or case_data.get("case_name") or "未命名案件"
        original_content = case_data.get("original_content") or case_data.get("rawText") or ""
        background = case_data.get("background") or case_data.get("case_background") or "暂无案件背景"
        normalized_case_type = workflow_service.normalize_case_type(
            text=original_content,
            ai_case_type=case_data.get("case_type") or ""
        )

        standardized_persons = workflow_service.standardize_person_records(case_data.get("persons") or [])
        case_data = {**case_data, "persons": standardized_persons}
        scenes_data = _canonicalize_scene_role_payloads(scenes_data, standardized_persons)

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
            "scene_role_map": _build_scene_role_map(scenes_data),
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
                interaction_style=person.get("interaction_style") or "配合型",
                personality=person.get("personality") or "暂无详细性格描述",
                speaking_style=person.get("speaking_style") or "常规",
                init_emotion=person.get("init_emotion", 50),
                init_trust=person.get("init_trust", 30),
                status=person.get("status") or "正常",
                hidden_truths=json.dumps(person.get("hidden_truths", []), ensure_ascii=False),
                knows_facts=json.dumps(person.get("knows_facts", []), ensure_ascii=False),
                does_not_know=json.dumps(person.get("does_not_know", []), ensure_ascii=False),
                iq_level=person.get("iq_level", "中等"),
                eq_level=person.get("eq_level", "中等"),
                lying_ability=person.get("lying_ability", "一般"),
                weakness=person.get("weakness", ""),
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
                dispatch_brief=scene_data.get("dispatch_brief") or "暂无接警信息",
                first_impression=scene_data.get("first_impression") or "暂无现场第一印象描述",
                stages=json.dumps(normalized_stages, ensure_ascii=False),
            )
            db.add(db_scene)
            db.flush()

            linked_role_ids = set()
            requested_primary_role_name = workflow_service.canonicalize_role_name(scene_data.get("primary_role_name"), persons_data)
            selected_roles = []

            for role_name in scene_data.get("roles") or []:
                role = created_roles.get(role_name)
                if not role or role.id in linked_role_ids:
                    continue

                linked_role_ids.add(role.id)
                role.scene_id = db_scene.id
                selected_roles.append(role)

            primary_role = next((role for role in selected_roles if role.name == requested_primary_role_name), None)
            if primary_role and not is_role_speakable(primary_role):
                primary_role = None
            if primary_role is None:
                primary_role = next((role for role in selected_roles if is_role_speakable(role)), None)

            for role in selected_roles:
                db.add(models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=bool(primary_role and role.id == primary_role.id)))

            if primary_role is None:
                for role in created_roles.values():
                    if not is_role_speakable(role):
                        continue
                    if role.id in linked_role_ids:
                        continue

                    db.add(models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=True))
                    linked_role_ids.add(role.id)
                    role.scene_id = db_scene.id
                    break

        db.commit()
        db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
        return db_case
    except Exception as exc:
        db.rollback()
        print(f"Full create failed: {exc}")
        raise HTTPException(status_code=500, detail=f"保存案件失败: {str(exc)}")


@router.put("/{case_id}", response_model=schemas.Case)
def update_case(case_id: int, payload: dict = Body(...), db: Session = Depends(database.get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []

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
                if selected_roles:
                    db.query(models.SceneRole).filter(models.SceneRole.scene_id == db_scene.id).delete()
                    for role in selected_roles:
                        role.scene_id = db_scene.id
                    primary_role = next((role for role in selected_roles if role.name == primary_role_name), selected_roles[0])
                    if not is_role_speakable(primary_role):
                        primary_role = next((role for role in selected_roles if is_role_speakable(role)), primary_role)
                    for role in selected_roles:
                        db.add(models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=role.id == primary_role.id))

        if scenes_data:
            structured_data["scene_role_map"] = _build_scene_role_map(scenes_data)
        structured_data = _standardize_case_structured_people(structured_data)
        structured_data, _ = migrate_structured_data_payload(structured_data)
        db_case.structured_data = json.dumps(structured_data, ensure_ascii=False)
        db.commit()
        db.refresh(db_case)
        try_sync_case_to_knowledge(db_case)
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
    _materialize_case_scenes_for_response(case)
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
    db.delete(case)
    db.commit()
    return {"message": "Case deleted"}
