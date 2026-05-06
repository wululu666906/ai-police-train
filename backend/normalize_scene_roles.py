import json

from database import SessionLocal
import models
from services.role_resolver import is_role_speakable, resolve_scene_role


def build_alarm_role(db, case_id: int):
    existing = (
        db.query(models.Role)
        .filter(models.Role.case_id == case_id, models.Role.name == "报警人")
        .first()
    )
    if existing:
        return existing

    role = models.Role(
        case_id=case_id,
        name="报警人",
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


def witness_like(person_meta: dict) -> bool:
    person_role = str((person_meta or {}).get("role") or "")
    return any(keyword in person_role for keyword in ("报警", "报案", "证人", "目击", "家属", "邻居", "朋友", "闺蜜", "同事"))


def suspect_like(person_meta: dict) -> bool:
    person_role = str((person_meta or {}).get("role") or "")
    person_role_type = str((person_meta or {}).get("role_type") or "")
    return any(keyword in person_role for keyword in ("嫌疑", "凶手", "加害", "作案")) or any(
        keyword in person_role_type for keyword in ("嫌疑", "凶手", "加害", "作案")
    )


def main():
    db = SessionLocal()
    try:
        scenes = db.query(models.Scene).order_by(models.Scene.id.asc()).all()
        for scene in scenes:
            case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
            if not case:
                continue

            try:
                structured = json.loads(case.structured_data or "{}")
            except Exception:
                structured = {}

            person_meta_map = {
                str(person.get("name", "")).strip(): person
                for person in (structured.get("persons") or [])
                if person.get("name")
            }

            scene_text = " ".join(
                [
                    str(scene.name or ""),
                    str(scene.description or ""),
                    str(scene.dispatch_brief or ""),
                    str(scene.first_impression or ""),
                ]
            )
            case_roles = db.query(models.Role).filter(models.Role.case_id == case.id).order_by(models.Role.id.asc()).all()

            primary_role = resolve_scene_role(db, scene, case)
            if scene.name and "接警" in scene.name and getattr(primary_role, "name", "") == "报警人":
                primary_role = build_alarm_role(db, case.id)

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
                elif scene.name and any(keyword in scene.name for keyword in ("现场", "勘查", "调查")) and witness_like(person_meta):
                    include = True
                elif scene.name and any(keyword in scene.name for keyword in ("审讯", "讯问", "嫌疑人")) and suspect_like(person_meta):
                    include = True

                if include:
                    secondary_roles.append(role)
                    seen_role_ids.add(role.id)

            db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).delete()

            if primary_role and getattr(primary_role, "id", None):
                db.add(models.SceneRole(scene_id=scene.id, role_id=primary_role.id, is_primary=True))
                if primary_role.name != "报警人":
                    primary_role.scene_id = scene.id

            for role in secondary_roles:
                db.add(models.SceneRole(scene_id=scene.id, role_id=role.id, is_primary=False))

        db.commit()
        print("scene role normalization completed")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
