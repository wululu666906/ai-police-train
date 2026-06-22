import base64
import json
from datetime import datetime
from statistics import mean, pstdev
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageStat
from sqlalchemy.orm import Session

import models


FRAME_SAMPLE_SECONDS = 3


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _decode_data_url(data_url: str) -> Image.Image:
    value = (data_url or "").strip()
    if "," in value and value.startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        raw = base64.b64decode(value)
        return Image.open(__import__("io").BytesIO(raw)).convert("RGB")
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid camera frame") from error


def _analyze_frame(frame_data_url: str) -> dict[str, Any]:
    image = _decode_data_url(frame_data_url)
    small = image.resize((96, 96))
    grayscale = small.convert("L")
    stat = ImageStat.Stat(grayscale)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])

    # Lightweight local prototype: keeps the data path runnable even before
    # EmotiEffLib/MediaPipe model files are provisioned in production.
    face_detected = brightness >= 18 and contrast >= 4
    tension_score = int(round(_clamp((contrast / 64) * 55 + (1 - abs(brightness - 132) / 132) * 25 + 20, 0, 100)))
    if not face_detected:
        emotion = "unknown"
        stability = 45
    elif tension_score >= 72:
        emotion = "tense"
        stability = 62
    elif contrast <= 18:
        emotion = "stable"
        stability = 86
    else:
        emotion = "hesitant"
        stability = 74

    gesture_label = "open_palm" if face_detected and contrast < 42 else "hands_off_camera"
    abnormal_motion = not face_detected or contrast > 82
    if abnormal_motion and face_detected:
        gesture_label = "abnormal_motion"

    return {
        "face": {
            "present": face_detected,
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
        },
        "micro_expression": {
            "emotion": emotion,
            "tension_score": tension_score,
            "stability_score": stability,
            "confidence": 0.58,
            "adapter": "lightweight-prototype",
        },
        "gesture": {
            "gesture_type": gesture_label,
            "normative": gesture_label == "open_palm",
            "abnormal": abnormal_motion,
            "adapter": "lightweight-prototype",
        },
    }


def _get_owned_session(db: Session, session_id: int, user: models.User) -> models.TrainingSession:
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if user.role != "admin":
        query = query.filter(models.TrainingSession.user_id == user.id)
    session = query.first()
    if not session:
        raise HTTPException(status_code=404, detail="Training session not found")
    return session


def record_event(
    db: Session,
    *,
    session: models.TrainingSession,
    event_type: str,
    category: str,
    label: str = "",
    score: float | None = None,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
) -> models.MultimodalEvent:
    event = models.MultimodalEvent(
        session_id=session.id,
        student_id=session.user_id,
        event_type=event_type,
        category=category,
        label=label or None,
        score=score,
        duration_ms=duration_ms,
        payload_json=_json_dumps(payload or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_frame(db: Session, *, session_id: int, user: models.User, frame_data_url: str) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, user)
    analysis = _analyze_frame(frame_data_url)

    face_payload = analysis["face"]
    micro_payload = analysis["micro_expression"]
    gesture_payload = analysis["gesture"]
    record_event(
        db,
        session=session,
        event_type="frame",
        category="face",
        label="present" if face_payload["present"] else "offline",
        score=1.0 if face_payload["present"] else 0.0,
        payload=face_payload,
    )
    record_event(
        db,
        session=session,
        event_type="frame",
        category="micro_expression",
        label=micro_payload["emotion"],
        score=float(micro_payload["tension_score"]),
        payload=micro_payload,
    )
    record_event(
        db,
        session=session,
        event_type="frame",
        category="gesture",
        label=gesture_payload["gesture_type"],
        score=1.0 if gesture_payload["normative"] else 0.0,
        payload=gesture_payload,
    )
    return analysis


def record_voice_event(
    db: Session,
    *,
    session_id: int,
    user: models.User,
    event_type: str,
    transcript: str = "",
    duration_ms: int | None = None,
    audio_level: float | None = None,
    repeated: bool = False,
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, user)
    payload = {
        "transcript": transcript.strip(),
        "audio_level": audio_level,
        "repeated": repeated,
    }
    label = "repeat" if repeated else event_type
    event = record_event(
        db,
        session=session,
        event_type=event_type,
        category="voice",
        label=label,
        score=audio_level,
        duration_ms=duration_ms,
        payload=payload,
    )
    return {"event_id": event.id, "status": "recorded"}


def _event_payload(event: models.MultimodalEvent) -> dict[str, Any]:
    payload = _safe_json_loads(event.payload_json, {})
    return payload if isinstance(payload, dict) else {}


def _time_label(index: int) -> str:
    seconds = index * FRAME_SAMPLE_SECONDS
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _risk_level(score: int) -> str:
    if score >= 85:
        return "low"
    if score >= 70:
        return "normal"
    if score >= 55:
        return "attention"
    return "high"


def _percent(part: int, total: int) -> int | None:
    if total <= 0:
        return None
    return int(round((part / total) * 100))


def _weighted_score(parts: list[tuple[int | None, float]]) -> int:
    available = [(score, weight) for score, weight in parts if isinstance(score, int)]
    if not available:
        return 0
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        return 0
    return int(round(sum(score * weight for score, weight in available) / total_weight))


def build_scene_performance_report(db: Session, session_id: int) -> dict[str, Any]:
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Training session not found")

    multimodal_events = (
        db.query(models.MultimodalEvent)
        .filter(models.MultimodalEvent.session_id == session_id)
        .order_by(models.MultimodalEvent.created_at.asc())
        .all()
    )
    face_events = (
        db.query(models.FaceVerificationEvent)
        .filter(models.FaceVerificationEvent.session_id == session_id)
        .order_by(models.FaceVerificationEvent.created_at.asc())
        .all()
    )

    frame_face_events = [event for event in multimodal_events if event.category == "face"]
    micro_events = [event for event in multimodal_events if event.category == "micro_expression"]
    gesture_events = [event for event in multimodal_events if event.category == "gesture"]
    voice_events = [event for event in multimodal_events if event.category == "voice"]

    passed_face = [event for event in face_events if event.status == "passed"]
    failed_face = [event for event in face_events if event.status == "failed"]
    monitor_face_events = [event for event in face_events if event.event_type != "verify"]
    failed_monitor_face = [event for event in monitor_face_events if event.status == "failed"]
    passed_monitor_face = [event for event in monitor_face_events if event.status == "passed"]
    offline_frames = [event for event in frame_face_events if event.label == "offline"]
    present_frames = [event for event in frame_face_events if event.label == "present"]
    abnormal_leave_count = len(offline_frames) + sum(
        1 for event in failed_face if any(keyword in str(event.reason or "") for keyword in ("未检测", "离开", "offline", "No face"))
    )
    face_sample_count = len(face_events) + len(frame_face_events)
    face_pass_rate = _percent(len(passed_face) + len(present_frames), face_sample_count)
    monitor_fail_rate = _percent(len(failed_monitor_face), len(monitor_face_events))
    leave_rate = _percent(len(offline_frames), len(frame_face_events))
    present_duration_seconds = len(present_frames) * FRAME_SAMPLE_SECONDS if present_frames else None
    reason_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    quality_issue_counts: dict[str, int] = {}
    for event in failed_face:
        reason_code = str(getattr(event, "reason_code", "") or "unknown")
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
        level = str(getattr(event, "abnormal_level", "") or "unknown")
        level_counts[level] = level_counts.get(level, 0) + 1
        payload = _safe_json_loads(getattr(event, "quality_json", ""), {})
        if isinstance(payload, dict):
            quality_code = str(payload.get("reason_code") or "")
            if quality_code:
                quality_issue_counts[quality_code] = quality_issue_counts.get(quality_code, 0) + 1

    tension_values = [float(event.score or 0) for event in micro_events if event.score is not None]
    if tension_values:
        avg_tension = mean(tension_values)
        volatility = pstdev(tension_values) if len(tension_values) > 1 else 0
        stability_score = int(round(_clamp(100 - volatility * 1.4 - max(0, avg_tension - 60) * 0.35, 0, 100)))
    else:
        avg_tension = None
        volatility = None
        stability_score = None
    tension_curve = [
        {"time": _time_label(index), "score": int(round(float(event.score or 0)))}
        for index, event in enumerate(micro_events[:60])
    ]
    emotion_counts: dict[str, int] = {}
    for event in micro_events:
        label = str(event.label or "unknown")
        emotion_counts[label] = emotion_counts.get(label, 0) + 1
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "暂无数据"

    normative_gestures = [event for event in gesture_events if event.label == "open_palm"]
    abnormal_gestures = [
        event for event in gesture_events if event.label in {"hands_off_camera", "frequent_leave", "abnormal_motion"}
    ]

    utterance_events = [event for event in voice_events if event.event_type in {"utterance_end", "hangup_tail"}]
    transcripts = [_event_payload(event).get("transcript", "") for event in utterance_events]
    repeated_count = sum(1 for event in voice_events if _event_payload(event).get("repeated") or event.label == "repeat")
    durations = [int(event.duration_ms or 0) for event in utterance_events if event.duration_ms]
    avg_duration_ms = int(mean(durations)) if durations else 0
    interruption_count = sum(1 for event in voice_events if event.event_type in {"interruption", "mute", "error"})
    complete_utterance_count = sum(1 for text in transcripts if len(str(text).strip()) >= 4)
    voice_completeness = int(round((complete_utterance_count / max(len(utterance_events), 1)) * 100)) if utterance_events else None
    continuous_expression = bool(len(utterance_events) >= 2 and interruption_count == 0) if utterance_events else None

    face_score = None
    if face_sample_count:
        face_score = 100
        if face_pass_rate is not None:
            face_score -= max(0, 100 - face_pass_rate) * 0.55
        if monitor_fail_rate is not None:
            face_score -= monitor_fail_rate * 0.35
        if leave_rate is not None:
            face_score -= leave_rate * 0.3
        face_score -= min(25, abnormal_leave_count * 4)
        if not passed_face:
            face_score -= 20
        face_score = int(_clamp(face_score, 0, 100))

    gesture_score = None
    if gesture_events:
        normative_rate = len(normative_gestures) / max(len(gesture_events), 1)
        abnormal_rate = len(abnormal_gestures) / max(len(gesture_events), 1)
        gesture_score = normative_rate * 75 + (1 - abnormal_rate) * 25
        gesture_score -= min(35, len(abnormal_gestures) * 3)
        gesture_score = int(_clamp(gesture_score, 0, 100))

    voice_score = None
    if utterance_events:
        voice_score = int(_clamp((voice_completeness or 0) - min(25, interruption_count * 8) - min(20, repeated_count * 6), 0, 100))

    behavior_score = _weighted_score([
        (face_score, 0.4),
        (stability_score, 0.2),
        (gesture_score, 0.2),
        (voice_score, 0.2),
    ])
    risk_tips = []
    abnormal_records = []
    if abnormal_leave_count:
        risk_tips.append("训练中存在离开镜头或身份核验异常")
        abnormal_records.append(f"异常离开/核验异常 {abnormal_leave_count} 次")
    if volatility is not None and volatility >= 18:
        risk_tips.append("情绪/压力波动较大")
        abnormal_records.append("压力曲线波动明显")
    if abnormal_gestures:
        risk_tips.append("存在离镜或异常动作记录")
        abnormal_records.append(f"异常动作 {len(abnormal_gestures)} 次")
    if repeated_count or interruption_count:
        risk_tips.append("语音表达存在中断或重复")
        abnormal_records.append(f"语音中断 {interruption_count} 次，重复 {repeated_count} 次")

    if not risk_tips:
        risk_tips.append("未发现明显实景行为风险")

    report = {
        "face": {
            "is_self": bool(passed_face) if face_events else None,
            "presence_duration_seconds": present_duration_seconds,
            "abnormal_leave_count": abnormal_leave_count if face_events or frame_face_events else None,
            "verification_pass_count": len(passed_face),
            "verification_fail_count": len(failed_face),
            "monitor_pass_count": len(passed_monitor_face),
            "monitor_fail_count": len(failed_monitor_face),
            "sample_count": face_sample_count,
            "pass_rate": face_pass_rate,
            "monitor_fail_rate": monitor_fail_rate,
            "leave_rate": leave_rate,
            "reason_counts": reason_counts,
            "abnormal_level_counts": level_counts,
            "quality_issue_counts": quality_issue_counts,
            "score": face_score,
            "has_data": bool(face_events or frame_face_events),
        },
        "micro_expression": {
            "dominant_emotion": dominant_emotion if micro_events else None,
            "stability_score": stability_score,
            "average_tension": int(round(avg_tension)) if avg_tension is not None else None,
            "tension_curve": tension_curve,
            "pressure_volatility": round(float(volatility), 2) if volatility is not None else None,
            "sample_count": len(micro_events),
            "score": stability_score,
            "pressure_analysis": "暂无数据" if not micro_events else ("压力波动较明显" if (volatility or 0) >= 18 else "压力波动处于可控范围"),
            "has_data": bool(micro_events),
        },
        "gesture": {
            "has_normative_communication_gesture": bool(normative_gestures) if gesture_events else None,
            "frequent_leave_camera": abnormal_leave_count >= 2 if gesture_events else None,
            "has_abnormal_action": bool(abnormal_gestures) if gesture_events else None,
            "gesture_types": list(dict.fromkeys(str(event.label or "") for event in gesture_events if event.label)),
            "abnormal_action_count": len(abnormal_gestures),
            "sample_count": len(gesture_events),
            "normative_rate": _percent(len(normative_gestures), len(gesture_events)),
            "abnormal_rate": _percent(len(abnormal_gestures), len(gesture_events)),
            "score": gesture_score,
            "has_data": bool(gesture_events),
        },
        "voice": {
            "completeness_score": voice_completeness,
            "continuous_expression": continuous_expression,
            "interruption_count": interruption_count,
            "repeat_count": repeated_count,
            "utterance_count": len(utterance_events),
            "average_utterance_duration_ms": avg_duration_ms,
            "score": voice_score,
            "has_data": bool(voice_events),
        },
        "overall": {
            "behavior_score": behavior_score,
            "risk_level": _risk_level(behavior_score),
            "score_weights": {"face": 0.4, "micro_expression": 0.2, "gesture": 0.2, "voice": 0.2},
            "risk_tips": risk_tips,
            "abnormal_records": abnormal_records,
            "generated_at": datetime.utcnow().isoformat(),
            "has_data": any(isinstance(score, int) for score in (face_score, stability_score, gesture_score, voice_score)),
        },
        "meta": {
            "sample_count": len(frame_face_events),
            "voice_event_count": len(voice_events),
            "adapter_status": "prototype",
        },
    }

    metric = (
        db.query(models.MultimodalSessionMetric)
        .filter(models.MultimodalSessionMetric.session_id == session_id)
        .first()
    )
    if not metric:
        metric = models.MultimodalSessionMetric(session_id=session.id, student_id=session.user_id)
    metric.summary_json = _json_dumps(report)
    metric.behavior_score = behavior_score
    metric.risk_level = report["overall"]["risk_level"]
    metric.updated_at = datetime.utcnow()
    db.add(metric)
    db.commit()
    return report


def append_scene_performance_report(db: Session, session_id: int, report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return report
    if report.get("scene_performance_report"):
        return report
    try:
        report["scene_performance_report"] = build_scene_performance_report(db, session_id)
    except Exception as error:
        report["scene_performance_report"] = {
            "face": {"is_self": None, "presence_duration_seconds": None, "abnormal_leave_count": None, "has_data": False},
            "micro_expression": {"stability_score": None, "tension_curve": [], "pressure_analysis": "暂无数据", "has_data": False},
            "gesture": {
                "has_normative_communication_gesture": None,
                "frequent_leave_camera": None,
                "has_abnormal_action": None,
                "has_data": False,
            },
            "voice": {
                "completeness_score": None,
                "continuous_expression": None,
                "interruption_count": None,
                "repeat_count": None,
                "has_data": False,
            },
            "overall": {
                "behavior_score": 0,
                "risk_level": "unknown",
                "risk_tips": ["实景表现数据暂不可用"],
                "abnormal_records": [str(error)],
                "generated_at": datetime.utcnow().isoformat(),
                "has_data": False,
            },
            "meta": {"adapter_status": "fallback"},
        }
    return report
