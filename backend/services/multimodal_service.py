import base64
import importlib.util
import json
import os
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageStat
from sqlalchemy.orm import Session

import models


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_deepface_home() -> Path:
    configured = os.getenv("AI_POLICE_DEEPFACE_HOME") or os.getenv("DEEPFACE_HOME")
    if configured:
        return Path(configured)
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ai-police-sim" / "deepface"
    return Path(tempfile.gettempdir()) / "ai-police-sim" / "deepface"


PROJECT_DEEPFACE_HOME = _default_deepface_home()
os.environ.setdefault("DEEPFACE_HOME", str(PROJECT_DEEPFACE_HOME))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
try:
    PROJECT_DEEPFACE_HOME.mkdir(parents=True, exist_ok=True)
except Exception:
    fallback_deepface_home = Path(tempfile.gettempdir()) / "ai-police-sim" / "deepface"
    os.environ["DEEPFACE_HOME"] = str(fallback_deepface_home)
    PROJECT_DEEPFACE_HOME = fallback_deepface_home
    PROJECT_DEEPFACE_HOME.mkdir(parents=True, exist_ok=True)

FRAME_SAMPLE_SECONDS = 1
NO_DATA_TEXT = "暂无数据"
FINAL_SCORE_WEIGHTS = {"behavior": 0.35, "face": 0.30, "attention": 0.35}
SCENE_REPORT_SCHEMA_VERSION = "scene_performance_report/v2"
SCENE_RUBRIC_VERSION = "police_scene_rubric/v2"
TOOL_EVIDENCE_KEYS = {"insightface", "deepface", "opencv", "mediapipe"}
RUBRIC_RULES: dict[str, dict[str, str]] = {
    "identity_presence": {
        "description": "评估学员是否稳定处于画面内，并保持本人身份核验一致，是所有实景视觉评分的基础项。",
        "high_score": "全程本人在场，核验/心跳持续通过，无离镜、遮挡、多人入镜或身份异常。",
        "deduction": "短暂离镜、低光导致核验失败、多人入镜、身份不一致均扣分；连续离镜或触发自动终止时该项应明显降分。",
    },
    "emotion_stability": {
        "description": "评估训练过程中面部情绪是否保持职业、稳定、可控，不把严肃表情简单视为负面。",
        "high_score": "以 neutral/stable 为主，情绪变化平缓，无持续愤怒、恐惧、厌恶或明显失控表情。",
        "deduction": "高压/负面情绪持续出现、情绪频繁跳变、表情与处置场景明显不匹配时扣分；单帧异常不重罚。",
    },
    "pressure_control": {
        "description": "评估压力水平及波动，强调持续高压力和剧烈波动，而不是一次性紧张。",
        "high_score": "平均压力处于可控范围，压力曲线平滑，面对冲突时能快速恢复稳定。",
        "deduction": "平均压力长期偏高、压力标准差大、连续多个窗口处于高压状态时扣分。",
    },
    "head_stability": {
        "description": "评估头部朝向是否稳定、是否保持基本正对交流对象/摄像头。",
        "high_score": "头部姿态自然稳定，少量点头或合理转头不扣分。",
        "deduction": "频繁大幅转头、长时间低头、侧脸交流、明显躲避镜头时扣分。",
    },
    "image_quality": {
        "description": "评估画面亮度、对比度和可识别质量，防止模型因低质量画面误判。",
        "high_score": "光线均匀、面部清晰、亮度和对比度适中。",
        "deduction": "低光、过曝、严重模糊、面部过小或遮挡时扣分，并降低相关模型置信度。",
    },
    "communication_gesture": {
        "description": "评估手势/姿态是否符合警情处置中的稳定、克制、开放沟通要求。",
        "high_score": "姿态稳定，手势自然、不过度，能体现倾听和沟通意图。",
        "deduction": "频繁离开画面、夸张挥手、压迫性动作、长时间无可判定姿态时扣分。",
    },
    "hand_visibility": {
        "description": "评估手部关键点是否稳定可见，用于判断手势规范性和小动作。",
        "high_score": "手部大部分时间可见，关键点置信度高，动作范围自然。",
        "deduction": "手部长时间不可见、置信度低、手部频繁遮挡面部或剧烈晃动时扣分。",
    },
    "posture_visibility": {
        "description": "评估身体姿态关键点可见性，作为站/坐姿稳定和动作判断的基础。",
        "high_score": "上半身/核心姿态关键点稳定可见，站坐姿自然端正。",
        "deduction": "姿态关键点长期缺失、身体大幅偏离画面、姿态严重倾斜时扣分。",
    },
    "action_continuity": {
        "description": "评估动作是否连续、平稳，避免突兀动作影响执法沟通形象。",
        "high_score": "动作过渡平滑，符合听、问、记、回应的自然节奏。",
        "deduction": "动作突兀、频繁抖动、画面运动异常、反复站起坐下或无关动作过多时扣分。",
    },
    "minor_motion_control": {
        "description": "评估小动作和异常动作频率，关注持续性干扰而非一次轻微调整。",
        "high_score": "无明显无关小动作，偶发调整后能恢复稳定。",
        "deduction": "频繁摸脸、晃动、离席、无关手势或异常动作率升高时扣分。",
    },
    "continuous_presence": {
        "description": "评估训练过程中是否持续在场，是专注度和训练完整性的底线。",
        "high_score": "全程在画面内，未出现脱岗、离镜或长时间遮挡。",
        "deduction": "离镜、遮挡、低头脱离检测、自动终止风险都会扣分；连续离镜比短暂离镜扣分更重。",
    },
    "focused_rate": {
        "description": "评估有效专注帧占比，结合在场、头部、运动信号判断是否投入训练。",
        "high_score": "大部分有效帧保持专注状态，能稳定面对训练对象。",
        "deduction": "分心帧比例升高、反复看向无关区域、长时间未面对交流对象时扣分。",
    },
    "gaze_stability": {
        "description": "评估视线/注视稳定性，允许合理看资料，但惩罚频繁无关偏移。",
        "high_score": "视线基本稳定，短暂记录或查看材料后能回到交流对象。",
        "deduction": "长时间偏离、频繁游离、明显躲避注视时扣分。",
    },
    "head_attention": {
        "description": "评估头部朝向对专注度的支撑，区别合理观察和持续分心。",
        "high_score": "头部朝向稳定，合理转头后及时回正。",
        "deduction": "长时间低头、侧头、转身、头部偏移过大时扣分。",
    },
    "distraction_control": {
        "description": "评估由画面运动和姿态变化反映的分心/不稳定行为。",
        "high_score": "画面运动平稳，无持续性无关动作。",
        "deduction": "频繁晃动、离席、身体大幅移动、训练无关动作增多时扣分。",
    },
}
REQUIRED_SCENE_SECTIONS = {
    "schema_version",
    "face",
    "micro_expression",
    "gesture",
    "attention",
    "voice",
    "scores",
    "overall",
    "degradation",
    "tool_evidence",
    "adapter_status",
    "rubric",
    "score_breakdown",
    "evidence_layer",
    "meta",
}
_MEDIAPIPE_SOLUTIONS_CACHE: dict[str, Any] | None = None
_DEEPFACE_ANALYZER: Any | None = None
_DEEPFACE_WARMUP_STARTED = False


def _deepface_emotion_weights_path() -> Path:
    return PROJECT_DEEPFACE_HOME / ".deepface" / "weights" / "facial_expression_model_weights.h5"


def _importable(module_name: str) -> tuple[bool, str]:
    try:
        import importlib

        importlib.import_module(module_name)
        return True, ""
    except Exception as error:
        return False, str(error)


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


def _as_int_score(value: float | int | None) -> int | None:
    if value is None:
        return None
    return int(round(_clamp(float(value), 0, 100)))


def _decode_data_url(data_url: str) -> Image.Image:
    value = (data_url or "").strip()
    if "," in value and value.startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        raw = base64.b64decode(value)
        return Image.open(__import__("io").BytesIO(raw)).convert("RGB")
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid camera frame") from error


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _frontend_mediapipe_status() -> dict[str, Any]:
    package_json_path = PROJECT_ROOT / "frontend" / "package.json"
    model_dir = PROJECT_ROOT / "frontend" / "public" / "mediapipe" / "models"
    required_files = {
        "hand_landmarker": model_dir / "hand_landmarker.task",
        "pose_landmarker": model_dir / "pose_landmarker_lite.task",
        "wasm": model_dir / "wasm",
    }
    package_installed = False
    if package_json_path.exists():
        try:
            package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
            deps = {
                **(package_data.get("dependencies") or {}),
                **(package_data.get("devDependencies") or {}),
            }
            package_installed = "@mediapipe/tasks-vision" in deps
        except Exception:
            package_installed = False
    assets = {name: path.exists() for name, path in required_files.items()}
    missing_assets = [name for name, exists in assets.items() if not exists]
    return {
        "package_installed": package_installed,
        "assets_ready": package_installed and not missing_assets,
        "missing_assets": missing_assets,
        "model_dir": str(model_dir),
    }


def _backend_mediapipe_status() -> dict[str, Any]:
    if not _module_available("mediapipe"):
        return {
            "available": False,
            "package_installed": False,
            "api": "unavailable",
            "solutions": False,
            "tasks_vision": False,
            "error": "mediapipe package is not installed",
        }
    tasks_ok, tasks_error = _importable("mediapipe.tasks.python.vision")
    try:
        import mediapipe as mp  # type: ignore

        solutions = getattr(mp, "solutions", None)
        has_solutions = bool(solutions and getattr(solutions, "hands", None) and getattr(solutions, "pose", None))
        runtime_ready = has_solutions
        return {
            "available": runtime_ready,
            "package_installed": True,
            "api": "mediapipe.solutions" if has_solutions else "mediapipe.tasks.python.vision",
            "solutions": bool(has_solutions),
            "tasks_vision": tasks_ok,
            "error": "" if runtime_ready else (
                "installed package exposes mediapipe.tasks.python.vision but no bundled task model assets are configured"
                if tasks_ok
                else (tasks_error or "mediapipe runtime API is unavailable")
            ),
        }
    except Exception as error:
        return {
            "available": False,
            "package_installed": True,
            "api": "mediapipe.tasks.python.vision" if tasks_ok else "mediapipe.solutions",
            "solutions": False,
            "tasks_vision": tasks_ok,
            "error": (
                "installed package exposes mediapipe.tasks.python.vision but no bundled task model assets are configured"
                if tasks_ok
                else str(error)
            ),
        }


def _get_mediapipe_solutions() -> dict[str, Any] | None:
    global _MEDIAPIPE_SOLUTIONS_CACHE
    if _MEDIAPIPE_SOLUTIONS_CACHE is not None:
        return _MEDIAPIPE_SOLUTIONS_CACHE
    try:
        import mediapipe as mp  # type: ignore

        if not getattr(mp, "solutions", None):
            _MEDIAPIPE_SOLUTIONS_CACHE = None
            return None
        _MEDIAPIPE_SOLUTIONS_CACHE = {
            "hands": mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.5,
            ),
            "pose": mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            ),
        }
        return _MEDIAPIPE_SOLUTIONS_CACHE
    except Exception:
        _MEDIAPIPE_SOLUTIONS_CACHE = None
        return None


def get_engine_status() -> dict[str, Any]:
    deepface_available, deepface_error = _importable("deepface.DeepFace")
    deepface_weights_path = _deepface_emotion_weights_path()
    deepface_weights_ready = deepface_weights_path.exists()
    opencv_available = _module_available("cv2")
    insightface_available = _module_available("insightface")
    backend_mediapipe = _backend_mediapipe_status()
    client_mediapipe = _frontend_mediapipe_status()
    mediapipe_available = bool(backend_mediapipe["available"] or client_mediapipe["assets_ready"])
    return {
        "insightface": {
            "available": insightface_available,
            "role": "face_structure_identity_liveness",
            "mode": "reused_from_face_service" if insightface_available else "opencv_proxy",
        },
        "deepface": {
            "available": deepface_available and deepface_weights_ready,
            "package_installed": deepface_available,
            "role": "emotion_signal",
            "mode": "deepface" if deepface_available and deepface_weights_ready else "emotion_proxy",
            "weights_ready": deepface_weights_ready,
            "weights_path": str(deepface_weights_path),
            "error": (
                ""
                if deepface_available and deepface_weights_ready
                else (
                    f"DeepFace emotion weights missing: {deepface_weights_path}"
                    if deepface_available
                    else deepface_error
                )
            ),
            "home": str(PROJECT_DEEPFACE_HOME),
        },
        "opencv": {
            "available": opencv_available,
            "role": "motion_head_attention_signal",
            "mode": "cv2" if opencv_available else "pil_proxy",
        },
        "mediapipe": {
            "available": mediapipe_available,
            "role": "gesture_pose_signal",
            "mode": "python_solutions_api" if backend_mediapipe["available"] else ("client_side_ready" if client_mediapipe["assets_ready"] else "installed_not_runtime_ready"),
            "note": "MediaPipe is integrated through solution/task APIs; browser client_signals are also accepted.",
            "backend": backend_mediapipe,
            "client": client_mediapipe,
        },
        "fallback": {
            "available": True,
            "role": "rule_based_scoring",
            "mode": "always_on",
        },
    }


def _has_current_scene_report_schema(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not REQUIRED_SCENE_SECTIONS.issubset(value.keys()):
        return False
    if value.get("schema_version") != SCENE_REPORT_SCHEMA_VERSION:
        return False
    scores = value.get("scores")
    if not isinstance(scores, dict) or not all(
        key in scores for key in ("face_score", "behavior_score", "attention_score", "final_score", "weights", "formula_mode")
    ):
        return False
    degradation = value.get("degradation")
    if not isinstance(degradation, dict) or not all(key in degradation for key in ("level", "label", "formula_mode", "unavailable_modules")):
        return False
    tool_evidence = value.get("tool_evidence")
    if not isinstance(tool_evidence, dict) or not TOOL_EVIDENCE_KEYS.issubset(tool_evidence.keys()):
        return False
    adapter_status = value.get("adapter_status")
    if not isinstance(adapter_status, dict) or not all(key in adapter_status for key in ("engine", "degradation", "formula_mode", "tool_evidence")):
        return False
    return True


def _landmark_list(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    landmarks = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            landmarks.append(
                {
                    "x": float(item.get("x", 0)),
                    "y": float(item.get("y", 0)),
                    "z": float(item.get("z", 0)),
                    "visibility": float(item.get("visibility", item.get("presence", 1))),
                }
            )
        except Exception:
            continue
    return landmarks


def _client_signal_summary(client_signals: dict[str, Any] | None) -> dict[str, Any]:
    signals = client_signals if isinstance(client_signals, dict) else {}
    hands_raw = signals.get("hands")
    hands = hands_raw if isinstance(hands_raw, list) else []
    hand_landmarks = [_landmark_list(item.get("landmarks") if isinstance(item, dict) else item) for item in hands]
    hand_landmarks = [item for item in hand_landmarks if item]
    pose = _landmark_list(signals.get("pose", {}).get("landmarks") if isinstance(signals.get("pose"), dict) else signals.get("pose"))
    motion = signals.get("motion") if isinstance(signals.get("motion"), dict) else {}
    model_status = signals.get("model_status") if isinstance(signals.get("model_status"), dict) else {}

    hand_confidences = [
        float(item.get("score", item.get("confidence", 0.75)))
        for item in hands
        if isinstance(item, dict)
    ]
    pose_visibility = mean([point["visibility"] for point in pose]) if pose else 0
    motion_score = float(motion.get("motion_score", motion.get("score", 0)) or 0)
    head_offset = float(motion.get("head_offset", 0) or 0)
    gaze_offset = float(motion.get("gaze_offset", 0) or 0)

    return {
        "has_mediapipe": bool(hand_landmarks or pose),
        "hand_count": len(hand_landmarks),
        "hand_confidence": round(mean(hand_confidences), 3) if hand_confidences else None,
        "pose_landmark_count": len(pose),
        "pose_visibility": round(float(pose_visibility), 3),
        "motion_score": round(_clamp(motion_score, 0, 1), 3),
        "head_offset": round(_clamp(head_offset, 0, 1), 3),
        "gaze_offset": round(_clamp(gaze_offset, 0, 1), 3),
        "model_status": model_status,
    }


def _mediapipe_solution_summary(image: Image.Image) -> dict[str, Any]:
    solutions = _get_mediapipe_solutions()
    if not solutions:
        return {
            "has_mediapipe": False,
            "model_status": {"mediapipe": "unavailable", "api": "mediapipe.solutions"},
        }
    try:
        import numpy as np  # type: ignore

        frame_rgb = np.asarray(image.convert("RGB"))
        hand_result = solutions["hands"].process(frame_rgb)
        pose_result = solutions["pose"].process(frame_rgb)
        hand_landmarks = list(getattr(hand_result, "multi_hand_landmarks", None) or [])
        pose_landmarks = getattr(getattr(pose_result, "pose_landmarks", None), "landmark", None) or []
        pose_visibility = mean([float(getattr(point, "visibility", 1) or 0) for point in pose_landmarks]) if pose_landmarks else 0
        return {
            "has_mediapipe": bool(hand_landmarks or pose_landmarks),
            "hand_count": len(hand_landmarks),
            "hand_confidence": None,
            "pose_landmark_count": len(pose_landmarks),
            "pose_visibility": round(float(pose_visibility), 3),
            "model_status": {"mediapipe": "ready", "api": "mediapipe.solutions"},
        }
    except Exception as error:
        return {
            "has_mediapipe": False,
            "model_status": {
                "mediapipe": "unavailable",
                "api": "mediapipe.solutions",
                "error": str(error),
            },
        }


def _deepface_emotion_analysis(image: Image.Image) -> dict[str, Any] | None:
    global _DEEPFACE_ANALYZER
    if _DEEPFACE_ANALYZER is False:
        return None
    try:
        import numpy as np  # type: ignore

        if _DEEPFACE_ANALYZER is None:
            from deepface import DeepFace  # type: ignore

            _DEEPFACE_ANALYZER = DeepFace

        result = _DEEPFACE_ANALYZER.analyze(
            img_path=np.asarray(image.convert("RGB")),
            actions=["emotion"],
            detector_backend="skip",
            enforce_detection=False,
            silent=True,
        )
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict):
            return None
        emotion_scores = result.get("emotion") if isinstance(result.get("emotion"), dict) else {}
        dominant = str(result.get("dominant_emotion") or "").strip() or "unknown"
        confidence = float(emotion_scores.get(dominant, 0) or 0) if isinstance(emotion_scores, dict) else 0
        negative_pressure = sum(
            float(emotion_scores.get(name, 0) or 0)
            for name in ("angry", "fear", "sad", "disgust")
        )
        stability = int(round(_clamp(100 - negative_pressure * 0.45 + confidence * 0.12, 35, 96)))
        tension = int(round(_clamp(negative_pressure * 0.62 + float(emotion_scores.get("surprise", 0) or 0) * 0.28, 0, 100)))
        return {
            "emotion": dominant,
            "tension_score": tension,
            "stability_score": stability,
            "confidence": round(_clamp(confidence / 100, 0.2, 0.95), 3),
            "adapter": "deepface",
            "raw_emotion": {key: round(float(value), 3) for key, value in emotion_scores.items()},
        }
    except Exception:
        _DEEPFACE_ANALYZER = False
        return None


def warmup_deepface_async() -> None:
    global _DEEPFACE_WARMUP_STARTED
    if _DEEPFACE_WARMUP_STARTED or not _deepface_emotion_weights_path().exists():
        return
    _DEEPFACE_WARMUP_STARTED = True

    def _warmup() -> None:
        image = Image.new("RGB", (224, 224), (180, 170, 155))
        _deepface_emotion_analysis(image)

    thread = threading.Thread(target=_warmup, name="deepface-warmup", daemon=True)
    thread.start()


def _degradation_status(summary: dict[str, Any], frame_available: bool, deepface_active: bool | None = None) -> dict[str, Any]:
    engine = get_engine_status()
    unavailable = []
    substitutions = {}
    deepface_ready = engine["deepface"]["available"] if deepface_active is None else bool(deepface_active)
    if not deepface_ready:
        unavailable.append("deepface")
        substitutions["deepface"] = "emotion_proxy"
    if not summary["has_mediapipe"]:
        unavailable.append("mediapipe")
        substitutions["mediapipe"] = "opencv_frame_diff_rules"
    if not engine["opencv"]["available"]:
        unavailable.append("opencv")
        substitutions["opencv"] = "pil_frame_statistics"
    if not frame_available:
        return {
            "level": 4,
            "label": "llm_only",
            "formula_mode": "llm_only",
            "confidence": 0.35,
            "unavailable_modules": ["vision_frame", *unavailable],
            "substitutions": {"vision": "voice_llm_scoring", **substitutions},
        }
    if summary["has_mediapipe"] and deepface_ready and engine["opencv"]["available"]:
        level = 1
    elif summary["has_mediapipe"]:
        level = 2
    else:
        level = 3
    return {
        "level": level,
        "label": {1: "full_ai_chain", 2: "partial_model_fallback", 3: "weak_visual_rules"}[level],
        "formula_mode": "weighted_multimodal",
        "confidence": {1: 0.9, 2: 0.74, 3: 0.58}[level],
        "unavailable_modules": unavailable,
        "substitutions": substitutions,
    }


def _tool_evidence(
    *,
    face_events: list[models.FaceVerificationEvent],
    frame_face_events: list[models.MultimodalEvent],
    micro_events: list[models.MultimodalEvent],
    gesture_events: list[models.MultimodalEvent],
    attention_events: list[models.MultimodalEvent],
) -> dict[str, Any]:
    engine = get_engine_status()
    mediapipe_samples = [
        _event_payload(event).get("signal_summary", {})
        for event in gesture_events
        if isinstance(_event_payload(event).get("signal_summary", {}), dict)
    ]
    mediapipe_hits = [item for item in mediapipe_samples if item.get("has_mediapipe")]
    deepface_events = [
        event for event in micro_events
        if _event_payload(event).get("adapter") == "deepface"
    ]
    return {
        "insightface": {
            "role": "face_identity_liveness_structure",
            "status": "active" if face_events else ("proxy" if frame_face_events else "no_data"),
            "evidence_count": len(face_events) + len(frame_face_events),
            "fallback": "pil_face_presence_proxy" if not face_events and frame_face_events else None,
        },
        "deepface": {
            "role": "emotion_signal",
            "status": "active" if deepface_events else ("proxy" if micro_events else "no_data"),
            "evidence_count": len(micro_events),
            "fallback": None if deepface_events else "emotion_proxy_from_frame_statistics",
        },
        "opencv": {
            "role": "motion_attention_signal",
            "status": "active" if engine["opencv"]["available"] else ("proxy" if attention_events else "no_data"),
            "evidence_count": len(attention_events),
            "fallback": None if engine["opencv"]["available"] else "pil_frame_statistics",
        },
        "mediapipe": {
            "role": "gesture_pose_signal",
            "status": "active" if mediapipe_hits else ("fallback" if gesture_events else "no_data"),
            "evidence_count": len(gesture_events),
            "fallback": None if mediapipe_hits else "rule_based_frame_diff",
            "sample_summary": mediapipe_hits[-1] if mediapipe_hits else (mediapipe_samples[-1] if mediapipe_samples else {}),
        },
    }


def _analyze_frame(frame_data_url: str, client_signals: dict[str, Any] | None = None) -> dict[str, Any]:
    image = _decode_data_url(frame_data_url)
    small = image.resize((96, 96))
    grayscale = small.convert("L")
    stat = ImageStat.Stat(grayscale)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    signal_summary = _client_signal_summary(client_signals)
    if not signal_summary["has_mediapipe"]:
        solution_summary = _mediapipe_solution_summary(image)
        if solution_summary["has_mediapipe"]:
            signal_summary = {
                **signal_summary,
                **solution_summary,
                "motion_score": signal_summary["motion_score"],
                "head_offset": signal_summary["head_offset"],
                "gaze_offset": signal_summary["gaze_offset"],
            }
        else:
            signal_summary["model_status"] = {
                **(signal_summary.get("model_status") or {}),
                "backend_mediapipe": solution_summary.get("model_status"),
            }

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
    emotion_confidence = None
    raw_emotion = None

    deepface_result = _deepface_emotion_analysis(image) if face_detected else None
    if deepface_result:
        emotion = deepface_result["emotion"]
        tension_score = int(deepface_result["tension_score"])
        stability = int(deepface_result["stability_score"])
        emotion_confidence = deepface_result["confidence"]
        raw_emotion = deepface_result.get("raw_emotion")

    if signal_summary["has_mediapipe"]:
        gesture_label = "structured_pose"
        normative = signal_summary["hand_count"] > 0 or signal_summary["pose_visibility"] >= 0.45
        abnormal_motion = signal_summary["motion_score"] > 0.78
    else:
        gesture_label = "open_palm" if face_detected and contrast < 42 else "hands_off_camera"
        abnormal_motion = not face_detected or contrast > 82
        normative = gesture_label == "open_palm"
        if abnormal_motion and face_detected:
            gesture_label = "abnormal_motion"

    attention_score = int(
        round(
            _clamp(
                (90 if face_detected else 38)
                - signal_summary["head_offset"] * 28
                - signal_summary["gaze_offset"] * 24
                - max(0, signal_summary["motion_score"] - 0.55) * 35,
                0,
                100,
            )
        )
    )
    behavior_signal_score = int(
        round(
            _clamp(
                (82 if normative else 50)
                + min(signal_summary["hand_count"], 2) * 5
                + signal_summary["pose_visibility"] * 10
                - (18 if abnormal_motion else 0),
                0,
                100,
            )
        )
    )
    face_signal_score = int(round(_clamp(stability * 0.55 + (100 - tension_score) * 0.25 + attention_score * 0.2, 0, 100)))

    degradation = _degradation_status(signal_summary, True, deepface_active=bool(deepface_result))
    if emotion_confidence is None:
        emotion_confidence = degradation["confidence"]
    adapter_status = {
        "face": "insightface_reused_or_pil_proxy",
        "emotion": "deepface" if deepface_result else "emotion_proxy",
        "motion": "opencv" if get_engine_status()["opencv"]["available"] else "pil_frame_statistics",
        "gesture": "client_mediapipe" if signal_summary["has_mediapipe"] else "rule_based_frame_diff",
    }

    return {
        "face": {
            "present": face_detected,
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "head_stability_score": int(round(_clamp(100 - signal_summary["head_offset"] * 65, 0, 100))),
        },
        "micro_expression": {
            "emotion": emotion,
            "tension_score": tension_score,
            "stability_score": stability,
            "confidence": emotion_confidence,
            "adapter": adapter_status["emotion"],
            "raw_emotion": raw_emotion,
        },
        "gesture": {
            "gesture_type": gesture_label,
            "normative": normative,
            "abnormal": abnormal_motion,
            "continuity_score": behavior_signal_score,
            "adapter": adapter_status["gesture"],
            "signal_summary": signal_summary,
        },
        "attention": {
            "score": attention_score,
            "focused": attention_score >= 70,
            "adapter": adapter_status["motion"],
        },
        "scores": {
            "face_score": face_signal_score,
            "behavior_score": behavior_signal_score,
            "attention_score": attention_score,
            "final_score": int(round(behavior_signal_score * 0.35 + face_signal_score * 0.30 + attention_score * 0.35)),
            "weights": FINAL_SCORE_WEIGHTS,
        },
        "fusion": {
            "emotion_stability": stability,
            "gesture_normative": normative,
            "pose_visibility": signal_summary["pose_visibility"],
            "attention_score": attention_score,
        },
        "degradation": degradation,
        "adapter_status": adapter_status,
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


def record_frame(
    db: Session,
    *,
    session_id: int,
    user: models.User,
    frame_data_url: str,
    client_signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, user)
    analysis = _analyze_frame(frame_data_url, client_signals)
    signal_meta = client_signals.get("_meta") if isinstance(client_signals, dict) and isinstance(client_signals.get("_meta"), dict) else {}
    frame_meta = {
        "frame_id": signal_meta.get("frame_id") or f"server-{session.id}-{datetime.utcnow().timestamp()}",
        "timestamp": signal_meta.get("timestamp") or datetime.utcnow().isoformat(),
        "source": signal_meta.get("source") or "multimodal",
    }

    face_payload = analysis["face"]
    micro_payload = analysis["micro_expression"]
    gesture_payload = analysis["gesture"]
    attention_payload = analysis["attention"]
    record_event(
        db,
        session=session,
        event_type="frame",
        category="face",
        label="present" if face_payload["present"] else "offline",
        score=1.0 if face_payload["present"] else 0.0,
        payload={**face_payload, "score": analysis["scores"]["face_score"], "_meta": frame_meta},
    )
    record_event(
        db,
        session=session,
        event_type="frame",
        category="micro_expression",
        label=micro_payload["emotion"],
        score=float(micro_payload["tension_score"]),
        payload={**micro_payload, "_meta": frame_meta},
    )
    record_event(
        db,
        session=session,
        event_type="frame",
        category="gesture",
        label=gesture_payload["gesture_type"],
        score=float(analysis["scores"]["behavior_score"]),
        payload={**gesture_payload, "_meta": frame_meta},
    )
    record_event(
        db,
        session=session,
        event_type="frame",
        category="attention",
        label="focused" if attention_payload["focused"] else "distracted",
        score=float(attention_payload["score"]),
        payload={**attention_payload, "_meta": frame_meta},
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


def _rubric_weighted_score(items: list[dict[str, Any]]) -> int | None:
    available = [
        (float(item["score"]), float(item["weight"]))
        for item in items
        if item.get("available") and item.get("score") is not None and float(item.get("weight", 0)) > 0
    ]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    return int(round(_clamp(sum(score * weight for score, weight in available) / total_weight, 0, 100)))


def _rubric_item(
    key: str,
    label: str,
    score: float | int | None,
    weight: float,
    evidence: str,
    *,
    available: bool = True,
) -> dict[str, Any]:
    rule = RUBRIC_RULES.get(key, {})
    return {
        "key": key,
        "label": label,
        "score": _as_int_score(score) if available and score is not None else None,
        "weight": weight,
        "available": bool(available and score is not None),
        "evidence": evidence,
        "description": rule.get("description", ""),
        "high_score": rule.get("high_score", ""),
        "deduction": rule.get("deduction", ""),
    }


def _average_payload_score(events: list[models.MultimodalEvent], key: str, fallback_score: bool = True) -> int | None:
    values = []
    for event in events:
        payload = _event_payload(event)
        value = payload.get(key)
        if value is None and fallback_score and event.score is not None:
            value = event.score
        if value is not None:
            values.append(float(value))
    return _as_int_score(mean(values)) if values else None


def _average_payload_value(events: list[models.MultimodalEvent], key: str) -> float | None:
    values = []
    for event in events:
        value = _event_payload(event).get(key)
        if value is not None:
            values.append(float(value))
    return mean(values) if values else None


def _average_signal_value(events: list[models.MultimodalEvent], key: str) -> float | None:
    values = []
    for event in events:
        signal = _event_payload(event).get("signal_summary", {})
        if isinstance(signal, dict) and signal.get(key) is not None:
            values.append(float(signal.get(key)))
    return mean(values) if values else None


def _event_timestamp(event: models.MultimodalEvent) -> datetime:
    meta = _event_payload(event).get("_meta", {})
    timestamp = meta.get("timestamp") if isinstance(meta, dict) else None
    if timestamp:
        try:
            return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
    return event.created_at or datetime.utcnow()


def _event_frame_id(event: models.MultimodalEvent) -> str:
    meta = _event_payload(event).get("_meta", {})
    if isinstance(meta, dict) and meta.get("frame_id"):
        return str(meta["frame_id"])
    return f"{event.created_at.isoformat() if event.created_at else 'unknown'}:{event.category}:{event.id}"


def _build_evidence_layer(multimodal_events: list[models.MultimodalEvent], face_events: list[models.FaceVerificationEvent]) -> dict[str, Any]:
    frame_map: dict[str, dict[str, Any]] = {}
    for event in multimodal_events:
        frame_id = _event_frame_id(event)
        frame = frame_map.setdefault(
            frame_id,
            {
                "frame_id": frame_id,
                "timestamp": _event_timestamp(event).isoformat(),
                "categories": {},
            },
        )
        frame["categories"][event.category] = {
            "label": event.label,
            "score": event.score,
            "payload": _event_payload(event),
        }

    frames = sorted(frame_map.values(), key=lambda item: item["timestamp"])
    windows = []
    if frames:
        started = datetime.fromisoformat(frames[0]["timestamp"])
        buckets: dict[int, list[dict[str, Any]]] = {}
        for frame in frames:
            current = datetime.fromisoformat(frame["timestamp"])
            bucket = int((current - started).total_seconds() // 10)
            buckets.setdefault(bucket, []).append(frame)
        for bucket, items in sorted(buckets.items()):
            window_start = started.timestamp() + bucket * 10
            window_end = window_start + 10
            total = len(items)
            face_present = sum(1 for item in items if item["categories"].get("face", {}).get("label") == "present")
            focused = sum(1 for item in items if item["categories"].get("attention", {}).get("label") == "focused")
            mediapipe_hits = 0
            deepface_hits = 0
            pose_values = []
            hand_values = []
            tension_values = []
            motion_values = []
            for item in items:
                micro = item["categories"].get("micro_expression", {}).get("payload", {})
                if micro.get("adapter") == "deepface":
                    deepface_hits += 1
                if micro.get("tension_score") is not None:
                    tension_values.append(float(micro["tension_score"]))
                gesture = item["categories"].get("gesture", {}).get("payload", {})
                signal = gesture.get("signal_summary", {}) if isinstance(gesture, dict) else {}
                if isinstance(signal, dict):
                    if signal.get("has_mediapipe"):
                        mediapipe_hits += 1
                    if signal.get("pose_visibility") is not None:
                        pose_values.append(float(signal["pose_visibility"]))
                    if signal.get("hand_count") is not None:
                        hand_values.append(float(signal["hand_count"]))
                    if signal.get("motion_score") is not None:
                        motion_values.append(float(signal["motion_score"]))
            windows.append(
                {
                    "index": bucket,
                    "start": datetime.fromtimestamp(window_start).isoformat(),
                    "end": datetime.fromtimestamp(window_end).isoformat(),
                    "sample_count": total,
                    "presence_rate": _percent(face_present, total),
                    "focused_rate": _percent(focused, total),
                    "deepface_rate": _percent(deepface_hits, total),
                    "mediapipe_rate": _percent(mediapipe_hits, total),
                    "avg_pose_visibility": round(mean(pose_values), 3) if pose_values else None,
                    "avg_hand_count": round(mean(hand_values), 3) if hand_values else None,
                    "avg_tension": round(mean(tension_values), 2) if tension_values else None,
                    "tension_volatility": round(pstdev(tension_values), 2) if len(tension_values) > 1 else 0 if tension_values else None,
                    "avg_motion": round(mean(motion_values), 3) if motion_values else None,
                }
            )

    total_frames = len(frames)
    expected = max(total_frames, len(face_events), 1)
    confidence = {
        "overall": round(
            _clamp(
                (total_frames / expected) * 0.35
                + (sum(1 for frame in frames if "micro_expression" in frame["categories"]) / expected) * 0.2
                + (sum(1 for frame in frames if "gesture" in frame["categories"]) / expected) * 0.25
                + (sum(1 for frame in frames if "attention" in frame["categories"]) / expected) * 0.2,
                0,
                1,
            ),
            3,
        ),
        "effective_frame_count": total_frames,
        "face_reference_count": len(face_events),
        "note": "评分基于同帧 frame_id/timestamp 融合；样本不足或模型缺失会降低置信度。",
    }
    return {
        "version": "evidence_layer/v1",
        "frame_count": total_frames,
        "frames_with_all_visual_categories": sum(
            1 for frame in frames if {"face", "micro_expression", "gesture", "attention"}.issubset(frame["categories"].keys())
        ),
        "windows": windows,
        "confidence": confidence,
    }


def _build_scene_rubric(
    *,
    face_sample_count: int,
    frame_face_events: list[models.MultimodalEvent],
    micro_events: list[models.MultimodalEvent],
    gesture_events: list[models.MultimodalEvent],
    attention_events: list[models.MultimodalEvent],
    face_pass_rate: int | None,
    monitor_fail_rate: int | None,
    leave_rate: int | None,
    abnormal_leave_count: int,
    stability_score: int | None,
    avg_tension: float | None,
    volatility: float | None,
    gesture_score: int | None,
    voice_score: int | None,
    normative_gestures: list[models.MultimodalEvent],
    abnormal_gestures: list[models.MultimodalEvent],
    attention_score: int | None,
) -> dict[str, Any]:
    head_stability = _average_payload_score(frame_face_events, "head_stability_score", fallback_score=False)
    brightness = _average_payload_value(frame_face_events, "brightness")
    contrast = _average_payload_value(frame_face_events, "contrast")
    quality_score = None
    if brightness is not None and contrast is not None:
        brightness_score = 100 - min(55, abs(brightness - 132) * 0.65)
        contrast_score = 100 - min(45, abs(contrast - 38) * 0.9)
        quality_score = _clamp(brightness_score * 0.55 + contrast_score * 0.45, 0, 100)
    pressure_score = None
    if avg_tension is not None:
        pressure_score = 100 - max(0, avg_tension - 35) * 1.15
        if volatility is not None:
            pressure_score -= min(28, volatility * 0.7)
        pressure_score = _clamp(pressure_score, 0, 100)

    hand_confidence = _average_signal_value(gesture_events, "hand_confidence")
    hand_count = _average_signal_value(gesture_events, "hand_count")
    pose_visibility = _average_signal_value(gesture_events, "pose_visibility")
    motion_score = _average_signal_value(gesture_events, "motion_score")
    head_offset = _average_signal_value(gesture_events, "head_offset")
    gaze_offset = _average_signal_value(gesture_events, "gaze_offset")
    normative_rate = _percent(len(normative_gestures), len(gesture_events))
    abnormal_rate = _percent(len(abnormal_gestures), len(gesture_events))
    hand_visible_score = None
    if hand_count is not None or hand_confidence is not None:
        hand_visible_score = _clamp(
            min(100, (hand_count or 0) * 42) * 0.45 + ((hand_confidence or 0.45) * 100) * 0.55,
            0,
            100,
        )
    pose_score = _clamp((pose_visibility or 0) * 100, 0, 100) if pose_visibility is not None else None
    continuity_score = None
    if gesture_score is not None or motion_score is not None:
        continuity_score = (gesture_score if gesture_score is not None else 78) - max(0, (motion_score or 0) - 0.35) * 50
    minor_motion_score = None
    if abnormal_rate is not None or motion_score is not None:
        minor_motion_score = 100 - (abnormal_rate or 0) * 0.75 - max(0, (motion_score or 0) - 0.45) * 45

    focused_rate = _percent(len([event for event in attention_events if event.label == "focused"]), len(attention_events))
    gaze_score = None
    if gaze_offset is not None:
        gaze_score = 100 - gaze_offset * 100
    head_attention_score = None
    if head_offset is not None:
        head_attention_score = 100 - head_offset * 95
    distraction_score = None
    if motion_score is not None:
        distraction_score = 100 - max(0, motion_score - 0.25) * 110

    face_items = [
        _rubric_item("identity_presence", "身份在场与离镜控制", face_pass_rate, 0.24, f"在场/核验通过率 {face_pass_rate if face_pass_rate is not None else '无'}%，异常离镜 {abnormal_leave_count} 次", available=face_sample_count > 0),
        _rubric_item("emotion_stability", "情绪稳定性", stability_score, 0.26, f"DeepFace/代理情绪稳定分 {stability_score if stability_score is not None else '无'}", available=bool(micro_events)),
        _rubric_item("pressure_control", "压力波动控制", pressure_score, 0.20, f"平均压力 {int(round(avg_tension)) if avg_tension is not None else '无'}，波动 {round(float(volatility), 1) if volatility is not None else '无'}", available=bool(micro_events)),
        _rubric_item("head_stability", "头部稳定与画面正对", head_stability, 0.18, f"头部稳定均值 {head_stability if head_stability is not None else '无'}", available=bool(frame_face_events)),
        _rubric_item("image_quality", "光线与画面质量", quality_score, 0.12, f"亮度 {round(brightness, 1) if brightness is not None else '无'}，对比度 {round(contrast, 1) if contrast is not None else '无'}", available=bool(frame_face_events)),
    ]
    behavior_items = [
        _rubric_item("communication_gesture", "规范沟通姿态", normative_rate, 0.24, f"规范姿态/手势占比 {normative_rate if normative_rate is not None else '无'}%", available=bool(gesture_events)),
        _rubric_item("hand_visibility", "手部可见与可信度", hand_visible_score, 0.18, f"平均手数 {round(hand_count, 2) if hand_count is not None else '无'}，手部置信度 {round(hand_confidence, 2) if hand_confidence is not None else '无'}", available=bool(gesture_events)),
        _rubric_item("posture_visibility", "身体姿态可见", pose_score, 0.18, f"姿态可见度 {round(pose_visibility, 2) if pose_visibility is not None else '无'}", available=bool(gesture_events)),
        _rubric_item("action_continuity", "动作连贯性", continuity_score, 0.20, f"动作连续分 {gesture_score if gesture_score is not None else '无'}，画面运动 {round(motion_score, 2) if motion_score is not None else '无'}", available=bool(gesture_events)),
        _rubric_item("minor_motion_control", "小动作与异常动作控制", minor_motion_score, 0.20, f"异常动作率 {abnormal_rate if abnormal_rate is not None else '无'}%", available=bool(gesture_events)),
    ]
    attention_items = [
        _rubric_item("continuous_presence", "持续在场", 100 - (leave_rate or 0) - min(35, abnormal_leave_count * 4), 0.26, f"离镜率 {leave_rate if leave_rate is not None else 0}%，异常 {abnormal_leave_count} 次", available=bool(frame_face_events)),
        _rubric_item("focused_rate", "持续专注判定", focused_rate, 0.24, f"专注帧占比 {focused_rate if focused_rate is not None else '无'}%", available=bool(attention_events)),
        _rubric_item("gaze_stability", "视线/注视稳定", gaze_score, 0.20, f"视线偏移 {round(gaze_offset, 2) if gaze_offset is not None else '无'}", available=gaze_offset is not None),
        _rubric_item("head_attention", "头部朝向稳定", head_attention_score, 0.16, f"头部偏移 {round(head_offset, 2) if head_offset is not None else '无'}", available=head_offset is not None),
        _rubric_item("distraction_control", "分心动作控制", distraction_score, 0.14, f"画面运动 {round(motion_score, 2) if motion_score is not None else '无'}", available=motion_score is not None),
    ]
    face_score = _rubric_weighted_score(face_items)
    behavior_score = _rubric_weighted_score(behavior_items)
    attention_score = _rubric_weighted_score(attention_items)
    return {
        "version": SCENE_RUBRIC_VERSION,
        "principle": "面向警情处置训练，按可观察的身份在场、情绪压力、规范姿态、动作连贯、持续专注进行证据化评分。",
        "dimensions": {
            "face": {"label": "表情与心理状态评分", "score": face_score, "items": face_items},
            "behavior": {"label": "行为动作评分", "score": behavior_score, "items": behavior_items},
            "attention": {"label": "注意力与交互评分", "score": attention_score, "items": attention_items},
        },
    }


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
    attention_events = [event for event in multimodal_events if event.category == "attention"]
    voice_events = [event for event in multimodal_events if event.category == "voice"]

    passed_face = [event for event in face_events if event.status == "passed"]
    failed_face = [event for event in face_events if event.status == "failed"]
    monitor_face_events = [event for event in face_events if event.event_type != "verify"]
    failed_monitor_face = [event for event in monitor_face_events if event.status == "failed"]
    passed_monitor_face = [event for event in monitor_face_events if event.status == "passed"]
    offline_frames = [event for event in frame_face_events if event.label == "offline"]
    present_frames = [event for event in frame_face_events if event.label == "present"]
    abnormal_leave_count = len(offline_frames) + sum(
        1
        for event in failed_face
        if any(keyword in str(event.reason or "") for keyword in ("未检测", "离开", "offline", "No face", "鏈娴?", "绂诲紑"))
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
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else NO_DATA_TEXT

    normative_gestures = [event for event in gesture_events if event.label in {"open_palm", "structured_pose"}]
    abnormal_gestures = [
        event for event in gesture_events if event.label in {"hands_off_camera", "frequent_leave", "abnormal_motion"}
    ]

    utterance_events = [event for event in voice_events if event.event_type in {"utterance_end", "hangup_tail"}]
    transcripts = [_event_payload(event).get("transcript", "") for event in utterance_events]
    repeated_count = sum(1 for event in voice_events if _event_payload(event).get("repeated") or event.label == "repeat")
    durations = [int(event.duration_ms or 0) for event in utterance_events if event.duration_ms]
    avg_duration_ms = int(mean(durations)) if durations else 0
    interruption_count = sum(1 for event in voice_events if event.event_type in {"interruption", "mute", "error"} or event.label in {"interruption", "mute", "error"})
    complete_utterance_count = sum(1 for text in transcripts if len(str(text).strip()) >= 4)
    voice_completeness = int(round((complete_utterance_count / max(len(utterance_events), 1)) * 100)) if utterance_events else None
    continuous_expression = bool(len(utterance_events) >= 2 and interruption_count == 0) if utterance_events else None

    face_score = _average_payload_score(frame_face_events, "score")
    if face_score is None and face_sample_count:
        face_score = 100
        if face_pass_rate is not None:
            face_score -= max(0, 100 - face_pass_rate) * 0.55
        if monitor_fail_rate is not None:
            face_score -= monitor_fail_rate * 0.35
        if leave_rate is not None:
            face_score -= leave_rate * 0.3
        face_score -= min(25, abnormal_leave_count * 4)
        if face_events and not passed_face:
            face_score -= 20
        face_score = int(_clamp(face_score, 0, 100))

    gesture_score = _average_payload_score(gesture_events, "continuity_score")
    if gesture_score is None and gesture_events:
        normative_rate = len(normative_gestures) / max(len(gesture_events), 1)
        abnormal_rate = len(abnormal_gestures) / max(len(gesture_events), 1)
        gesture_score = normative_rate * 75 + (1 - abnormal_rate) * 25
        gesture_score -= min(35, len(abnormal_gestures) * 3)
        gesture_score = int(_clamp(gesture_score, 0, 100))

    attention_score = _average_payload_score(attention_events, "score")
    if attention_score is None and frame_face_events:
        attention_score = int(_clamp(95 - (leave_rate or 0) * 0.65 - min(35, abnormal_leave_count * 6), 0, 100))

    voice_score = None
    if utterance_events:
        voice_score = int(_clamp((voice_completeness or 0) - min(25, interruption_count * 8) - min(20, repeated_count * 6), 0, 100))

    fallback_behavior_score = _weighted_score([
        (gesture_score, 0.75),
        (stability_score, 0.25),
    ])

    rubric = _build_scene_rubric(
        face_sample_count=face_sample_count,
        frame_face_events=frame_face_events,
        micro_events=micro_events,
        gesture_events=gesture_events,
        attention_events=attention_events,
        face_pass_rate=face_pass_rate,
        monitor_fail_rate=monitor_fail_rate,
        leave_rate=leave_rate,
        abnormal_leave_count=abnormal_leave_count,
        stability_score=stability_score,
        avg_tension=avg_tension,
        volatility=volatility,
        gesture_score=gesture_score,
        voice_score=voice_score,
        normative_gestures=normative_gestures,
        abnormal_gestures=abnormal_gestures,
        attention_score=attention_score,
    )
    rubric_dimensions = rubric["dimensions"]
    face_score = rubric_dimensions["face"]["score"] if rubric_dimensions["face"]["score"] is not None else face_score
    behavior_score = rubric_dimensions["behavior"]["score"] if rubric_dimensions["behavior"]["score"] is not None else fallback_behavior_score
    attention_score = rubric_dimensions["attention"]["score"] if rubric_dimensions["attention"]["score"] is not None else attention_score

    visual_scores = [score for score in (face_score, behavior_score if gesture_events else None, attention_score) if isinstance(score, int)]
    if not visual_scores and voice_score is not None:
        final_score = voice_score
        formula_mode = "llm_only"
        degradation = {
            "level": 4,
            "label": "llm_only",
            "formula_mode": "llm_only",
            "confidence": 0.35,
            "unavailable_modules": ["vision_frame"],
            "substitutions": {"vision": "voice_llm_scoring"},
        }
    else:
        final_score = _weighted_score([
            (behavior_score if isinstance(behavior_score, int) and behavior_score > 0 else None, FINAL_SCORE_WEIGHTS["behavior"]),
            (face_score, FINAL_SCORE_WEIGHTS["face"]),
            (attention_score, FINAL_SCORE_WEIGHTS["attention"]),
        ])
        formula_mode = "weighted_multimodal"
        has_mediapipe = any(_event_payload(event).get("signal_summary", {}).get("has_mediapipe") for event in gesture_events)
        has_deepface = any(_event_payload(event).get("adapter") == "deepface" for event in micro_events)
        degradation = _degradation_status({"has_mediapipe": has_mediapipe}, bool(frame_face_events), deepface_active=has_deepface)

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
    if degradation["level"] >= 3:
        risk_tips.append("部分视觉模型不可用，已按降级规则生成实景评分")
    if not risk_tips:
        risk_tips.append("未发现明显实景行为风险")

    tool_evidence = _tool_evidence(
        face_events=face_events,
        frame_face_events=frame_face_events,
        micro_events=micro_events,
        gesture_events=gesture_events,
        attention_events=attention_events,
    )
    evidence_layer = _build_evidence_layer(multimodal_events, face_events)
    adapter_status = {
        "engine": get_engine_status(),
        "degradation": degradation,
        "formula_mode": formula_mode,
        "tool_evidence": tool_evidence,
        "confidence": evidence_layer["confidence"],
    }
    report = {
        "schema_version": SCENE_REPORT_SCHEMA_VERSION,
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
            "pressure_analysis": NO_DATA_TEXT if not micro_events else ("压力波动较明显" if (volatility or 0) >= 18 else "压力波动处于可控范围"),
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
        "attention": {
            "score": attention_score,
            "focused_rate": _percent(len([event for event in attention_events if event.label == "focused"]), len(attention_events)),
            "sample_count": len(attention_events),
            "has_data": bool(attention_events or frame_face_events),
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
        "scores": {
            "face_score": face_score,
            "behavior_score": behavior_score,
            "attention_score": attention_score,
            "final_score": final_score,
            "weights": FINAL_SCORE_WEIGHTS,
            "formula": "Final Score = 0.35 * Behavior + 0.30 * Face + 0.35 * Attention",
            "formula_mode": formula_mode,
        },
        "rubric": rubric,
        "score_breakdown": {
            "face": rubric_dimensions["face"]["items"],
            "behavior": rubric_dimensions["behavior"]["items"],
            "attention": rubric_dimensions["attention"]["items"],
        },
        "evidence_layer": evidence_layer,
        "overall": {
            "behavior_score": behavior_score,
            "face_score": face_score,
            "attention_score": attention_score,
            "final_score": final_score,
            "risk_level": _risk_level(final_score),
            "score_weights": FINAL_SCORE_WEIGHTS,
            "risk_tips": risk_tips,
            "abnormal_records": abnormal_records,
            "generated_at": datetime.utcnow().isoformat(),
            "has_data": any(isinstance(score, int) for score in (face_score, stability_score, gesture_score, voice_score, attention_score)),
        },
        "degradation": degradation,
        "tool_evidence": tool_evidence,
        "adapter_status": adapter_status,
        "meta": {
            "sample_count": len(frame_face_events),
            "deepface_sample_count": len(micro_events),
            "opencv_sample_count": len(attention_events),
            "mediapipe_sample_count": len(gesture_events),
            "voice_event_count": len(voice_events),
            "adapter_status": degradation["label"],
            "confidence": evidence_layer["confidence"],
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
    metric.face_score = face_score
    metric.behavior_score = behavior_score
    metric.attention_score = attention_score
    metric.final_score = final_score
    metric.adapter_status_json = _json_dumps(adapter_status)
    metric.risk_level = report["overall"]["risk_level"]
    metric.updated_at = datetime.utcnow()
    db.add(metric)
    db.commit()
    return report


def append_scene_performance_report(db: Session, session_id: int, report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return report
    existing_report = report.get("scene_performance_report")
    if _has_current_scene_report_schema(existing_report):
        return report
    try:
        report["scene_performance_report"] = build_scene_performance_report(db, session_id)
    except Exception as error:
        engine_status = get_engine_status()
        fallback_tool_evidence = {
            "insightface": {"role": "face_identity_liveness_structure", "status": "no_data", "evidence_count": 0, "fallback": "report_generation_failed"},
            "deepface": {"role": "emotion_signal", "status": "no_data", "evidence_count": 0, "fallback": "report_generation_failed"},
            "opencv": {"role": "motion_attention_signal", "status": "no_data", "evidence_count": 0, "fallback": "report_generation_failed"},
            "mediapipe": {"role": "gesture_pose_signal", "status": "no_data", "evidence_count": 0, "fallback": "report_generation_failed"},
        }
        fallback_degradation = {
            "level": 4,
            "label": "fallback_error",
            "formula_mode": "fallback_error",
            "confidence": 0,
            "unavailable_modules": ["multimodal_report"],
            "substitutions": {},
        }
        fallback_rubric = {
            "version": SCENE_RUBRIC_VERSION,
            "principle": "实景评分细则暂不可用，报告生成进入兜底模式。",
            "dimensions": {
                "face": {"label": "表情与心理状态评分", "score": None, "items": []},
                "behavior": {"label": "行为动作评分", "score": 0, "items": []},
                "attention": {"label": "注意力与交互评分", "score": None, "items": []},
            },
        }
        fallback_evidence_layer = {
            "version": "evidence_layer/v1",
            "frame_count": 0,
            "frames_with_all_visual_categories": 0,
            "windows": [],
            "confidence": {
                "overall": 0,
                "effective_frame_count": 0,
                "face_reference_count": 0,
                "note": "实景证据层生成失败。",
            },
        }
        report["scene_performance_report"] = {
            "schema_version": SCENE_REPORT_SCHEMA_VERSION,
            "face": {"is_self": None, "presence_duration_seconds": None, "abnormal_leave_count": None, "has_data": False},
            "micro_expression": {"stability_score": None, "tension_curve": [], "pressure_analysis": NO_DATA_TEXT, "has_data": False},
            "gesture": {
                "has_normative_communication_gesture": None,
                "frequent_leave_camera": None,
                "has_abnormal_action": None,
                "has_data": False,
            },
            "attention": {"score": None, "has_data": False},
            "voice": {
                "completeness_score": None,
                "continuous_expression": None,
                "interruption_count": None,
                "repeat_count": None,
                "has_data": False,
            },
            "scores": {
                "face_score": None,
                "behavior_score": 0,
                "attention_score": None,
                "final_score": 0,
                "weights": FINAL_SCORE_WEIGHTS,
                "formula_mode": "fallback_error",
            },
            "overall": {
                "behavior_score": 0,
                "face_score": None,
                "attention_score": None,
                "final_score": 0,
                "risk_level": "unknown",
                "risk_tips": ["实景表现数据暂不可用"],
                "abnormal_records": [str(error)],
                "generated_at": datetime.utcnow().isoformat(),
                "has_data": False,
            },
            "rubric": fallback_rubric,
            "score_breakdown": {"face": [], "behavior": [], "attention": []},
            "evidence_layer": fallback_evidence_layer,
            "degradation": fallback_degradation,
            "tool_evidence": fallback_tool_evidence,
            "adapter_status": {
                "engine": engine_status,
                "degradation": fallback_degradation,
                "formula_mode": "fallback_error",
                "tool_evidence": fallback_tool_evidence,
                "confidence": fallback_evidence_layer["confidence"],
            },
            "meta": {"adapter_status": "fallback"},
        }
    return report
