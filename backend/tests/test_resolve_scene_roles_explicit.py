"""Scene role resolution must respect explicit SceneRole bindings."""

import json

import models
from services.role_resolver import resolve_scene_roles


def test_resolve_scene_roles_only_returns_linked_roles(db_session):
    case = models.Case(
        title="测试案件",
        case_type="纠纷",
        background="测试",
        original_content="测试",
        structured_data=json.dumps(
            {
                "scene_role_map": {
                    "现场调解": {
                        "role_names": ["张某", "李某"],
                        "primary_role_name": "张某",
                    }
                }
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(case)
    db_session.flush()

    scene = models.Scene(case_id=case.id, name="现场调解", description="", difficulty="中等", stages="[]")
    db_session.add(scene)
    db_session.flush()

    roles = {}
    for name in ("张某", "李某", "孙桂兰"):
        role = models.Role(
            case_id=case.id,
            name=name,
            role_type="当事人",
            personality="测试",
            init_emotion=50,
            init_trust=30,
            status="正常",
        )
        db_session.add(role)
        db_session.flush()
        roles[name] = role

    for name in ("张某", "李某"):
        db_session.add(models.SceneRole(scene_id=scene.id, role_id=roles[name].id, is_primary=name == "张某"))
    db_session.commit()

    resolved = resolve_scene_roles(db_session, scene, case)
    resolved_names = {role.name for role in resolved}
    assert resolved_names == {"张某", "李某"}
    assert "孙桂兰" not in resolved_names
