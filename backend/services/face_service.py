import base64
import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy.orm import Session

import models
from services.classroom_service import sync_assignment_submission_for_session
from services.evaluation_service import evaluate_session
from services.multimodal_service import append_scene_performance_report


FACE_SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.72"))
FACE_HEARTBEAT_SIMILARITY_THRESHOLD = float(os.getenv("FACE_HEARTBEAT_SIMILARITY_THRESHOLD", "0.68"))
FACE_LIVENESS_THRESHOLD = float(os.getenv("FACE_LIVENESS_THRESHOLD", "0.55"))
FACE_MAX_FAILURES = int(os.getenv("FACE_MAX_FAILURES", "5"))
FACE_SERIOUS_MAX_FAILURES = int(os.getenv("FACE_SERIOUS_MAX_FAILURES", "5"))
FACE_VOTE_WINDOW = int(os.getenv("FACE_VOTE_WINDOW", "3"))
FACE_VOTE_FAIL_LIMIT = int(os.getenv("FACE_VOTE_FAIL_LIMIT", "2"))
FACE_CONSECUTIVE_MAX_FAILURES = int(os.getenv("FACE_CONSECUTIVE_MAX_FAILURES", "5"))
FACE_CHALLENGE_TURN_DELTA = float(os.getenv("FACE_CHALLENGE_TURN_DELTA", "0.055"))
FACE_CHALLENGE_DISTANCE_DELTA = float(os.getenv("FACE_CHALLENGE_DISTANCE_DELTA", "0.18"))
FACE_CHALLENGE_CONSECUTIVE_HITS = int(os.getenv("FACE_CHALLENGE_CONSECUTIVE_HITS", "3"))
FACE_CHALLENGE_BLINK_SCORE = float(os.getenv("FACE_CHALLENGE_BLINK_SCORE", "0.45"))
FACE_ENGINE_REQUIRED = os.getenv("FACE_ENGINE_REQUIRED", "1").strip().lower() in {"1", "true", "yes", "on"}
FACE_IMAGE_DIR = Path(os.getenv("FACE_IMAGE_DIR", Path(__file__).resolve().parents[1] / "static" / "face_profiles"))
INSIGHTFACE_MODEL_DIR = os.getenv(
    "INSIGHTFACE_MODEL_DIR",
    str(Path.home() / ".cache" / "ai-police-sim" / "insightface_models"),
)
EMBEDDING_MODEL = os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l")

_face_app = None
_face_engine_error = ""
_challenge_store: dict[str, dict[str, Any]] = {}


def _face_service_unavailable_detail(error: Exception | str) -> str:
    return f"人脸识别模型暂不可用，请确认人脸识别依赖和模型文件已正确安装后重试。原始错误：{error}"


def _is_face_engine_unavailable(error: HTTPException | Exception | str) -> bool:
    detail = getattr(error, "detail", error)
    text = str(detail or "").lower()
    return "face engine unavailable" in text or "insightface" in text or "onnx" in text or "模型暂不可用" in text or "model" in text


def localize_face_reason(reason: Any) -> str:
    text = str(reason or "").strip()
    lowered = text.lower()
    if not text:
        return "人脸核验异常"
    if "insightface unavailable" in lowered:
        return "人脸识别依赖未安装或不可用，请先检查人脸识别配置。"
    if "model init failed" in lowered:
        return "人脸识别模型初始化失败，请检查模型文件和运行环境。"
    if "invalid image" in lowered:
        return "图片格式无效，请上传清晰的本人正脸照片。"
    if "invalid camera frame" in lowered:
        return "摄像头画面格式无效，请刷新页面或重新开启摄像头后重试。"
    if "no face detected" in lowered or "no face" in lowered:
        return "未检测到人脸，请将本人面部置于圆形识别区域内。"
    if "multiple faces" in lowered or "multiple" in lowered:
        return "检测到多人入镜，请保持单人面对摄像头。"
    if "embedding extraction" in lowered:
        return "人脸特征提取失败，请保持正脸、光线充足后重试。"
    if "please choose a face photo" in lowered:
        return "请选择本人正脸照片。"
    if "image must not exceed" in lowered:
        return "图片大小不能超过 8MB。"
    if "invalid face profile" in lowered:
        return "人脸档案无效，请在管理端重新注册人脸照片。"
    if "no registered face profile" in lowered or "registered face profile" in lowered:
        return "当前账号尚未在管理端注册人脸档案。"
    if "liveness failed" in lowered or "liveness" in lowered:
        return "活体检测未通过，请本人正对摄像头并保持自然动作。"
    if "face mismatch" in lowered or "mismatch" in lowered:
        return "当前人脸与注册学员不一致，请确认由本人参加训练。"
    if lowered == "passed":
        return "身份验证通过"
    if "unknown evaluator error" in lowered:
        return "评估服务异常，系统已生成异常终止说明。"
    return text


@dataclass
class FaceExtraction:
    embedding: list[float]
    face_count: int
    detection_score: float
    bbox: list[float]
    quality: dict[str, Any]


def _load_engine():
    global _face_app, _face_engine_error
    if _face_app is not None:
        return _face_app
    try:
        from insightface.app import FaceAnalysis
    except Exception as error:
        _face_engine_error = _face_service_unavailable_detail(error)
        raise HTTPException(status_code=503, detail=_face_engine_error)

    try:
        app = FaceAnalysis(name=EMBEDDING_MODEL, root=INSIGHTFACE_MODEL_DIR, providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _face_app = app
        _face_engine_error = ""
        return app
    except Exception as error:
        _face_engine_error = _face_service_unavailable_detail(error)
        raise HTTPException(status_code=503, detail=_face_engine_error)


def engine_status() -> dict[str, Any]:
    model_path = Path(INSIGHTFACE_MODEL_DIR) / "models" / EMBEDDING_MODEL
    expected_files = ["det_10g.onnx", "w600k_r50.onnx"]
    return {
        "engine": "insightface",
        "model": EMBEDDING_MODEL,
        "model_dir": INSIGHTFACE_MODEL_DIR,
        "model_path": str(model_path),
        "model_files_ready": all((model_path / filename).exists() for filename in expected_files),
        "expected_files": expected_files,
        "engine_required": FACE_ENGINE_REQUIRED,
        "degraded_allowed": not FACE_ENGINE_REQUIRED,
        "loaded": _face_app is not None,
        "last_error": _face_engine_error,
        "similarity_threshold": FACE_SIMILARITY_THRESHOLD,
        "heartbeat_similarity_threshold": FACE_HEARTBEAT_SIMILARITY_THRESHOLD,
        "liveness_threshold": FACE_LIVENESS_THRESHOLD,
        "max_failures": FACE_MAX_FAILURES,
        "challenge_turn_delta": FACE_CHALLENGE_TURN_DELTA,
        "challenge_distance_delta": FACE_CHALLENGE_DISTANCE_DELTA,
        "challenge_consecutive_hits": FACE_CHALLENGE_CONSECUTIVE_HITS,
        "challenge_blink_score": FACE_CHALLENGE_BLINK_SCORE,
    }


def create_liveness_challenge(session_id: int, student_id: int) -> dict[str, Any]:
    actions = ["blink", random.choice(["turn_left", "turn_right"])]
    challenge_id = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    _challenge_store[challenge_id] = {
        "session_id": session_id,
        "student_id": student_id,
        "actions": actions,
        "baseline": None,
        "completed": {},
        "hits": {},
        "expires_at": expires_at,
    }
    return {
        "challenge_id": challenge_id,
        "actions": actions,
        "expires_at": expires_at.isoformat(),
        "mode": "action_challenge",
        "notice": "当前为动作挑战活体，不是金融级红外/深度活体。",
    }


def validate_liveness_challenge(
    *,
    session_id: int,
    student_id: int,
    challenge_id: str | None,
    liveness_actions: list[dict[str, Any]] | None,
) -> tuple[bool, dict[str, Any], str]:
    if not challenge_id:
        return False, {"mode": "action_challenge", "passed": False, "reason": "missing_challenge"}, "缺少活体挑战，请重新获取验证动作。"
    challenge = _challenge_store.get(challenge_id)
    if not challenge:
        return False, {"mode": "action_challenge", "passed": False, "reason": "invalid_challenge"}, "活体挑战已失效，请重新验证。"
    if challenge["session_id"] != session_id or challenge["student_id"] != student_id:
        return False, {"mode": "action_challenge", "passed": False, "reason": "challenge_mismatch"}, "活体挑战与当前会话不匹配。"
    if datetime.utcnow() > challenge["expires_at"]:
        _challenge_store.pop(challenge_id, None)
        return False, {"mode": "action_challenge", "passed": False, "reason": "challenge_expired"}, "活体挑战已过期，请重新验证。"

    completed = {
        str(item.get("action")): bool(item.get("passed"))
        for item in (liveness_actions or [])
        if isinstance(item, dict)
    }
    required = challenge["actions"]
    missing = [action for action in required if not completed.get(action)]
    payload = {
        "mode": "action_challenge",
        "challenge_id": challenge_id,
        "required_actions": required,
        "completed_actions": completed,
        "passed": not missing,
        "missing_actions": missing,
    }
    if missing:
        return False, payload, "活体动作未完成，请按提示完成眨眼、转头或张嘴动作。"
    _challenge_store.pop(challenge_id, None)
    return True, payload, "活体动作验证通过"


def update_liveness_challenge_from_quality(
    *,
    session_id: int,
    student_id: int,
    challenge_id: str | None,
    quality: dict[str, Any],
) -> tuple[bool, dict[str, Any], str]:
    if not challenge_id:
        return False, {"mode": "server_action_challenge", "passed": False, "reason": "missing_challenge"}, "缺少活体挑战，请重新开始验证。"
    challenge = _challenge_store.get(challenge_id)
    if not challenge:
        return False, {"mode": "server_action_challenge", "passed": False, "reason": "invalid_challenge"}, "活体挑战已失效，请重新开始验证。"
    if challenge["session_id"] != session_id or challenge["student_id"] != student_id:
        return False, {"mode": "server_action_challenge", "passed": False, "reason": "challenge_mismatch"}, "活体挑战与当前会话不匹配。"
    if datetime.utcnow() > challenge["expires_at"]:
        _challenge_store.pop(challenge_id, None)
        return False, {"mode": "server_action_challenge", "passed": False, "reason": "challenge_expired"}, "活体挑战已过期，请重新开始验证。"

    required = list(challenge.get("actions") or [])
    bbox = quality.get("bbox") or [0, 0, 0, 0]
    frame_width = float(quality.get("frame_width") or 640)
    x1, _y1, x2, _y2 = [float(item) for item in bbox[:4]]
    center_x = ((x1 + x2) / 2) / max(frame_width, 1)
    area_ratio = float(quality.get("face_area_ratio") or 0)
    client_quality = quality.get("client_quality") if isinstance(quality.get("client_quality"), dict) else {}
    client_liveness_actions = client_quality.get("liveness_actions") if isinstance(client_quality, dict) else None
    client_completed = {
        str(item.get("action")): bool(item.get("passed"))
        for item in (client_liveness_actions or [])
        if isinstance(item, dict)
    }
    blink_score = float(client_quality.get("blink_score") or 0)

    if not challenge.get("baseline"):
        challenge["baseline"] = {"center_x": center_x, "area_ratio": area_ratio}
        payload = {
            "mode": "server_action_challenge",
            "challenge_id": challenge_id,
            "required_actions": required,
            "completed_actions": {},
            "passed": False,
            "missing_actions": required,
        }
        return False, payload, "已检测到人脸，请按提示完成动作。"

    baseline = challenge["baseline"]
    completed = dict(challenge.get("completed") or {})
    hits = dict(challenge.get("hits") or {})
    base_x = float(baseline.get("center_x") or 0.5)
    base_area = max(float(baseline.get("area_ratio") or area_ratio), 0.001)
    # The camera preview is mirrored for the learner, so left/right challenge labels
    # are interpreted from the learner's perspective instead of the raw image axis.
    action_matched = {
        "blink": client_completed.get("blink") or blink_score >= FACE_CHALLENGE_BLINK_SCORE,
        "turn_left": center_x > base_x + FACE_CHALLENGE_TURN_DELTA,
        "turn_right": center_x < base_x - FACE_CHALLENGE_TURN_DELTA,
        "move_closer": area_ratio > base_area * (1 + FACE_CHALLENGE_DISTANCE_DELTA),
        "move_farther": area_ratio < base_area * (1 - FACE_CHALLENGE_DISTANCE_DELTA),
    }
    for action in required:
        if action_matched.get(action):
            hits[action] = hits.get(action, 0) + 1
        else:
            hits[action] = 0
    for action, count in hits.items():
        if count >= FACE_CHALLENGE_CONSECUTIVE_HITS:
            completed[action] = True
    challenge["hits"] = hits
    challenge["completed"] = completed

    missing = [action for action in required if not completed.get(action)]
    payload = {
        "mode": "server_action_challenge",
        "challenge_id": challenge_id,
        "required_actions": required,
        "completed_actions": completed,
        "passed": not missing,
        "missing_actions": missing,
    }
    if missing:
        return False, payload, "动作未完成，请继续按提示调整。"
    _challenge_store.pop(challenge_id, None)
    return True, payload, "活体动作验证通过。"


def _image_to_array(raw: bytes) -> np.ndarray:
    try:
        image = Image.open(__import__("io").BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="图片格式无效，请上传清晰的本人正脸照片。")
    return np.asarray(image)


def _enhance_frame_for_face_detection(frame: np.ndarray) -> np.ndarray:
    image = Image.fromarray(frame).convert("RGB")
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Contrast(image).enhance(1.25)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3))
    return np.asarray(image)


def _is_circular_visible_region(quality: dict[str, Any]) -> bool:
    client_quality = quality.get("client_quality")
    return isinstance(client_quality, dict) and client_quality.get("visible_region") == "circle"


def _quality_reason(quality: dict[str, Any]) -> tuple[str, str, str] | None:
    center_limit = 0.44 if _is_circular_visible_region(quality) else 0.34
    if quality.get("face_area_ratio", 0) < 0.055:
        return ("face_too_small", "人脸占比过小，请靠近摄像头并置于识别框内。", "minor")
    if quality.get("center_offset", 1) > center_limit:
        return ("face_off_center", "人脸偏离识别区域中心，请正对摄像头。", "medium")
    if quality.get("brightness", 0) < 42:
        return ("low_light", "光线不足，请面向光源或提高环境亮度。", "minor")
    if quality.get("detection_score", 0) < 0.45:
        return ("low_detection_confidence", "人脸检测置信度较低，请调整角度和光线。", "minor")
    return None


def _frame_quality(frame: np.ndarray, face: Any, face_count: int) -> dict[str, Any]:
    height, width = frame.shape[:2]
    bbox = np.asarray(getattr(face, "bbox", [0, 0, width, height]), dtype=np.float32)
    x1, y1, x2, y2 = [float(item) for item in bbox[:4]]
    face_width = max(0.0, x2 - x1)
    face_height = max(0.0, y2 - y1)
    area_ratio = (face_width * face_height) / max(float(width * height), 1.0)
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    center_offset = max(abs(center_x - width / 2) / max(width / 2, 1), abs(center_y - height / 2) / max(height / 2, 1))
    gray = np.asarray(Image.fromarray(frame).convert("L"), dtype=np.float32)
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    blur = float(np.var(gray[:-1, :-1] - gray[1:, 1:])) if gray.shape[0] > 1 and gray.shape[1] > 1 else 0.0
    quality = {
        "frame_width": width,
        "frame_height": height,
        "bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
        "face_area_ratio": round(area_ratio, 4),
        "center_offset": round(float(center_offset), 4),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "blur": round(blur, 2),
        "face_count": face_count,
        "detection_score": round(float(getattr(face, "det_score", 0) or 0), 4),
    }
    reason = _quality_reason(quality)
    quality["passed"] = reason is None
    if reason:
        quality["reason_code"], quality["reason"], quality["abnormal_level"] = reason
    return quality


def _merge_client_quality(quality: dict[str, Any], client_quality: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**quality, "client_quality": client_quality or {}}
    reason = _quality_reason(merged)
    merged["passed"] = reason is None
    if reason:
        merged["reason_code"], merged["reason"], merged["abnormal_level"] = reason
    else:
        merged.pop("reason_code", None)
        merged.pop("reason", None)
        merged.pop("abnormal_level", None)
    return merged


def decode_data_url(data_url: str) -> bytes:
    value = (data_url or "").strip()
    if "," in value and value.startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value)
    except Exception:
        raise HTTPException(status_code=400, detail="摄像头画面格式无效，请刷新页面或重新开启摄像头后重试。")


def extract_face(raw: bytes) -> FaceExtraction:
    frame = _image_to_array(raw)
    app = _load_engine()
    faces = app.get(frame)
    if not faces:
        enhanced_frame = _enhance_frame_for_face_detection(frame)
        faces = app.get(enhanced_frame)
        if faces:
            frame = enhanced_frame
    if not faces:
        raise HTTPException(status_code=422, detail="未检测到人脸，请将本人面部置于圆形识别区域内。")
    if len(faces) > 1:
        raise HTTPException(status_code=422, detail="检测到多人入镜，请保持单人面对摄像头。")

    face = faces[0]
    quality = _frame_quality(frame, face, len(faces))
    embedding = getattr(face, "normed_embedding", None)
    if embedding is None:
        embedding = getattr(face, "embedding", None)
    if embedding is None:
        raise HTTPException(status_code=422, detail="人脸特征提取失败，请保持正脸、光线充足后重试。")
    vector = np.asarray(embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return FaceExtraction(
        embedding=vector.astype(float).tolist(),
        face_count=len(faces),
        detection_score=float(getattr(face, "det_score", 0) or 0),
        bbox=quality["bbox"],
        quality=quality,
    )


async def read_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="请选择本人正脸照片。")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 8MB。")
    return raw


def save_profile_image(raw: bytes, student_id: int) -> str:
    FACE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"student_{student_id}_{uuid4().hex}.jpg"
    target = FACE_IMAGE_DIR / filename
    image = Image.open(__import__("io").BytesIO(raw)).convert("RGB")
    image.thumbnail((900, 900))
    image.save(target, format="JPEG", quality=88)
    return f"/static/face-profiles/{filename}"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=np.float32)
    b = np.asarray(right, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def register_profile(db: Session, student: models.User, raw: bytes) -> models.FaceProfile:
    extraction = extract_face(raw)
    quality_payload = _merge_client_quality(extraction.quality, client_quality)
    quality_reason = _quality_reason(quality_payload)
    if quality_reason:
        raise HTTPException(status_code=422, detail=quality_reason[1])
    image_url = save_profile_image(raw, student.id)
    profile = db.query(models.FaceProfile).filter(models.FaceProfile.student_id == student.id).first()
    if not profile:
        profile = models.FaceProfile(student_id=student.id)
    existing_embeddings = _profile_embeddings(profile) if profile.id else []
    existing_images = _safe_json_loads(getattr(profile, "sample_images_json", None), [])
    existing_quality = _safe_json_loads(getattr(profile, "quality_json", None), [])
    if not isinstance(existing_images, list):
        existing_images = []
    if not isinstance(existing_quality, list):
        existing_quality = []
    embeddings = (existing_embeddings + [extraction.embedding])[-5:]
    sample_images = (existing_images + [image_url])[-5:]
    quality_samples = (existing_quality + [extraction.quality])[-5:]
    profile.face_embedding = json.dumps(embeddings[-1])
    profile.face_image_url = image_url
    profile.embeddings_json = json.dumps(embeddings, ensure_ascii=False)
    profile.sample_images_json = json.dumps(sample_images, ensure_ascii=False)
    profile.quality_json = json.dumps(quality_samples, ensure_ascii=False)
    profile.embedding_model = f"insightface:{EMBEDDING_MODEL}"
    profile.updated_at = datetime.utcnow()
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def serialize_profile(profile: models.FaceProfile | None) -> dict[str, Any]:
    if not profile:
        return {"registered": False}
    return {
        "registered": True,
        "student_id": profile.student_id,
        "face_image_url": profile.face_image_url,
        "sample_count": len(_profile_embeddings(profile)),
        "sample_images": _safe_json_loads(getattr(profile, "sample_images_json", None), []),
        "embedding_model": profile.embedding_model,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _profile_embedding(profile: models.FaceProfile) -> list[float]:
    embeddings = _profile_embeddings(profile)
    if embeddings:
        return embeddings[-1]


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return fallback


def _profile_embeddings(profile: models.FaceProfile) -> list[list[float]]:
    embeddings = _safe_json_loads(getattr(profile, "embeddings_json", None), [])
    if isinstance(embeddings, list) and embeddings and all(isinstance(item, list) for item in embeddings):
        return [[float(value) for value in item] for item in embeddings if item]
    try:
        value = json.loads(profile.face_embedding or "[]")
    except Exception:
        value = []
    if not isinstance(value, list) or not value:
        raise HTTPException(status_code=409, detail="人脸档案无效，请在管理端重新注册人脸照片。")
    return [[float(item) for item in value]]


def count_session_failures(db: Session, session_id: int) -> int:
    return _count_consecutive_session_failures(db, session_id)


def count_session_monitor_failures(db: Session, session_id: int) -> int:
    return _count_consecutive_session_failures(db, session_id, monitor_only=True)


def count_session_monitor_failures_total(db: Session, session_id: int) -> int:
    return (
        db.query(models.FaceVerificationEvent)
        .filter(
            models.FaceVerificationEvent.session_id == session_id,
            models.FaceVerificationEvent.event_type != "verify",
            models.FaceVerificationEvent.status == "failed",
        )
        .count()
    )


def count_session_failures_total(db: Session, session_id: int) -> int:
    return (
        db.query(models.FaceVerificationEvent)
        .filter(
            models.FaceVerificationEvent.session_id == session_id,
            models.FaceVerificationEvent.status == "failed",
        )
        .count()
    )


def count_session_serious_failures_total(db: Session, session_id: int) -> int:
    return (
        db.query(models.FaceVerificationEvent)
        .filter(
            models.FaceVerificationEvent.session_id == session_id,
            models.FaceVerificationEvent.event_type != "verify",
            models.FaceVerificationEvent.status == "failed",
            models.FaceVerificationEvent.abnormal_level == "serious",
        )
        .count()
    )


def _recent_monitor_events(db: Session, session_id: int) -> list[models.FaceVerificationEvent]:
    return (
        db.query(models.FaceVerificationEvent)
        .filter(
            models.FaceVerificationEvent.session_id == session_id,
            models.FaceVerificationEvent.event_type != "verify",
        )
        .order_by(models.FaceVerificationEvent.created_at.desc())
        .limit(FACE_VOTE_WINDOW)
        .all()
    )


def _vote_window(db: Session, session_id: int) -> dict[str, Any]:
    events = list(reversed(_recent_monitor_events(db, session_id)))
    failed = [event for event in events if event.status == "failed"]
    serious = [event for event in failed if event.abnormal_level == "serious"]
    return {
        "size": len(events),
        "fail_count": len(failed),
        "serious_count": len(serious),
        "fail_limit": FACE_VOTE_FAIL_LIMIT,
        "event_ids": [event.id for event in events],
    }


def is_face_session_terminated_by_policy(db: Session, session_id: int) -> bool:
    consecutive_failures = _count_consecutive_session_failures(db, session_id, monitor_only=True)
    return consecutive_failures >= FACE_CONSECUTIVE_MAX_FAILURES


def _count_consecutive_session_failures(db: Session, session_id: int, *, monitor_only: bool = False) -> int:
    query = db.query(models.FaceVerificationEvent).filter(models.FaceVerificationEvent.session_id == session_id)
    if monitor_only:
        query = query.filter(models.FaceVerificationEvent.event_type != "verify")
    events = (
        query
        .order_by(models.FaceVerificationEvent.created_at.desc())
        .limit(12)
        .all()
    )
    failure_count = 0
    for event in events:
        if event.status == "failed":
            failure_count += 1
            continue
        if event.status == "passed":
            break
    return (
        failure_count
    )


def build_adaptive_fallback_report(
    *,
    session: models.TrainingSession,
    failure_count: int,
    reason: str,
    error: str,
) -> dict[str, Any]:
    return {
        "total_score": 0,
        "grade_level": "不合格",
        "strengths": [],
        "improvements": [
            "训练期间请保持本人持续位于圆形人脸识别区域内。",
            "请避免离开画面、多人同时入镜或由他人替训。",
            "重新训练前请确认管理端人脸档案、摄像头光线和 VideoCap/USB 摄像头连接正常。",
        ],
        "suggestions": "本次训练因人脸识别异常累计达到上限而自动终止。请确认本人正对摄像头、保持单人入镜后重新训练。",
        "assessment_point_results": [],
        "common_reviews": [
            {
                "title": "人脸识别异常自动终止",
                "content": "系统检测到离开识别区域、身份不匹配、多人入镜或活体异常累计达到上限，已自动结束本次训练。",
            }
        ],
        "assessment_check_results": [],
        "termination_reason": "multimodal_guard_finished",
        "termination_report": "人脸识别异常累计达到上限，系统已自动终止训练并生成评估结果。",
        "failure_count": failure_count,
        "last_reason": localize_face_reason(reason),
        "evaluation_meta": {
            "scoring_version": "adaptive_v1",
            "evaluation_type": "auto_terminated_fallback",
            "trigger": "multimodal_guard",
            "session_id": session.id,
            "auto_finished": True,
            "evaluator_error": error,
            "assessment_completion": {"weight_rate": 0, "hit_count": 0, "total_count": 0},
            "report_header": {
                "total_score": 0,
                "grade_level": "不合格",
                "evaluator": "系统评估",
            },
            "stage_gap_summary": {
                "missing": ["本人持续在场", "人脸身份一致", "活体状态有效"],
                "summary": "人脸识别异常触发自动终止，未形成完整训练闭环。",
            },
        },
    }


def _finalize_face_termination(
    db: Session,
    *,
    session: models.TrainingSession,
    failure_count: int,
    reason: str,
) -> dict[str, Any]:
    db.add(
        models.Message(
            session_id=session.id,
            role="system",
            content="【系统自动终止】人脸识别异常累计达到上限，本次训练已结束并进入评估流程。",
        )
    )
    session.status = "evaluating"
    session.evaluation_result = None
    now = datetime.utcnow()
    if session.training_started_at is None:
        session.training_started_at = session.created_at or now
    session.training_finished_at = session.training_finished_at or now
    db.commit()

    report = evaluate_session(db, session.id, session.user_id, force_recompute=True)
    if isinstance(report, dict) and not report.get("error"):
        meta = report.setdefault("evaluation_meta", {})
        meta["scoring_version"] = meta.get("scoring_version") or "adaptive_v1"
        meta["evaluation_type"] = "auto_terminated"
        meta["trigger"] = "multimodal_guard"
        meta["auto_finished"] = True
        report["termination_reason"] = "multimodal_guard_finished"
        report["termination_report"] = "人脸识别异常累计达到上限，系统已自动终止训练并完成当前评估流程。"
        report["failure_count"] = failure_count
        report["last_reason"] = localize_face_reason(reason)
        report["termination_report"] = "系统已根据实训检测守护规则自动结束训练，并生成完整评估报告。人脸异常作为实训检测事件纳入报告，不再覆盖能力评估结论。"
        report["face_monitor"] = {
            "termination_reason": "face_verification_failed",
            "failure_count": failure_count,
            "last_reason": localize_face_reason(reason),
        }
        report["termination_reason"] = "multimodal_guard_finished"
        report["termination_report"] = "系统已根据实训检测守护规则自动结束训练；因常规评估生成失败，当前报告以实训检测兜底结果为准。"
        report["face_monitor"] = {
            "termination_reason": "face_verification_failed",
            "failure_count": failure_count,
            "last_reason": localize_face_reason(reason),
        }
        report["termination_reason"] = "multimodal_guard_finished"
        report["termination_report"] = "\u7cfb\u7edf\u5df2\u6839\u636e\u5b9e\u8bad\u68c0\u6d4b\u5b88\u62a4\u89c4\u5219\u81ea\u52a8\u7ed3\u675f\u8bad\u7ec3\uff0c\u5e76\u751f\u6210\u5b8c\u6574\u8bc4\u4f30\u62a5\u544a\u3002\u4eba\u8138\u5f02\u5e38\u4f5c\u4e3a\u5b9e\u8bad\u68c0\u6d4b\u4e8b\u4ef6\u7eb3\u5165\u62a5\u544a\uff0c\u4e0d\u518d\u8986\u76d6\u80fd\u529b\u8bc4\u4f30\u7ed3\u8bba\u3002"
        report = append_scene_performance_report(db, session.id, report)
        session.status = "finished"
        session.evaluation_result = json.dumps(report, ensure_ascii=False)
        db.commit()
    else:
        report = build_adaptive_fallback_report(
            session=session,
            failure_count=failure_count,
            reason=reason,
            error=str(report.get("error") if isinstance(report, dict) else "评估服务异常"),
        )
        report["termination_reason"] = "multimodal_guard_finished"
        report["termination_report"] = "\u7cfb\u7edf\u5df2\u6839\u636e\u5b9e\u8bad\u68c0\u6d4b\u5b88\u62a4\u89c4\u5219\u81ea\u52a8\u7ed3\u675f\u8bad\u7ec3\uff1b\u56e0\u5e38\u89c4\u8bc4\u4f30\u751f\u6210\u5931\u8d25\uff0c\u5f53\u524d\u62a5\u544a\u4ee5\u5b9e\u8bad\u68c0\u6d4b\u515c\u5e95\u7ed3\u679c\u4e3a\u51c6\u3002"
        report["face_monitor"] = {
            "termination_reason": "face_verification_failed",
            "failure_count": failure_count,
            "last_reason": localize_face_reason(reason),
        }
        report = append_scene_performance_report(db, session.id, report)
        session.status = "finished"
        session.evaluation_result = json.dumps(report, ensure_ascii=False)
        db.commit()

    try:
        sync_assignment_submission_for_session(db, session.id, session.user_id, report)
    except Exception as error:
        print(f"Face termination submission sync failed: {error}")
    return report


def record_event(
    db: Session,
    *,
    session: models.TrainingSession,
    event_type: str,
    status: str,
    reason: str,
    similarity: float | None = None,
    liveness_score: float | None = None,
    auto_finalize: bool = True,
    reason_code: str | None = None,
    quality: dict[str, Any] | None = None,
    liveness: dict[str, Any] | None = None,
    abnormal_level: str | None = None,
) -> models.FaceVerificationEvent:
    if auto_finalize:
        failure_basis = _count_consecutive_session_failures(db, session.id, monitor_only=True)
        failure_count = failure_basis + 1 if status == "failed" else failure_basis
    else:
        failure_count = 0
    event = models.FaceVerificationEvent(
        session_id=session.id,
        student_id=session.user_id,
        event_type=event_type,
        status=status,
        reason=localize_face_reason(reason),
        reason_code=reason_code,
        similarity=None if similarity is None else int(round(similarity * 100)),
        liveness_score=None if liveness_score is None else int(round(liveness_score * 100)),
        quality_json=json.dumps(quality or {}, ensure_ascii=False),
        liveness_json=json.dumps(liveness or {}, ensure_ascii=False),
        abnormal_level=abnormal_level,
        failure_count=failure_count,
    )
    db.add(event)
    db.commit()

    consecutive_failures = (
        _count_consecutive_session_failures(db, session.id, monitor_only=True) if auto_finalize else 0
    )
    should_finalize = (
        auto_finalize
        and status == "failed"
        and consecutive_failures >= FACE_CONSECUTIVE_MAX_FAILURES
    )
    if should_finalize:
        _finalize_face_termination(
            db,
            session=session,
            failure_count=failure_count,
            reason=reason,
        )

    db.refresh(event)
    return event


def verify_frame(
    db: Session,
    *,
    session: models.TrainingSession,
    frame_data_url: str,
    event_type: str = "verify",
    liveness_score: float | None = None,
    challenge_id: str | None = None,
    liveness_actions: list[dict[str, Any]] | None = None,
    client_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auto_finalize = event_type != "verify"
    profile = db.query(models.FaceProfile).filter(models.FaceProfile.student_id == session.user_id).first()
    if not profile:
        reason = "当前账号尚未在管理端注册人脸档案。"
        event = record_event(
            db,
            session=session,
            event_type=event_type,
            status="failed",
            reason=reason,
            liveness_score=liveness_score,
            auto_finalize=auto_finalize,
            reason_code="no_registered_profile",
            abnormal_level="serious" if auto_finalize else "medium",
        )
        return _verification_response(False, event, None, reason)

    challenge_payload: dict[str, Any] | None = None

    try:
        extraction = extract_face(decode_data_url(frame_data_url))
    except HTTPException as error:
        reason_code = "multiple_faces" if "多人" in str(error.detail) else "no_face"
        abnormal_level = "serious" if reason_code in {"multiple_faces", "no_face"} else "medium"
        event = record_event(
            db,
            session=session,
            event_type=event_type,
            status="failed",
            reason=localize_face_reason(error.detail),
            liveness_score=liveness_score,
            auto_finalize=auto_finalize,
            reason_code=reason_code,
            abnormal_level=abnormal_level,
        )
        return _verification_response(False, event, None, localize_face_reason(error.detail))

    quality_payload = _merge_client_quality(extraction.quality, client_quality)
    quality_reason = _quality_reason(quality_payload)
    if quality_reason and event_type == "verify":
        reason_code, reason_text, abnormal_level = quality_reason
        event = record_event(
            db,
            session=session,
            event_type=event_type,
            status="failed",
            reason=reason_text,
            liveness_score=liveness_score,
            auto_finalize=auto_finalize,
            reason_code=reason_code,
            quality=quality_payload,
            abnormal_level=abnormal_level,
        )
        return _verification_response(
            False,
            event,
            None,
            reason_text,
            detection_score=extraction.detection_score,
            quality=quality_payload,
        )

    similarities = [cosine_similarity(template, extraction.embedding) for template in _profile_embeddings(profile)]
    similarity = max(similarities) if similarities else 0.0
    best_template_index = similarities.index(similarity) if similarities else -1
    live_score = float(liveness_score if liveness_score is not None else 1.0)
    similarity_threshold = FACE_HEARTBEAT_SIMILARITY_THRESHOLD if event_type == "heartbeat" else FACE_SIMILARITY_THRESHOLD
    if quality_payload.get("blur", 0) < 22 and quality_payload.get("detection_score", 0) >= 0.5:
        similarity_threshold -= 0.03 if event_type == "heartbeat" else 0.04
    similarity_threshold = max(0.58 if event_type == "heartbeat" else 0.62, similarity_threshold)
    quality_penalty = quality_reason is not None and event_type == "heartbeat"
    identity_passed = similarity >= similarity_threshold
    passed = identity_passed and live_score >= FACE_LIVENESS_THRESHOLD and not (event_type == "verify" and quality_reason)
    reason_code = None
    abnormal_level = None
    if event_type == "verify" and identity_passed and not quality_reason:
        challenge_passed, challenge_payload, challenge_reason = update_liveness_challenge_from_quality(
            session_id=session.id,
            student_id=session.user_id,
            challenge_id=challenge_id,
            quality=quality_payload,
        )
        if challenge_passed:
            passed = True
            reason = "人脸验证通过"
        else:
            passed = False
            reason = challenge_reason
            reason_code = "liveness_challenge_pending"
            abnormal_level = "minor"
    elif passed:
        reason = "身份验证通过"
    elif live_score < FACE_LIVENESS_THRESHOLD:
        reason = "活体检测未通过，请本人正对摄像头并保持自然动作。"
        reason_code = "liveness_failed"
        abnormal_level = "serious"
    elif quality_penalty and quality_reason:
        reason_code, reason, abnormal_level = quality_reason
        abnormal_level = "minor"
    else:
        reason = "当前人脸与注册学员不一致，请确认由本人参加训练。"
        reason_code = "face_mismatch"
        abnormal_level = "serious" if similarity < max(0.45, similarity_threshold - 0.15) else "medium"
    event = record_event(
        db,
        session=session,
        event_type=event_type,
        status="passed" if passed else "failed",
        reason=reason,
        similarity=similarity,
        liveness_score=live_score,
        auto_finalize=auto_finalize,
        reason_code=reason_code,
        quality={**quality_payload, "best_template_index": best_template_index},
        liveness=challenge_payload or {"score": live_score, "mode": "monitor"},
        abnormal_level=abnormal_level,
    )
    vote = _vote_window(db, session.id) if auto_finalize else None
    terminated = is_face_session_terminated_by_policy(db, session.id) if auto_finalize and not passed else False
    return _verification_response(
        passed,
        event,
        similarity,
        reason,
        detection_score=extraction.detection_score,
        similarity_threshold=similarity_threshold,
        liveness_score=live_score,
        quality=quality_payload,
        vote_window=vote,
        abnormal_level=abnormal_level,
        reason_code=reason_code,
        liveness=challenge_payload,
        terminated=terminated,
    )


def _verification_response(
    passed: bool,
    event: models.FaceVerificationEvent,
    similarity: float | None,
    reason: str,
    *,
    detection_score: float | None = None,
    similarity_threshold: float | None = None,
    liveness_score: float | None = None,
    quality: dict[str, Any] | None = None,
    vote_window: dict[str, Any] | None = None,
    abnormal_level: str | None = None,
    reason_code: str | None = None,
    liveness: dict[str, Any] | None = None,
    terminated: bool = False,
) -> dict[str, Any]:
    return {
        "passed": passed,
        "status": "terminated" if terminated else ("passed" if passed else "failed"),
        "reason": localize_face_reason(reason),
        "similarity": similarity,
        "similarity_threshold": similarity_threshold,
        "detection_score": detection_score,
        "liveness_score": liveness_score,
        "quality_metrics": quality,
        "vote_window": vote_window,
        "abnormal_level": abnormal_level,
        "reason_code": reason_code,
        "liveness": liveness,
        "failure_count": event.failure_count,
        "max_failures": FACE_MAX_FAILURES,
        "terminated": terminated,
        "event_id": event.id,
    }
