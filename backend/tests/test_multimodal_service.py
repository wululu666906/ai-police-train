import json
from datetime import datetime, timedelta

import models
from services.face_service import (
    count_session_failures,
    count_session_failures_total,
    count_session_monitor_failures,
    count_session_monitor_failures_total,
    create_liveness_challenge,
    cosine_similarity,
    _liveness_probability_threshold_to_logit,
    verify_frame,
)
from services.multimodal_service import append_scene_performance_report, build_scene_performance_report, get_engine_status, record_event, record_frame


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
    assert report["overall"]["behavior_score"] == 0


def test_scene_performance_report_aggregates_face_and_behavior(db_session):
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
    report = build_scene_performance_report(db_session, session.id)

    assert report["face"]["is_self"] is True
    assert report["face"]["presence_duration_seconds"] == 1
    assert report["face"]["abnormal_leave_count"] == 1
    assert report["face"]["pass_rate"] is not None
    assert report["face"]["score"] is not None
    assert report["face"]["reason_counts"]["low_light"] == 1
    assert report["face"]["abnormal_level_counts"]["minor"] == 1
    assert report["micro_expression"]["stability_score"] > 0
    assert report["gesture"]["has_normative_communication_gesture"] is True
    assert report["gesture"]["normative_rate"] is not None
    assert report["gesture"]["score"] is not None
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


def test_append_scene_performance_report_rebuilds_legacy_scene_report(db_session):
    user = models.User(username="multi_legacy_scene", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="finished")
    db_session.add(session)
    db_session.commit()

    base_report = {
        "total_score": 76,
        "scene_performance_report": {
            "overall": {"behavior_score": 55},
            "scores": {"behavior_score": 55},
        },
    }
    result = append_scene_performance_report(db_session, session.id, base_report)
    scene_report = result["scene_performance_report"]

    assert scene_report["schema_version"] == "scene_performance_report/v2"
    assert "degradation" in scene_report
    assert "adapter_status" in scene_report
    assert set(scene_report["tool_evidence"]) >= {"insightface", "deepface", "opencv", "mediapipe"}


def test_multimodal_frame_accepts_client_signals_and_scores(db_session):
    user = models.User(username="multi_client_signals", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    from PIL import Image
    import base64
    import io

    image = Image.new("RGB", (24, 24), color=(120, 128, 132))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    frame = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    result = record_frame(
        db_session,
        session_id=session.id,
        user=user,
        frame_data_url=frame,
        client_signals={
            "hands": [{"landmarks": [{"x": 0.5, "y": 0.5, "z": 0, "visibility": 1} for _ in range(21)], "score": 0.9}],
            "pose": {"landmarks": [{"x": 0.5, "y": 0.5, "z": 0, "visibility": 0.8} for _ in range(33)]},
            "motion": {"motion_score": 0.2, "head_offset": 0.1, "gaze_offset": 0.1},
            "model_status": {"mediapipe": "ready"},
        },
    )

    assert result["scores"]["final_score"] == round(
        result["scores"]["behavior_score"] * 0.35
        + result["scores"]["face_score"] * 0.30
        + result["scores"]["attention_score"] * 0.35
    )
    assert result["gesture"]["adapter"] == "client_mediapipe"
    assert result["degradation"]["level"] in {1, 2}


def test_multimodal_frame_counts_all_frame_samples_in_tool_evidence(db_session):
    user = models.User(username="multi_sample_parity", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    from PIL import Image
    import base64
    import io

    image = Image.new("RGB", (24, 24), color=(140, 135, 130))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    frame = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    record_frame(
        db_session,
        session_id=session.id,
        user=user,
        frame_data_url=frame,
        client_signals={"hands": [], "pose": {"landmarks": []}, "motion": {}, "model_status": {"mediapipe": "ready"}},
    )
    record_frame(
        db_session,
        session_id=session.id,
        user=user,
        frame_data_url=frame,
        client_signals={"hands": [], "pose": {"landmarks": []}, "motion": {}, "model_status": {"mediapipe": "ready"}},
    )

    report = build_scene_performance_report(db_session, session.id)

    assert report["tool_evidence"]["insightface"]["evidence_count"] >= 2
    assert report["tool_evidence"]["deepface"]["evidence_count"] >= 2
    assert report["tool_evidence"]["mediapipe"]["evidence_count"] >= 2
    assert report["meta"]["deepface_sample_count"] >= 2
    assert report["meta"]["mediapipe_sample_count"] >= 2


def test_multimodal_report_exposes_tool_evidence(db_session):
    user = models.User(username="multi_tool_evidence", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="finished")
    db_session.add(session)
    db_session.commit()

    record_event(db_session, session=session, event_type="frame", category="face", label="present", score=1, payload={"score": 82})
    record_event(db_session, session=session, event_type="frame", category="attention", label="focused", score=88, payload={"score": 88})
    record_event(
        db_session,
        session=session,
        event_type="frame",
        category="gesture",
        label="structured_pose",
        score=90,
        payload={"continuity_score": 90, "signal_summary": {"has_mediapipe": True, "hand_count": 1}},
    )
    record_event(db_session, session=session, event_type="frame", category="micro_expression", label="stable", score=35)

    report = build_scene_performance_report(db_session, session.id)

    assert set(report["tool_evidence"]) >= {"insightface", "deepface", "opencv", "mediapipe"}
    assert report["tool_evidence"]["mediapipe"]["status"] == "active"
    assert report["tool_evidence"]["mediapipe"]["evidence_count"] == 1


def test_multimodal_engine_status_reports_fallback():
    status = get_engine_status()

    assert status["fallback"]["available"] is True
    assert "deepface" in status


def test_face_auto_termination_uses_multimodal_guard_reason(db_session, monkeypatch):
    user = models.User(username="face_guard_reason", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    from services import face_service

    monkeypatch.setattr(
        face_service,
        "evaluate_session",
        lambda db, session_id, user_id, force_recompute=False: {
            "total_score": 76,
            "grade_level": "合格",
            "evaluation_meta": {"scoring_version": "adaptive_v1"},
        },
    )
    monkeypatch.setattr(face_service, "sync_assignment_submission_for_session", lambda *args, **kwargs: None)

    report = face_service._finalize_face_termination(
        db_session,
        session=session,
        failure_count=5,
        reason="no face detected",
    )

    assert report["termination_reason"] == "multimodal_guard_finished"
    assert report["face_monitor"]["termination_reason"] == "face_verification_failed"
    assert report["total_score"] == 76


def test_face_auto_termination_report_has_time_fields(db_session, monkeypatch):
    user = models.User(username="face_guard_time", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    from services import face_service
    from services.evaluation_service import finalize_evaluation_report

    def fake_evaluate(db, session_id, user_id, force_recompute=False):
        return finalize_evaluation_report(
            {"total_score": 80, "scores": [], "evaluation_meta": {}},
            session,
            None,
            None,
            ["请说明现场情况"],
        )

    monkeypatch.setattr(face_service, "evaluate_session", fake_evaluate)
    monkeypatch.setattr(face_service, "sync_assignment_submission_for_session", lambda *args, **kwargs: None)

    report = face_service._finalize_face_termination(
        db_session,
        session=session,
        failure_count=5,
        reason="no face detected",
    )
    header = report["evaluation_meta"]["report_header"]

    assert report["evaluated_at"]
    assert header["finished_at"]
    assert isinstance(header["duration_seconds"], int)


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


def test_face_failure_total_counts_all_failed_events(db_session):
    user = models.User(username="face_total_all", hashed_password="x", role="student")
    db_session.add(user)
    db_session.commit()
    session = models.TrainingSession(user_id=user.id, scene_id=1, status="active")
    db_session.add(session)
    db_session.commit()

    events = [
        ("heartbeat", "failed"),
        ("verify", "failed"),
        ("heartbeat", "passed"),
        ("heartbeat", "failed"),
    ]
    for index, (event_type, status) in enumerate(events):
        db_session.add(
            models.FaceVerificationEvent(
                session_id=session.id,
                student_id=user.id,
                event_type=event_type,
                status=status,
                reason="no face detected" if status == "failed" else "passed",
                failure_count=index + 1,
                created_at=datetime.utcnow() + timedelta(seconds=index),
            )
        )
    db_session.commit()

    assert count_session_failures_total(db_session, session.id) == 3
    assert count_session_failures(db_session, session.id) == 1
    assert count_session_monitor_failures(db_session, session.id) == 1


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


def test_liveness_threshold_uses_vendor_logit_semantics():
    assert round(_liveness_probability_threshold_to_logit(0.50), 6) == 0
    assert round(_liveness_probability_threshold_to_logit(0.60), 3) == 0.405
