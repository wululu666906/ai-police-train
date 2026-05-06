import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

import models
from .role_resolver import is_role_speakable, resolve_scene_role


ALARM_ROLE_NAME = "报警人"


def _person_meta_map(case: Optional[models.Case]) -> Dict[str, dict]:
    if not case or not case.structured_data:
        return {}
    try:
        structured = json.loads(case.structured_data or "{}")
    except Exception:
        return {}
    persons = structured.get("persons") or []
    return {str(person.get("name", "")).strip(): person for person in persons if person.get("name")}


def _build_alarm_role(db: Session, case_id: int) -> models.Role:
    existing = (
        db.query(models.Role)
        .filter(models.Role.case_id == case_id, models.Role.name == ALARM_ROLE_NAME)
        .first()
    )
    if existing:
        return existing

    role = models.Role(
        case_id=case_id,
        name=ALARM_ROLE_NAME,
        role_type="配合型",
        personality="情绪紧张，愿意配合，但表达可能不完整",
        speaking_style="急促",
        init_emotion=70,
        init_trust=45,
        status="正常",
        iq_level="中等",
        eq_level="中等",
        lying_ability="一般",
        weakness="容易慌张，信息表述可能缺漏",
        knows_facts=json.dumps(["自己看到、听到或发现异常后的情况"], ensure_ascii=False),
        does_not_know=json.dumps(["作案经过", "凶手完整动机"], ensure_ascii=False),
        hidden_truths=json.dumps([], ensure_ascii=False),
    )
    db.add(role)
    db.flush()
    return role


def _witness_like(person_meta: dict) -> bool:
    person_role = str((person_meta or {}).get("role") or "")
    return any(keyword in person_role for keyword in ("报警", "报案", "证人", "目击", "家属", "邻居", "朋友", "闺蜜", "同事"))


def _suspect_like(person_meta: dict) -> bool:
    person_role = str((person_meta or {}).get("role") or "")
    person_role_type = str((person_meta or {}).get("role_type") or "")
    return any(keyword in person_role for keyword in ("嫌疑", "凶手", "加害", "作案")) or any(
        keyword in person_role_type for keyword in ("嫌疑", "凶手", "加害", "作案")
    )


def _scene_snapshot(db: Session, scene: models.Scene, case: models.Case) -> Dict[str, Any]:
    role_rows = (
        db.query(models.SceneRole, models.Role)
        .join(models.Role, models.Role.id == models.SceneRole.role_id)
        .filter(models.SceneRole.scene_id == scene.id)
        .all()
    )
    primary_rows = [row for row in role_rows if row[0].is_primary]
    primary_count = len(primary_rows)
    primary_names = [row[1].name for row in primary_rows]
    dead_primary_names = [row[1].name for row in primary_rows if not is_role_speakable(row[1])]

    issues: List[str] = []
    if primary_count == 0:
        issues.append("missing_primary")
    if primary_count > 1:
        issues.append("multiple_primary")
    if dead_primary_names:
        issues.append("dead_primary")
    if not role_rows:
        issues.append("missing_links")

    resolved_role = resolve_scene_role(db, scene, case)
    resolved_name = getattr(resolved_role, "name", None)
    primary_name = primary_names[0] if primary_names else None
    if resolved_name and primary_name and resolved_name != primary_name:
        issues.append("primary_mismatch")

    return {
        "scene_id": scene.id,
        "scene_name": scene.name,
        "current_primary_names": primary_names,
        "resolved_role_name": resolved_name,
        "resolved_role_status": getattr(resolved_role, "status", None),
        "issues": issues,
    }


def audit_scene_roles(db: Session, case_id: Optional[int] = None) -> Dict[str, Any]:
    cases_query = db.query(models.Case)
    if case_id is not None:
        cases_query = cases_query.filter(models.Case.id == case_id)
    cases = cases_query.order_by(models.Case.id.asc()).all()

    case_reports = []
    issue_scene_count = 0

    for case in cases:
        scenes = db.query(models.Scene).filter(models.Scene.case_id == case.id).order_by(models.Scene.id.asc()).all()
        scene_reports = []
        for scene in scenes:
            snapshot = _scene_snapshot(db, scene, case)
            if snapshot["issues"]:
                issue_scene_count += 1
            scene_reports.append(snapshot)

        case_reports.append(
            {
                "case_id": case.id,
                "case_title": case.title,
                "scene_count": len(scene_reports),
                "issue_scene_count": sum(1 for item in scene_reports if item["issues"]),
                "scenes": scene_reports,
            }
        )

    return {
        "case_count": len(case_reports),
        "issue_scene_count": issue_scene_count,
        "cases": case_reports,
    }


def normalize_scene_roles(db: Session, case_id: Optional[int] = None) -> Dict[str, Any]:
    cases_query = db.query(models.Case)
    if case_id is not None:
        cases_query = cases_query.filter(models.Case.id == case_id)
    cases = cases_query.order_by(models.Case.id.asc()).all()

    repaired_scene_count = 0
    touched_case_count = 0

    for case in cases:
        person_meta_map = _person_meta_map(case)
        scenes = db.query(models.Scene).filter(models.Scene.case_id == case.id).order_by(models.Scene.id.asc()).all()
        case_roles = db.query(models.Role).filter(models.Role.case_id == case.id).order_by(models.Role.id.asc()).all()
        case_changed = False

        for scene in scenes:
            scene_text = " ".join(
                [str(scene.name or ""), str(scene.description or ""), str(scene.dispatch_brief or ""), str(scene.first_impression or "")]
            )

            primary_role = resolve_scene_role(db, scene, case)
            if scene.name and "接警" in scene.name and getattr(primary_role, "name", "") == ALARM_ROLE_NAME:
                primary_role = _build_alarm_role(db, case.id)

            secondary_roles = []
            seen_role_ids = {getattr(primary_role, "id", None)}

            for role in case_roles:
                if role.id in seen_role_ids:
                    continue
                if not is_role_speakable(role):
                    continue

                person_meta = person_meta_map.get(role.name, {})
                role_is_named = bool(role.name and role.name in scene_text)

                include = False
                if role_is_named:
                    include = True
                elif scene.name and any(keyword in scene.name for keyword in ("现场", "勘查", "调查")) and _witness_like(person_meta):
                    include = True
                elif scene.name and any(keyword in scene.name for keyword in ("审讯", "讯问", "嫌疑人")) and _suspect_like(person_meta):
                    include = True

                if include:
                    secondary_roles.append(role)
                    seen_role_ids.add(role.id)

            old_links = (
                db.query(models.SceneRole, models.Role)
                .join(models.Role, models.Role.id == models.SceneRole.role_id)
                .filter(models.SceneRole.scene_id == scene.id)
                .all()
            )
            old_signature = sorted((row[1].name, bool(row[0].is_primary)) for row in old_links)
            new_signature = []
            if primary_role and getattr(primary_role, "id", None):
                new_signature.append((primary_role.name, True))
            new_signature.extend(sorted((role.name, False) for role in secondary_roles))

            if old_signature != sorted(new_signature):
                case_changed = True
                repaired_scene_count += 1

            db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).delete()

            if primary_role and getattr(primary_role, "id", None):
                db.add(models.SceneRole(scene_id=scene.id, role_id=primary_role.id, is_primary=True))
                if primary_role.name != ALARM_ROLE_NAME:
                    primary_role.scene_id = scene.id

            for role in secondary_roles:
                db.add(models.SceneRole(scene_id=scene.id, role_id=role.id, is_primary=False))

        if case_changed:
            touched_case_count += 1

    db.commit()
    return {
        "repaired_scene_count": repaired_scene_count,
        "touched_case_count": touched_case_count,
    }
