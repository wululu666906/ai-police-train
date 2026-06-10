import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

import models
from services.role_resolver import is_role_speakable, resolve_scene_role
from services.scene_role_service import audit_scene_roles
from services.case_schema_service import (
    PERSON_ALIAS_TO_CANONICAL,
    SCHEMA_VERSION,
    migrate_structured_data_payload,
)
from services.text_repair import repair_text


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return []


def _push_issue(
    issues: List[Dict[str, Any]],
    *,
    issue_type: str,
    severity: str,
    message: str,
    recommendation: str,
    case: Optional[models.Case] = None,
    scene: Optional[models.Scene] = None,
    role: Optional[models.Role] = None,
):
    issues.append(
        {
            "type": issue_type,
            "severity": severity,
            "message": message,
            "recommendation": recommendation,
            "case_id": case.id if case else None,
            "case_title": repair_text(case.title) if case else None,
            "scene_id": scene.id if scene else None,
            "scene_name": repair_text(scene.name) if scene else None,
            "role_id": role.id if role else None,
            "role_name": repair_text(role.name) if role else None,
        }
    )


def _person_has_alias_conflict(person: dict[str, Any]) -> bool:
    for alias, target in PERSON_ALIAS_TO_CANONICAL.items():
        alias_value = person.get(alias)
        target_value = person.get(target)
        if alias_value in (None, "", []):
            continue
        if target_value in (None, "", []):
            continue
        if alias_value != target_value:
            return True
    return False


def repair_person_alias_conflicts(db: Session, case_id: Optional[int] = None) -> Dict[str, Any]:
    cases_query = db.query(models.Case).order_by(models.Case.id.asc())
    if case_id is not None:
        cases_query = cases_query.filter(models.Case.id == case_id)
    cases = cases_query.all()

    repaired_person_count = 0
    repaired_case_count = 0

    for case in cases:
        if not case.structured_data:
            continue
        try:
            structured = json.loads(case.structured_data)
        except Exception:
            continue
        if not isinstance(structured, dict):
            continue

        persons = structured.get("persons") or []
        if not isinstance(persons, list):
            continue

        case_changed = False
        for person in persons:
            if not isinstance(person, dict):
                continue
            if not _person_has_alias_conflict(person):
                continue
            case_changed = True
            repaired_person_count += 1

        if not case_changed:
            continue

        migrated, _ = migrate_structured_data_payload(structured)
        case.structured_data = json.dumps(migrated, ensure_ascii=False)
        repaired_case_count += 1

    db.commit()
    return {
        "repaired_person_count": repaired_person_count,
        "repaired_case_count": repaired_case_count,
    }


def build_data_quality_report(db: Session) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    cases = db.query(models.Case).order_by(models.Case.id.asc()).all()
    scene_audit = audit_scene_roles(db)
    audit_by_scene_id = {}
    for case_report in scene_audit.get("cases", []):
        for scene_report in case_report.get("scenes", []):
            audit_by_scene_id[scene_report["scene_id"]] = scene_report

    issue_case_ids = set()
    issue_scene_ids = set()
    issue_role_ids = set()
    alias_conflict_count = 0
    deprecated_field_residue_count = 0
    person_boundary_duplication_count = 0
    scene_role_mismatch_count = 0

    for case in cases:
        scenes = db.query(models.Scene).filter(models.Scene.case_id == case.id).order_by(models.Scene.id.asc()).all()
        case_roles = db.query(models.Role).filter(models.Role.case_id == case.id).all()
        structured = {}
        if case.structured_data:
            try:
                structured = json.loads(case.structured_data)
            except Exception:
                structured = {}

        if structured and str(structured.get("schema_version") or "").strip() != SCHEMA_VERSION:
            _push_issue(
                issues,
                issue_type="schema_version_outdated",
                severity="medium",
                message="案件 structured_data 未使用最新 schema_version，存在字段契约漂移风险。",
                recommendation="执行兼容迁移并写回最新 schema_version。",
                case=case,
            )
            issue_case_ids.add(case.id)

        for person in structured.get("persons") or []:
            if not isinstance(person, dict):
                continue
            for alias, target in PERSON_ALIAS_TO_CANONICAL.items():
                alias_value = person.get(alias)
                target_value = person.get(target)
                if alias_value in (None, "", []):
                    continue
                if target_value in (None, "", []):
                    continue
                if alias_value != target_value:
                    alias_conflict_count += 1
                    _push_issue(
                        issues,
                        issue_type="person_alias_conflict",
                        severity="medium",
                        message=f"人物字段 {alias} 与 {target} 值不一致，存在双写漂移。",
                        recommendation=f"停止写入 {alias}，统一以 {target} 为准。",
                        case=case,
                    )
                    issue_case_ids.add(case.id)
                    break

            for alias, target in PERSON_ALIAS_TO_CANONICAL.items():
                if person.get(alias) in (None, "", []):
                    continue
                if person.get(target) not in (None, "", []):
                    deprecated_field_residue_count += 1

            trigger_points = set(_as_text_list(person.get("trigger_points")))
            trigger_sources = set(_as_text_list(person.get("trigger_sources")))
            no_go_topics = set(_as_text_list(person.get("no_go_topics")))
            if trigger_points and (trigger_points & trigger_sources or trigger_points & no_go_topics):
                person_boundary_duplication_count += 1

        for scene in scenes:
            scene_issue_found = False
            if not repair_text(scene.dispatch_brief or "").strip():
                _push_issue(
                    issues,
                    issue_type="missing_dispatch_brief",
                    severity="medium",
                    message="场景缺少接警简报，学员进入训练前信息不足。",
                    recommendation="补充 dispatch brief，让学员端开场信息更完整。",
                    case=case,
                    scene=scene,
                )
                scene_issue_found = True

            if not repair_text(scene.first_impression or "").strip():
                _push_issue(
                    issues,
                    issue_type="missing_first_impression",
                    severity="medium",
                    message="场景缺少现场第一印象描述，学员到场后的观察信息不足。",
                    recommendation="补充 first impression，帮助学员建立场景感知。",
                    case=case,
                    scene=scene,
                )
                scene_issue_found = True

            scene_roles = [role for role in case_roles if role.scene_id == scene.id]
            speakable_roles = [role for role in scene_roles if is_role_speakable(role)]
            resolved_role = resolve_scene_role(db, scene, case)
            if not speakable_roles and not (resolved_role and is_role_speakable(resolved_role)):
                _push_issue(
                    issues,
                    issue_type="no_speakable_role",
                    severity="high",
                    message="场景没有可对话的存活角色，学员进入后无法开展正常对话。",
                    recommendation="为该场景绑定至少一个可说话角色，或调整角色状态。",
                    case=case,
                    scene=scene,
                )
                scene_issue_found = True

            snapshot = audit_by_scene_id.get(scene.id)
            if snapshot:
                issue_codes = snapshot.get("issues", [])
                if any(code in issue_codes for code in ("missing_primary", "multiple_primary", "dead_primary", "missing_links", "primary_mismatch")):
                    scene_role_mismatch_count += 1
                if "missing_primary" in issue_codes:
                    _push_issue(
                        issues,
                        issue_type="missing_primary_role",
                        severity="high",
                        message="场景缺少主对话角色，系统需要在多个角色间兜底判断。",
                        recommendation="为场景指定唯一主说话角色。",
                        case=case,
                        scene=scene,
                    )
                    scene_issue_found = True
                if "multiple_primary" in issue_codes:
                    _push_issue(
                        issues,
                        issue_type="multiple_primary_roles",
                        severity="high",
                        message="场景存在多个主对话角色，容易导致对话分配混乱。",
                        recommendation="只保留一个 primary 角色，其余改为辅助角色。",
                        case=case,
                        scene=scene,
                    )
                    scene_issue_found = True
                if "dead_primary" in issue_codes:
                    _push_issue(
                        issues,
                        issue_type="dead_primary_role",
                        severity="high",
                        message="当前主对话角色不可说话，可能出现死者开口或重伤者被对话。",
                        recommendation="将 primary 调整为存活且可交流的角色。",
                        case=case,
                        scene=scene,
                    )
                    scene_issue_found = True
                if "missing_links" in issue_codes:
                    _push_issue(
                        issues,
                        issue_type="missing_scene_role_links",
                        severity="medium",
                        message="场景未正确绑定人物关系，角色分配依赖兜底解析。",
                        recommendation="补齐 SceneRole 绑定关系，减少训练时的歧义。",
                        case=case,
                        scene=scene,
                    )
                    scene_issue_found = True

            if scene_issue_found:
                issue_scene_ids.add(scene.id)
                issue_case_ids.add(case.id)

        for role in case_roles:
            status = repair_text(role.status or "").strip()
            if not repair_text(role.name or "").strip():
                _push_issue(
                    issues,
                    issue_type="missing_role_name",
                    severity="medium",
                    message="角色缺少名称，学员端将无法正确展示对话对象。",
                    recommendation="为角色补充明确姓名或身份称谓。",
                    case=case,
                    role=role,
                )
                issue_role_ids.add(role.id)
                issue_case_ids.add(case.id)
            if not status:
                _push_issue(
                    issues,
                    issue_type="missing_role_status",
                    severity="low",
                    message="角色状态为空，系统无法明确判断其是否可说话。",
                    recommendation="补充角色状态，例如正常、死亡、重伤、昏迷等。",
                    case=case,
                    role=role,
                )
                issue_role_ids.add(role.id)
                issue_case_ids.add(case.id)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(
        key=lambda item: (
            severity_order.get(item["severity"], 99),
            item.get("case_id") or 0,
            item.get("scene_id") or 0,
            item["type"],
        )
    )

    return {
        "summary": {
            "case_count": len(cases),
            "issue_case_count": len(issue_case_ids),
            "issue_scene_count": len(issue_scene_ids),
            "issue_role_count": len(issue_role_ids),
            "total_issue_count": len(issues),
            "high_count": sum(1 for item in issues if item["severity"] == "high"),
            "medium_count": sum(1 for item in issues if item["severity"] == "medium"),
            "low_count": sum(1 for item in issues if item["severity"] == "low"),
            "alias_conflict_count": alias_conflict_count,
            "deprecated_field_residue_count": deprecated_field_residue_count,
            "person_boundary_duplication_count": person_boundary_duplication_count,
            "scene_role_mismatch_count": scene_role_mismatch_count,
        },
        "issues": issues,
    }
