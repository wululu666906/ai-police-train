import json

import models
import services.opening_turn_service as opening_service
from services.opening_turn_service import (
    INTAKE_MINIMAL_DISPATCH,
    ensure_opening_turn,
    infer_session_scene_kind,
    redact_dispatch_brief_for_student,
    resolve_dialogue_mode,
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


def test_redact_dispatch_brief_for_intake():
    scene = models.Scene(name="接警研判", dispatch_brief="详细案情不应展示", first_impression="现场印象")
    session = models.TrainingSession(current_stage="接警研判", current_emotion=50, current_trust=30)
    assert redact_dispatch_brief_for_student(scene, session) == INTAKE_MINIMAL_DISPATCH


def test_ensure_opening_turn_uses_independent_model_and_is_idempotent(db_session, monkeypatch):
    case = db_session.query(models.Case).first()
    scene = db_session.query(models.Scene).filter(models.Scene.case_id == case.id).first()
    role = db_session.query(models.Role).filter(models.Role.case_id == case.id).first()
    student = db_session.query(models.User).filter(models.User.role == "student").first()
    session = models.TrainingSession(
        user_id=student.id,
        scene_id=scene.id,
        current_stage="初始接触",
        current_emotion=50,
        current_trust=30,
        revealed_info=dump_runtime_state(load_runtime_state([])),
        status="active",
    )
    db_session.add(session)
    scene.opening_config = json.dumps({"enabled": True, "speaker_role_ids": [role.id]})
    db_session.commit()
    db_session.refresh(session)

    model_payload = '{"utterances":[{"content":"我先说明一下现场情况。"}],"inner_thought":"主动说明"}'
    generation_kwargs = {}

    def fake_completion(**kwargs):
        generation_kwargs.update(kwargs)
        return object(), {"attempts": [{"status": "success"}]}

    monkeypatch.setattr(opening_service, "create_roleplay_json_completion", fake_completion)
    monkeypatch.setattr(opening_service, "extract_message_text", lambda _: model_payload)
    created = ensure_opening_turn(db_session, session, scene, case, role)
    db_session.commit()

    assert len(created) == 1
    assert created[0].role == "assistant"
    assert created[0].content == "我先说明一下现场情况。"
    assert len(created[0].content) <= opening_service.ROLE_REPLY_MAX_CHARS
    assert generation_kwargs["return_trace"] is True
    assert generation_kwargs["max_tokens"] >= 800
    assert load_runtime_state(session.revealed_info)["opening_delivered"] is True
    assert ensure_opening_turn(db_session, session, scene, case, role) == []
    db_session.query(models.Message).filter(models.Message.session_id == session.id).delete()
    db_session.delete(session)
    db_session.commit()


def test_scene_opening_defaults_to_one_role_and_honors_explicit_multiple_roles(monkeypatch):
    scene = models.Scene(name="现场排查", description="核查现场线索")
    roles = [
        models.Role(id=11, name="甲", role_type="证人", status="正常"),
        models.Role(id=12, name="乙", role_type="证人", status="正常"),
    ]

    monkeypatch.setattr(
        opening_service,
        "generate_opening_utterances",
        lambda _case, role, _scene, **_kwargs: ([{"content": f"我是{role.name}。"}], ""),
    )

    default_rows = opening_service.generate_scene_opening_utterances(None, scene, roles, {})
    configured_rows = opening_service.generate_scene_opening_utterances(
        None,
        scene,
        roles,
        {"speaker_role_ids": [11, 12]},
    )

    assert [row["role"].id for row in default_rows] == [11]
    assert [row["role"].id for row in configured_rows] == [11, 12]


def test_scene_opening_fallback_uses_role_fact_instead_of_shared_scene_template():
    rows = opening_service._fallback_opening_utterances({
        "role_name": "王某",
        "role_facts": ["2012年冬季，我在鬼山坡种植了杉木苗。"],
        "opening_behavior": "现场人员主动说明",
    })

    assert rows == [{"content": "我是王某。我能确认的是，2012年冬季，我在鬼山坡种植了杉木苗。"}]
