import json

import models
from services.opening_turn_service import (
    INTAKE_MINIMAL_DISPATCH,
    ensure_opening_turn,
    generate_opening_utterances,
    infer_session_scene_kind,
    is_caller_opening_role,
    redact_dispatch_brief_for_student,
    resolve_dialogue_mode,
    should_generate_opening,
)
from services.training_runtime_service import dump_runtime_state, load_runtime_state


def test_infer_intake_scene_kind():
    scene = models.Scene(name="接警研判", description="", difficulty="中等", stages="[]")
    session = models.TrainingSession(current_stage="接警研判", current_emotion=50, current_trust=30)
    assert infer_session_scene_kind(scene, session) == "intake"
    assert resolve_dialogue_mode(scene, session) == "caller_first"


def test_non_intake_scene_is_officer_led():
    scene = models.Scene(name="现场处置", description="", difficulty="中等", stages="[]")
    session = models.TrainingSession(current_stage="现场处置", current_emotion=50, current_trust=30)
    assert infer_session_scene_kind(scene, session) == "onsite"
    assert resolve_dialogue_mode(scene, session) == "officer_led"


def test_is_caller_opening_role():
    role = models.Role(name="张某", role_type="报警人", status="正常")
    assert is_caller_opening_role(role) is True
    suspect = models.Role(name="李某", role_type="嫌疑人", status="正常")
    assert is_caller_opening_role(suspect) is False


def test_generate_opening_utterances_fallback():
    case = models.Case(
        title="测试",
        case_type="邻里纠纷",
        background="楼道纠纷升级",
        structured_data=json.dumps({"conflict_points": ["打架斗殴"]}, ensure_ascii=False),
    )
    role = models.Role(name="张某", role_type="报警人", status="正常")
    scene = models.Scene(name="接警研判", description="", difficulty="中等", stages="[]")
    utterances, thought = generate_opening_utterances(case, role, scene)
    assert len(utterances) >= 1
    assert any("110" in item["content"] for item in utterances)
    assert thought


def test_redact_dispatch_brief_for_intake():
    scene = models.Scene(name="接警研判", dispatch_brief="详细案情不应展示", first_impression="现场印象")
    session = models.TrainingSession(current_stage="接警研判", current_emotion=50, current_trust=30)
    assert redact_dispatch_brief_for_student(scene, session) == INTAKE_MINIMAL_DISPATCH


def test_ensure_opening_turn_persists_messages(db_session):
    case = db_session.query(models.Case).first()
    scene = db_session.query(models.Scene).filter(models.Scene.case_id == case.id).first()
    role = db_session.query(models.Role).filter(models.Role.case_id == case.id).first()
    session = models.TrainingSession(
        user_id=db_session.query(models.User).filter(models.User.role == "student").first().id,
        scene_id=scene.id,
        current_stage="初始接触",
        current_emotion=80,
        current_trust=30,
        revealed_info=dump_runtime_state(load_runtime_state([])),
        status="active",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert should_generate_opening(scene, session, role, []) is True
    created = ensure_opening_turn(db_session, session, scene, case, role)
    db_session.commit()
    db_session.refresh(session)
    assert len(created) >= 1
    messages = db_session.query(models.Message).filter(models.Message.session_id == session.id).all()
    assert messages
    assert messages[0].role == "assistant"
    assert messages[0].speaker_name == role.name

    runtime = load_runtime_state(session.revealed_info)
    assert runtime.get("opening_delivered") is True
    assert runtime.get("dialogue_mode") == "caller_first"

    # idempotent
    again = ensure_opening_turn(db_session, session, scene, case, role)
    assert again == []
