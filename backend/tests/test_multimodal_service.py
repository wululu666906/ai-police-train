import json
from datetime import datetime, timedelta

import models
from services.face_service import (
    count_session_failures,
    count_session_monitor_failures,
    count_session_monitor_failures_total,
    create_liveness_challenge,
    cosine_similarity,
    verify_frame,
)
from services.multimodal_service import append_scene_performance_report, build_scene_performance_report, record_event


def test_scene_performance_report_defaults_without_multimodal_data(db_session):
    user = models.User(username="multi_default", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="finished")
    db_session.add(session)
    db_session.commit()

    report = build_scene_performance_report(db_session, session.id)

    assert report["face"]["is_self"] is None
    assert report["face"]["abnormal_leave_count"] is None
    assert report["micro_expression"]["pressure_analysis"] == "暂无数据"
    assert report["voice"]["utterance_count"] == 0
    assert report["overall"]["behavior_score"] == 0


def test_scene_performance_report_aggregates_face_voice_and_behavior(db_session):
    user = models.User(username="multi_events", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="finished")
    db_session.add(session)
    db_session.commit()
    db_session.add(
        models.FaceVerificationEvent(
            session_id=session.id,
            student_id=user.id,
            event_type="verify",
            status="passed",
            reason="passed",
            failure_count=0,
            reason_code=None,
            abnormal_level=None,
        )
    )
    db_session.add(
        models.FaceVerificationEvent(
            session_id=session.id,
            student_id=user.id,
            event_type="heartbeat",
            status="failed",
            reason="low light",
            reason_code="low_light",
            abnormal_level="minor",
            quality_json=json.dumps({"reason_code": "low_light"}, ensure_ascii=False),
            failure_count=1,
        )
    )
    db_session.commit()

    record_event(db_session, session=session, event_type="frame", category="face", label="present", score=1)
    record_event(db_session, session=session, event_type="frame", category="face", label="offline", score=0)
    record_event(
        db_session,
        session=session,
        event_type="frame",
        category="micro_expression",
        label="tense",
        score=78,
        payload={"tension_score": 78},
    )
    record_event(
        db_session,
        session=session,
        event_type="frame",
        category="micro_expression",
        label="stable",
        score=42,
        payload={"tension_score": 42},
    )
    record_event(db_session, session=session, event_type="frame", category="gesture", label="open_palm", score=1)
    record_event(
        db_session,
        session=session,
        event_type="utterance_end",
        category="voice",
        label="utterance_end",
        duration_ms=1800,
        payload={"transcript": "请您先说明情况", "repeated": False},
    )
    record_event(
        db_session,
        session=session,
        event_type="utterance_end",
        category="voice",
        label="repeat",
        duration_ms=1600,
        payload={"transcript": "请您先说明情况", "repeated": True},
    )

    report = build_scene_performance_report(db_session, session.id)

    assert report["face"]["is_self"] is True
    assert report["face"]["presence_duration_seconds"] == 3
    assert report["face"]["abnormal_leave_count"] == 1
    assert report["face"]["pass_rate"] is not None
    assert report["face"]["score"] is not None
    assert report["face"]["reason_counts"]["low_light"] == 1
    assert report["face"]["abnormal_level_counts"]["minor"] == 1
    assert report["micro_expression"]["stability_score"] > 0
    assert report["gesture"]["has_normative_communication_gesture"] is True
    assert report["gesture"]["normative_rate"] is not None
    assert report["gesture"]["score"] is not None
    assert report["voice"]["utterance_count"] == 2
    assert report["voice"]["repeat_count"] == 1
    assert report["overall"]["behavior_score"] > 0


def test_append_scene_performance_report_preserves_existing_fields(db_session):
    user = models.User(username="multi_append", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="finished")
    db_session.add(session)
    db_session.commit()

    base_report = {"total_score": 88, "evaluation_meta": {"scoring_version": "adaptive_v1"}}
    result = append_scene_performance_report(db_session, session.id, base_report)

    assert result["total_score"] == 88
    assert result["evaluation_meta"]["scoring_version"] == "adaptive_v1"
    assert "scene_performance_report" in result

    stored = db_session.query(models.MultimodalSessionMetric).filter_by(session_id=session.id).first()
    assert stored is not None
    assert json.loads(stored.summary_json)["overall"]["behavior_score"] == 0


def test_face_failure_count_uses_consecutive_failures(db_session):
    user = models.User(username="face_fail", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    db_session.add(
        models.FaceVerificationEvent(
            session_id=session.id,
            student_id=user.id,
            event_type="heartbeat",
            status="failed",
            reason="no face detected",
            failure_count=1,
            created_at=datetime.utcnow(),
        )
    )
    db_session.add(
        models.FaceVerificationEvent(
            session_id=session.id,
            student_id=user.id,
            event_type="heartbeat",
            status="failed",
            reason="no face detected",
            failure_count=2,
            created_at=datetime.utcnow() + timedelta(seconds=1),
        )
    )
    db_session.add(
        models.FaceVerificationEvent(
            session_id=session.id,
            student_id=user.id,
            event_type="heartbeat",
            status="passed",
            reason="passed",
            failure_count=0,
            created_at=datetime.utcnow() + timedelta(seconds=2),
        )
    )
    db_session.commit()

    assert count_session_failures(db_session, session.id) == 0


def test_face_monitor_total_failures_do_not_clear_after_pass(db_session):
    user = models.User(username="face_total_fail", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    base_time = datetime.utcnow()
    events = [
        ("failed", 1),
        ("failed", 2),
        ("passed", 2),
    ]
    for index, (status, failure_count) in enumerate(events):
        db_session.add(
            models.FaceVerificationEvent(
                session_id=session.id,
                student_id=user.id,
                event_type="heartbeat",
                status=status,
                reason="no face detected" if status == "failed" else "passed",
                failure_count=failure_count,
                created_at=base_time + timedelta(seconds=index),
            )
        )
    db_session.commit()

    assert count_session_monitor_failures(db_session, session.id) == 0
    assert count_session_monitor_failures_total(db_session, session.id) == 2


def test_face_verify_failures_do_not_auto_finish_session(db_session):
    user = models.User(username="face_verify_retry", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    last_result = None
    for _ in range(5):
        last_result = verify_frame(
            db_session,
            session=session,
            frame_data_url="data:image/jpeg;base64,",
            event_type="verify",
            liveness_score=1.0,
        )

    db_session.refresh(session)
    assert session.status == "active"
    assert last_result["status"] == "failed"
    assert last_result["terminated"] is False
    assert count_session_failures(db_session, session.id) == 5
    assert count_session_monitor_failures(db_session, session.id) == 0
    assert count_session_monitor_failures_total(db_session, session.id) == 0


def test_old_face_profile_embedding_is_compatible(db_session):
    user = models.User(username="face_legacy", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    embedding = [0.0] * 512
    embedding[0] = 1.0
    profile = models.FaceProfile(
        student_id=user.id,
        face_embedding=json.dumps(embedding),
        embedding_model="insightface:buffalo_l",
    )
    db_session.add(profile)
    db_session.commit()

    from services.face_service import _profile_embeddings

    templates = _profile_embeddings(profile)
    assert len(templates) == 1
    assert cosine_similarity(templates[0], embedding) == 1.0


def test_liveness_challenge_requires_all_actions():
    challenge = create_liveness_challenge(session_id=9991, student_id=9992)
    from services.face_service import validate_liveness_challenge

    passed, payload, _ = validate_liveness_challenge(
        session_id=9991,
        student_id=9992,
        challenge_id=challenge["challenge_id"],
        liveness_actions=[{"action": challenge["actions"][0], "passed": True}],
    )

    assert passed is False
    assert payload["missing_actions"]
