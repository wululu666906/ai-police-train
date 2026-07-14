import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy.orm import Session

import models
from services.classroom_service import sync_assignment_submission_for_session
from services.evaluation_service import enforce_final_score_policy, evaluate_session
from services.import_isolation import isolated_sys_path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend").exists() and (parent / "frontend").exists():
            return parent
    for parent in Path(__file__).resolve().parents:
        if (parent / "data").exists():
            return parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _find_project_root()
DEFAULT_FACE_MODEL_DIR = PROJECT_ROOT / "data" / "face_models"


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = (PROJECT_ROOT / path).resolve()
    if candidate.exists() or not str(path).startswith(".."):
        return candidate
    parts = path.parts
    if "data" in parts:
        data_index = parts.index("data")
        return (PROJECT_ROOT / Path(*parts[data_index:])).resolve()
    return (PROJECT_ROOT / "data" / path.name).resolve()


FACE_SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.68"))
FACE_FAST_VERIFY_SIMILARITY_THRESHOLD = float(os.getenv("FACE_FAST_VERIFY_SIMILARITY_THRESHOLD", "0.64"))
FACE_HEARTBEAT_SIMILARITY_THRESHOLD = float(os.getenv("FACE_HEARTBEAT_SIMILARITY_THRESHOLD", "0.68"))
FACE_MAX_FAILURES = int(os.getenv("FACE_MAX_FAILURES", "5"))
FACE_SERIOUS_MAX_FAILURES = int(os.getenv("FACE_SERIOUS_MAX_FAILURES", "5"))
FACE_VOTE_WINDOW = int(os.getenv("FACE_VOTE_WINDOW", "3"))
FACE_VOTE_FAIL_LIMIT = int(os.getenv("FACE_VOTE_FAIL_LIMIT", "2"))
FACE_CONSECUTIVE_MAX_FAILURES = int(os.getenv("FACE_CONSECUTIVE_MAX_FAILURES", "5"))
FACE_ENGINE_REQUIRED = os.getenv("FACE_ENGINE_REQUIRED", "1").strip().lower() in {"1", "true", "yes", "on"}
FACE_IMAGE_DIR = _resolve_path(os.getenv("FACE_IMAGE_DIR", Path(__file__).resolve().parents[1] / "static" / "face_profiles"))
INSIGHTFACE_MODEL_DIR = _resolve_path(
    os.getenv("INSIGHTFACE_MODEL_DIR", str(DEFAULT_FACE_MODEL_DIR)),
)
EMBEDDING_MODEL = os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l")

_face_app = None
_face_engine_error = ""


def _face_service_unavailable_detail(error: Exception | str) -> str:
    return f"人脸识别模型暂不可用，请确认人脸识别依赖和模型文件已正确安装后重试。原始错误：{error}"


def _is_face_engine_unavailable(error: HTTPException | Exception | str) -> bool:
    detail = getattr(error, "detail", error)
    text = str(detail or "").lower()
    return "face engine unavailable" in text or "insightface" in text or "onnx" in text or "model" in text or "??" in text


def localize_face_reason(reason: Any) -> str:
    text = str(reason or "").strip()
    lowered = text.lower()
    if not text:
        return "人脸验证失败"
    if set(text) == {"?"}:
        return "人脸验证未通过，请按提示调整后重试。"
    if "insightface unavailable" in lowered:
        return "人脸识别模型暂不可用，请检查后端模型服务。"
    if "model init failed" in lowered:
        return "人脸识别模型初始化失败，请检查模型文件和运行环境。"
    if "invalid image" in lowered:
        return "画面格式无效，请重新采集。"
    if "invalid camera frame" in lowered:
        return "摄像头画面无效，请保持摄像头正常工作。"
    if "no face detected" in lowered or "no face" in lowered:
        return "未检测到人脸，请正对摄像头。"
    if "multiple faces" in lowered or "multiple" in lowered:
        return "检测到多人入镜，请保持单人验证。"
    if "embedding extraction" in lowered:
        return "人脸特征提取失败，请调整光线后重试。"
    if "please choose a face photo" in lowered:
        return "请选择人脸照片。"
    if "image must not exceed" in lowered:
        return "图片大小不能超过 8MB。"
    if "invalid face profile" in lowered:
        return "人脸档案无效，请重新注册。"
    if "no registered face profile" in lowered or "registered face profile" in lowered:
        return "当前账号尚未注册人脸档案。"
    if "face mismatch" in lowered or "mismatch" in lowered:
        return "当前人脸与注册学员不一致，请确认由本人参加训练。"
    if lowered == "passed":
        return "人脸验证通过"
    if "unknown evaluator error" in lowered:
        return "评估生成失败，已生成兜底报告。"
    return text

@dataclass
class FaceExtraction:
    frame: np.ndarray
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
        with isolated_sys_path(INSIGHTFACE_MODEL_DIR):
            from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name=EMBEDDING_MODEL,
            root=str(INSIGHTFACE_MODEL_DIR),
            allowed_modules=["detection", "recognition"],
            providers=["CPUExecutionProvider"],
        )
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
    dependency_status = _face_dependency_status()
    return {
        "engine": "insightface",
        "model": EMBEDDING_MODEL,
        "model_dir": str(INSIGHTFACE_MODEL_DIR),
        "model_path": str(model_path),
        "model_files_ready": all((model_path / filename).exists() for filename in expected_files),
        "expected_files": expected_files,
        "verification_mode": "identity_only",
        "dependencies": dependency_status,
        "engine_required": FACE_ENGINE_REQUIRED,
        "degraded_allowed": not FACE_ENGINE_REQUIRED,
        "loaded": _face_app is not None,
        "last_error": _face_engine_error,
        "similarity_threshold": FACE_SIMILARITY_THRESHOLD,
        "fast_verify_similarity_threshold": FACE_FAST_VERIFY_SIMILARITY_THRESHOLD,
        "heartbeat_similarity_threshold": FACE_HEARTBEAT_SIMILARITY_THRESHOLD,
        "max_failures": FACE_MAX_FAILURES,
    }


def _face_dependency_status() -> dict[str, Any]:
    import importlib.util

    dependencies = {}
    for module_name in ("insightface", "cv2", "numpy"):
        spec = importlib.util.find_spec(module_name)
        dependencies[module_name] = {
            "available": spec is not None,
            "origin": getattr(spec, "origin", None) if spec else None,
        }
    return dependencies


def warmup_face_engine_async() -> None:
    import threading

    def _warmup() -> None:
        try:
            _load_engine()
        except Exception as error:
            print(f"Face engine warmup failed: {error}")

    thread = threading.Thread(target=_warmup, name="face-engine-warmup", daemon=True)
    thread.start()


def _image_to_array(raw: bytes) -> np.ndarray:
    try:
        image = Image.open(__import__("io").BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="图片格式无效，请上传清晰的人脸照片。")
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
        return ("face_too_small", "人脸距离摄像头过远，请靠近后重试。", "minor")
    if quality.get("center_offset", 1) > center_limit:
        return ("face_off_center", "请将人脸放在圆形区域中央。", "medium")
    if quality.get("brightness", 0) < 42:
        return ("low_light", "当前光线偏暗，请补充光线。", "minor")
    if quality.get("detection_score", 0) < 0.45:
        return ("low_detection_confidence", "人脸检测置信度偏低，请正对摄像头。", "minor")
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


def _face_crop(frame: np.ndarray, bbox: list[float], *, margin: float = 0.2) -> np.ndarray:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = [float(item) for item in bbox[:4]]
    face_width = max(1.0, x2 - x1)
    face_height = max(1.0, y2 - y1)
    pad_x = face_width * margin
    pad_y = face_height * margin
    left = max(0, int(round(x1 - pad_x)))
    top = max(0, int(round(y1 - pad_y)))
    right = min(width, int(round(x2 + pad_x)))
    bottom = min(height, int(round(y2 + pad_y)))
    crop = frame[top:bottom, left:right]
    if crop.size == 0:
        crop = frame
    image = Image.fromarray(crop).convert("RGB")
    return np.asarray(image, dtype=np.float32)


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
        raise HTTPException(status_code=400, detail="摄像头画面数据无效，请重新采集。")


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
        raise HTTPException(status_code=422, detail="未检测到人脸，请正对摄像头。")
    if len(faces) > 1:
        raise HTTPException(status_code=422, detail="检测到多人入镜，请保持单人验证。")

    face = faces[0]
    quality = _frame_quality(frame, face, len(faces))
    embedding = getattr(face, "normed_embedding", None)
    if embedding is None:
        embedding = getattr(face, "embedding", None)
    if embedding is None:
        raise HTTPException(status_code=422, detail="人脸特征提取失败，请调整光线后重试。")
    vector = np.asarray(embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return FaceExtraction(
        frame=frame,
        embedding=vector.astype(float).tolist(),
        face_count=len(faces),
        detection_score=float(getattr(face, "det_score", 0) or 0),
        bbox=quality["bbox"],
        quality=quality,
    )


async def read_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="请选择人脸照片。")
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
    quality_payload = _merge_client_quality(extraction.quality, None)
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
        raise HTTPException(status_code=409, detail="人脸档案无效，请重新注册。")
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
        "grade_level": "未通过",
        "strengths": [],
        "improvements": [
            "训练过程中人脸监控连续异常，未能完成有效训练。",
            "请确认摄像头可用、本人在镜头内，并重新开始训练。",
            "重新训练前建议检查光线、坐姿和人脸档案是否正确。",
        ],
        "suggestions": "本次训练因人脸验证异常中断，请处理摄像头、人脸档案或本人验证问题后重新训练。",
        "assessment_point_results": [],
        "common_reviews": [
            {
                "title": "人脸验证异常",
                "content": "系统检测到人脸验证连续异常，已终止训练并生成兜底记录。",
            }
        ],
        "assessment_check_results": [],
        "termination_reason": "face_verification_finished",
        "termination_report": "训练因人脸验证连续异常被系统自动终止。",
        "failure_count": failure_count,
        "last_reason": localize_face_reason(reason),
        "evaluation_meta": {
            "scoring_version": "adaptive_v1",
            "evaluation_type": "auto_terminated_fallback",
            "trigger": "face_verification_guard",
            "session_id": session.id,
            "auto_finished": True,
            "evaluator_error": error,
            "assessment_completion": {"weight_rate": 0, "hit_count": 0, "total_count": 0},
            "report_header": {
                "total_score": 0,
                "grade_level": "未通过",
                "evaluator": "系统自动评估",
            },
            "stage_gap_summary": {
                "missing": ["身份验证稳定性", "训练过程完整性", "摄像头在线状态"],
                "summary": "训练过程被人脸验证异常打断，无法形成完整对话表现。",
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
            content="系统检测到人脸验证连续异常，本次训练已自动终止并进入评估。",
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
        meta["trigger"] = "face_verification_guard"
        meta["auto_finished"] = True
        report["termination_reason"] = "face_verification_finished"
        report["termination_report"] = "系统检测到人脸验证连续异常，本次训练已自动终止。请确认本人在镜头内并保持摄像头在线。"
        report["failure_count"] = failure_count
        report["last_reason"] = localize_face_reason(reason)
        report["face_monitor"] = {
            "termination_reason": "face_verification_failed",
            "failure_count": failure_count,
            "last_reason": localize_face_reason(reason),
        }
        report = enforce_final_score_policy(report, policy_source="face_termination_success")
        session.status = "finished"
        session.evaluation_result = json.dumps(report, ensure_ascii=False)
        db.commit()
    else:
        report = build_adaptive_fallback_report(
            session=session,
            failure_count=failure_count,
            reason=reason,
            error=str(report.get("error") if isinstance(report, dict) else "未知评估错误"),
        )
        report["termination_reason"] = "face_verification_finished"
        report["termination_report"] = "系统检测到人脸验证连续异常，本次训练已自动终止。"
        report["face_monitor"] = {
            "termination_reason": "face_verification_failed",
            "failure_count": failure_count,
            "last_reason": localize_face_reason(reason),
        }
        report = enforce_final_score_policy(report, policy_source="face_termination_fallback")
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
    auto_finalize: bool = True,
    reason_code: str | None = None,
    quality: dict[str, Any] | None = None,
    abnormal_level: str | None = None,
) -> models.FaceVerificationEvent:
    if auto_finalize:
        failure_basis = _count_consecutive_session_failures(db, session.id, monitor_only=True)
        failure_count = failure_basis + 1 if status == "failed" else 0
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
        quality_json=json.dumps(quality or {}, ensure_ascii=False),
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
            auto_finalize=auto_finalize,
            reason_code="no_registered_profile",
            abnormal_level="serious" if auto_finalize else "medium",
        )
        return _verification_response(False, event, None, reason)

    try:
        extraction = extract_face(decode_data_url(frame_data_url))
    except HTTPException as error:
        detail_text = str(error.detail or "")
        reason_code = "multiple_faces" if "multiple" in detail_text.lower() or "多人" in detail_text else "no_face"
        abnormal_level = "serious" if reason_code in {"multiple_faces", "no_face"} else "medium"
        event = record_event(
            db,
            session=session,
            event_type=event_type,
            status="failed",
            reason=localize_face_reason(error.detail),
            auto_finalize=auto_finalize,
            reason_code=reason_code,
            abnormal_level=abnormal_level,
        )
        return _verification_response(False, event, None, localize_face_reason(error.detail))

    quality_payload = _merge_client_quality(extraction.quality, client_quality)
    quality_reason = _quality_reason(quality_payload)
    similarities = [cosine_similarity(template, extraction.embedding) for template in _profile_embeddings(profile)]
    similarity = max(similarities) if similarities else 0.0
    best_template_index = similarities.index(similarity) if similarities else -1

    if event_type == "verify":
        similarity_threshold = FACE_FAST_VERIFY_SIMILARITY_THRESHOLD
    elif event_type == "heartbeat":
        similarity_threshold = FACE_HEARTBEAT_SIMILARITY_THRESHOLD
    else:
        similarity_threshold = FACE_SIMILARITY_THRESHOLD
    if quality_payload.get("blur", 0) < 22 and quality_payload.get("detection_score", 0) >= 0.5:
        similarity_threshold -= 0.03 if event_type == "heartbeat" else 0.02
    similarity_threshold = max(0.58 if event_type == "heartbeat" else 0.62, similarity_threshold)
    identity_passed = similarity >= similarity_threshold

    verify_quality_soft_pass = (
        event_type == "verify"
        and identity_passed
        and quality_reason is not None
        and quality_reason[2] == "minor"
        and similarity >= similarity_threshold + 0.03
    )
    passed = identity_passed and (not quality_reason or verify_quality_soft_pass)

    reason_code = None
    abnormal_level = None
    if event_type == "verify" and passed:
        reason = "人脸验证通过"
    elif passed:
        reason = "人脸已回到识别区域。"
    elif quality_reason:
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
        auto_finalize=auto_finalize,
        reason_code=reason_code,
        quality={**quality_payload, "best_template_index": best_template_index},
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
        quality=quality_payload,
        vote_window=vote,
        abnormal_level=abnormal_level,
        reason_code=reason_code,
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
    quality: dict[str, Any] | None = None,
    vote_window: dict[str, Any] | None = None,
    abnormal_level: str | None = None,
    reason_code: str | None = None,
    terminated: bool = False,
) -> dict[str, Any]:
    return {
        "passed": passed,
        "status": "terminated" if terminated else ("passed" if passed else "failed"),
        "reason": localize_face_reason(reason),
        "similarity": similarity,
        "similarity_threshold": similarity_threshold,
        "detection_score": detection_score,
        "quality_metrics": quality,
        "vote_window": vote_window,
        "abnormal_level": abnormal_level,
        "reason_code": reason_code,
        "failure_count": event.failure_count,
        "monitor_failure_count": event.failure_count,
        "max_failures": FACE_MAX_FAILURES,
        "terminated": terminated,
        "event_id": event.id,
    }
