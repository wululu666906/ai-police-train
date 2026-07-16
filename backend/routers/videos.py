"""
视频实训模块 - 后端路由
第一阶段：视频上传、管理、节点配置、学员端视频展厅

路由顺序说明：固定路径必须定义在动态路径（/{video_id}）之前，
否则 FastAPI 会把固定路径段（如 "upload"、"admin"、"student"）当整数解析而报错。
"""
import json
import os
import shutil
import time
import subprocess
import threading
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user
from services import video_auto_config_service

router = APIRouter(prefix="/videos", tags=["Videos"])

# 静态文件存储根目录
VIDEOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "videos")
THUMBNAILS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "thumbnails")
AUTO_IMPORT_DIR = os.getenv("VIDEO_AUTO_IMPORT_DIR") or os.path.join(VIDEOS_DIR, "auto_upload")
_configured_ffmpeg = os.getenv("FFMPEG_BINARY", "").strip()
if _configured_ffmpeg and not os.path.isabs(_configured_ffmpeg):
    _configured_ffmpeg = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", _configured_ffmpeg))
FFMPEG_BINARY = (
    _configured_ffmpeg
    if _configured_ffmpeg and (os.path.isfile(_configured_ffmpeg) or shutil.which(_configured_ffmpeg))
    else shutil.which("ffmpeg") or "ffmpeg"
)
FFPROBE_BINARY = os.getenv("FFPROBE_BINARY", "").strip()
if not FFPROBE_BINARY and os.path.isabs(FFMPEG_BINARY):
    _ffprobe_candidate = os.path.join(os.path.dirname(FFMPEG_BINARY), "ffprobe.exe" if os.name == "nt" else "ffprobe")
    FFPROBE_BINARY = _ffprobe_candidate if os.path.exists(_ffprobe_candidate) else "ffprobe"
FFPROBE_BINARY = FFPROBE_BINARY or shutil.which("ffprobe") or "ffprobe"

ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024   # 2 GB
MAX_THUMBNAIL_SIZE = 10 * 1024 * 1024      # 10 MB
ALLOWED_VIDEO_EXTS = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi"}
AUTO_IMPORT_SCAN_INTERVAL_SECONDS = 10
VIDEO_AUTO_ANALYZE = os.getenv("VIDEO_AUTO_ANALYZE", "true").strip().lower() not in {"0", "false", "no"}
_LAST_AUTO_IMPORT_SCAN_AT = 0.0
_LAST_AUTO_IMPORT_SUMMARY = {
    "watched_dir": AUTO_IMPORT_DIR,
    "imported_count": 0,
    "skipped_count": 0,
    "detected_count": 0,
}


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

def _require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return current_user


def _video_url(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    return f"/static/videos/{file_path}"


def _thumbnail_url(thumbnail_path: Optional[str]) -> Optional[str]:
    if not thumbnail_path:
        return None
    return f"/static/thumbnails/{thumbnail_path}"


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/")


def _guess_title_from_filename(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    normalized = stem.replace("_", " ").replace("-", " ").strip()
    return normalized or stem or "\u672a\u547d\u540d\u89c6\u9891"


def _infer_video_type_from_path(file_path: str) -> str:
    lowered = _normalize_rel_path(file_path).lower()
    if "/interactive/" in lowered or lowered.startswith("interactive/") or "/\u5b9e\u8bad/" in lowered:
        return "interactive"
    return "teaching"


def _infer_video_status_from_path(file_path: str) -> str:
    lowered = _normalize_rel_path(file_path).lower()
    if "/published/" in lowered or lowered.startswith("published/"):
        return "published"
    if "/archived/" in lowered or lowered.startswith("archived/"):
        return "archived"
    return "draft"


def _infer_tags_from_path(file_path: str) -> list[str]:
    parts = [part for part in _normalize_rel_path(os.path.dirname(file_path)).split("/") if part]
    skip_parts = {"auto_upload", "interactive", "teaching", "published", "archived", "draft"}
    tags = ["\u81ea\u52a8\u5bfc\u5165"]
    for part in parts:
        if part.lower() in skip_parts:
            continue
        if part not in tags:
            tags.append(part)
    return tags


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _infer_video_type_from_name(filename: str) -> str:
    title = _guess_title_from_filename(filename)
    interactive_keywords = [
        "interactive", "\u5b9e\u8bad", "\u8bad\u7ec3", "\u8003\u6838", "\u6f14\u7ec3", "\u6267\u6cd5", "\u5904\u7f6e", "\u76d8\u67e5", "\u95ee\u7b54", "\u62e6\u622a",
    ]
    return "interactive" if _contains_any(title, interactive_keywords) else "teaching"


def _merge_tags(*tag_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in tag_groups:
        for tag in group:
            if tag and tag not in merged:
                merged.append(tag)
    return merged


def _infer_scene_profile(title: str) -> dict:
    normalized = title.lower()
    profiles = []
    profiles.append({
        "match": ["\u4ea4\u901a", "\u62e6\u505c", "\u67e5\u8f66", "\u8def\u68c0"],
        "briefing": "\u7cfb\u7edf\u5df2\u6309\u4ea4\u901a\u6267\u6cd5\u573a\u666f\u81ea\u52a8\u5efa\u6a21\uff0c\u5efa\u8bae\u91cd\u70b9\u68c0\u67e5\u7ad9\u4f4d\u5b89\u5168\u3001\u62e6\u505c\u793a\u610f\u3001\u8bc1\u4ef6\u67e5\u9a8c\u548c\u89c4\u8303\u544a\u77e5\u3002",
        "tags": ["\u4ea4\u901a\u6267\u6cd5", "\u8f66\u8f86\u68c0\u67e5"],
        "nodes": [
            {
                "title": "\u5b89\u5168\u793a\u610f\u505c\u8f66",
                "instruction": "\u8bf7\u89c4\u8303\u793a\u610f\u76ee\u6807\u8f66\u8f86\u9760\u8fb9\u505c\u8f66\uff0c\u5e76\u4fdd\u6301\u5b89\u5168\u7ad9\u4f4d\u3002",
                "gesture_hint": "\u4f7f\u7528\u62e6\u505c\u6216\u505c\u6b62\u624b\u52bf\uff0c\u52a8\u4f5c\u6e05\u6670\u7a33\u5b9a\u3002",
                "speech_hint": "\u8bf7\u9760\u8fb9\u505c\u8f66\uff0c\u914d\u5408\u68c0\u67e5\u3002",
                "required_gesture": "stop_signal",
                "required_keywords": ["\u9760\u8fb9\u505c\u8f66", "\u914d\u5408\u68c0\u67e5"],
                "prop_label": "\u6267\u6cd5\u6307\u6325\u624b\u52bf",
            },
            {
                "title": "\u51fa\u793a\u8bc1\u4ef6\u5e76\u8868\u660e\u8eab\u4efd",
                "instruction": "\u8bf7\u51fa\u793a\u6267\u6cd5\u8bc1\u4ef6\uff0c\u5e76\u5411\u5bf9\u65b9\u8bf4\u660e\u8eab\u4efd\u4e0e\u6267\u6cd5\u76ee\u7684\u3002",
                "gesture_hint": "\u5c06\u8bc1\u4ef6\u7a33\u5b9a\u5c55\u793a\u5728\u80f8\u524d\u4e2d\u90e8\uff0c\u4fbf\u4e8e\u5bf9\u65b9\u8fa8\u8ba4\u3002",
                "speech_hint": "\u60a8\u597d\uff0c\u6211\u662f\u6267\u52e4\u6c11\u8b66\uff0c\u8bf7\u51fa\u793a\u76f8\u5173\u8bc1\u4ef6\u3002",
                "required_gesture": "show_id",
                "required_keywords": ["\u6c11\u8b66", "\u8bf7\u51fa\u793a"],
                "prop_label": "\u68c0\u67e5\u8bc1\u4ef6",
            },
            {
                "title": "\u8bf4\u660e\u68c0\u67e5\u4e8b\u9879",
                "instruction": "\u8bf7\u8bf4\u660e\u672c\u6b21\u68c0\u67e5\u4f9d\u636e\uff0c\u4ee5\u53ca\u5bf9\u65b9\u9700\u8981\u914d\u5408\u7684\u4e8b\u9879\u3002",
                "speech_hint": "\u73b0\u8fdb\u884c\u4f8b\u884c\u68c0\u67e5\uff0c\u8bf7\u914d\u5408\u51fa\u793a\u9a7e\u9a76\u8bc1\u548c\u884c\u9a76\u8bc1\u3002",
                "required_keywords": ["\u4f8b\u884c\u68c0\u67e5", "\u9a7e\u9a76\u8bc1", "\u884c\u9a76\u8bc1"],
                "node_type": "voice_qa",
            },
        ],
    })
    profiles.append({
        "match": ["\u8bc1\u4ef6", "\u8eab\u4efd", "\u76d8\u67e5", "\u6838\u9a8c"],
        "briefing": "\u7cfb\u7edf\u5df2\u6309\u8eab\u4efd\u6838\u9a8c\u573a\u666f\u81ea\u52a8\u5efa\u6a21\uff0c\u5efa\u8bae\u91cd\u70b9\u5173\u6ce8\u656c\u793c\u3001\u8bc1\u4ef6\u51fa\u793a\u3001\u53e3\u5934\u6838\u67e5\u548c\u7ed3\u679c\u544a\u77e5\u3002",
        "tags": ["\u8eab\u4efd\u6838\u9a8c", "\u8bc1\u4ef6\u68c0\u67e5"],
        "nodes": [
            {
                "title": "\u89c4\u8303\u656c\u793c\u4e0e\u8eab\u4efd\u8868\u660e",
                "instruction": "\u8bf7\u5148\u656c\u793c\uff0c\u518d\u6e05\u6670\u8868\u660e\u6267\u6cd5\u8eab\u4efd\u3002",
                "gesture_hint": "\u53f3\u624b\u62ac\u81f3\u7709\u5fc3\u9644\u8fd1\u5b8c\u6210\u6807\u51c6\u656c\u793c\u3002",
                "speech_hint": "\u60a8\u597d\uff0c\u6211\u662f\u6267\u52e4\u6c11\u8b66\uff0c\u8bf7\u914d\u5408\u8eab\u4efd\u68c0\u67e5\u3002",
                "required_gesture": "salute",
                "required_keywords": ["\u6c11\u8b66", "\u8eab\u4efd\u68c0\u67e5"],
            },
            {
                "title": "\u51fa\u793a\u8bc1\u4ef6",
                "instruction": "\u8bf7\u51fa\u793a\u6267\u6cd5\u8bc1\u4ef6\uff0c\u5e76\u4fdd\u6301\u8bc1\u4ef6\u5c55\u793a\u52a8\u4f5c\u7a33\u5b9a\u3002",
                "gesture_hint": "\u53cc\u624b\u5728\u80f8\u524d\u4e2d\u90e8\u7a33\u5b9a\u5c55\u793a\u8bc1\u4ef6\u3002",
                "required_gesture": "show_id",
                "prop_label": "\u6267\u6cd5\u8bc1\u4ef6",
                "prop_hint": "\u8bf7\u5148\u53d6\u51fa\u6267\u6cd5\u8bc1\u4ef6\uff0c\u518d\u8fdb\u884c\u8eab\u4efd\u6838\u9a8c\u8bf4\u660e\u3002",
            },
            {
                "title": "\u6838\u9a8c\u4fe1\u606f\u5e76\u8bf4\u660e\u8981\u6c42",
                "instruction": "\u8bf7\u544a\u77e5\u5bf9\u65b9\u9700\u8981\u914d\u5408\u63d0\u4f9b\u7684\u8eab\u4efd\u4fe1\u606f\u3002",
                "speech_hint": "\u8bf7\u51fa\u793a\u8eab\u4efd\u8bc1\u4ef6\uff0c\u5e76\u4fdd\u6301\u539f\u5730\u914d\u5408\u6838\u9a8c\u3002",
                "required_keywords": ["\u8eab\u4efd\u8bc1", "\u914d\u5408\u6838\u9a8c"],
                "node_type": "voice_qa",
            },
        ],
    })
    profiles.append({
        "match": [],
        "briefing": "\u7cfb\u7edf\u5df2\u6309\u901a\u7528\u4ea4\u4e92\u5b9e\u8bad\u89c6\u9891\u81ea\u52a8\u5efa\u6a21\uff0c\u8bf7\u68c0\u67e5\u8282\u70b9\u8282\u594f\u3001\u52a8\u4f5c\u8981\u6c42\u548c\u6807\u51c6\u8bdd\u672f\u540e\u76f4\u63a5\u4f7f\u7528\u3002",
        "tags": ["\u81ea\u52a8\u5efa\u6a21"],
        "nodes": [
            {
                "title": "\u52a8\u4f5c\u793a\u610f",
                "instruction": "\u8bf7\u6839\u636e\u89c6\u9891\u60c5\u5883\u5b8c\u6210\u89c4\u8303\u52a8\u4f5c\u793a\u610f\u3002",
                "gesture_hint": "\u52a8\u4f5c\u6e05\u6670\uff0c\u4fdd\u6301\u77ed\u6682\u7a33\u5b9a\u3002",
                "required_gesture": "raise_hand",
            },
            {
                "title": "\u51fa\u793a\u8bc1\u4ef6",
                "instruction": "\u8bf7\u51fa\u793a\u6267\u6cd5\u8bc1\u4ef6\u5e76\u8bf4\u660e\u8eab\u4efd\u3002",
                "gesture_hint": "\u53cc\u624b\u80f8\u524d\u4fdd\u6301\u8bc1\u4ef6\u5c55\u793a\u59ff\u6001\u3002",
                "speech_hint": "\u60a8\u597d\uff0c\u6211\u662f\u6267\u52e4\u6c11\u8b66\uff0c\u8bf7\u914d\u5408\u68c0\u67e5\u3002",
                "required_gesture": "show_id",
                "required_keywords": ["\u6c11\u8b66", "\u914d\u5408\u68c0\u67e5"],
                "prop_label": "\u6267\u6cd5\u8bc1\u4ef6",
            },
            {
                "title": "\u53e3\u5934\u5904\u7f6e\u8bf4\u660e",
                "instruction": "\u8bf7\u8bf4\u660e\u540e\u7eed\u5904\u7f6e\u8981\u6c42\u548c\u6ce8\u610f\u4e8b\u9879\u3002",
                "speech_hint": "\u8bf7\u4fdd\u6301\u51b7\u9759\uff0c\u6309\u8981\u6c42\u914d\u5408\u540e\u7eed\u5904\u7f6e\u3002",
                "required_keywords": ["\u4fdd\u6301\u51b7\u9759", "\u914d\u5408"],
                "node_type": "voice_qa",
            },
        ],
    })
    for profile in profiles:
        if not profile["match"] or _contains_any(normalized, profile["match"]):
            return profile
    return profiles[-1]


def _auto_node_trigger_times(duration_seconds: Optional[int], node_count: int) -> list[int]:
    duration = int(duration_seconds or 0)
    if duration <= 0:
        return [15 + idx * 20 for idx in range(node_count)]
    safe_start = max(8, min(20, duration // 8 or 8))
    safe_end = max(duration - 10, safe_start + node_count * 8)
    span = max(safe_end - safe_start, node_count * 6)
    return [
        max(1, min(max(duration - 2, 1), int(round(safe_start + (span * idx) / max(node_count - 1, 1)))))
        for idx in range(node_count)
    ]


def _build_default_auto_nodes(video: models.TrainingVideo, title: str, duration_seconds: Optional[int]) -> list[models.VideoNode]:
    if video.video_type != "interactive":
        return []

    profile = _infer_scene_profile(title)
    node_specs = profile.get("nodes") or []
    video_path = os.path.join(VIDEOS_DIR, video.file_path) if video.file_path else None
    trigger_times = video_auto_config_service.suggest_training_timestamps(video_path, duration_seconds, len(node_specs))
    if not trigger_times:
        trigger_times = _auto_node_trigger_times(duration_seconds, len(node_specs))
    nodes: list[models.VideoNode] = []
    for index, spec in enumerate(node_specs):
        required_gesture = spec.get("required_gesture")
        required_keywords = spec.get("required_keywords") or []
        node_type = spec.get("node_type") or ("voice_qa" if required_keywords else "action")
        prompt_content = {
            "instruction": spec.get("instruction") or f"\u8bf7\u5b8c\u6210\u7b2c {index + 1} \u4e2a\u81ea\u52a8\u751f\u6210\u7684\u8bad\u7ec3\u52a8\u4f5c\u3002",
            "gesture_hint": spec.get("gesture_hint") or "",
            "speech_hint": spec.get("speech_hint") or "",
            "prop_label": spec.get("prop_label") or ("\u6267\u6cd5\u8bc1\u4ef6" if required_gesture == "show_id" else ""),
            "prop_hint": spec.get("prop_hint") or "",
            "gesture_config": {
                "min_confidence": 0.55,
                "hold_frames": 5,
                "tolerance": "standard",
            },
            "identity_config": {
                "mode": "presence",
                "require_single_face": True,
                "require_live_motion": True,
                "backend_cv": False,
            },
        }
        pass_mode = "all" if required_gesture and required_keywords else ("gesture_only" if required_gesture else "speech_only")
        node_config = {
            "speech_rule": {
                "match_mode": "any",
                "min_count": 1,
                "min_length": 0,
            },
            "pass_rule": {
                "mode": pass_mode,
            },
            "assessment_points": video_auto_config_service._default_assessment_points_for_auto_node(
                index,
                node_type=node_type,
                required_gesture=required_gesture,
                required_keywords=required_keywords,
                prop_mode="manual" if spec.get("prop_label") else "auto",
            ),
            "hybrid_signals": {
                "use_template": True,
                "use_frames": True,
                "use_ocr": True,
                "use_transcript": True,
            },
        }
        nodes.append(models.VideoNode(
            video_id=video.id,
            node_index=index,
            title=spec.get("title") or f"\u81ea\u52a8\u8282\u70b9 {index + 1}",
            trigger_time=trigger_times[index],
            pause_mode="auto_pause",
            prompt_content=json.dumps(prompt_content, ensure_ascii=False),
            timeout_seconds=45 if node_type == "voice_qa" else 30,
            retry_score_deduct=5,
            skip_score_deduct=15,
            prop_mode="manual" if prompt_content.get("prop_label") else "auto",
            node_type=node_type,
            node_config=json.dumps(node_config, ensure_ascii=False),
            required_gesture=required_gesture,
            required_keywords=json.dumps(required_keywords, ensure_ascii=False),
            score_weight=10,
        ))
    return nodes


def _sync_auto_import_videos(db: Session, force: bool = False) -> dict:
    global _LAST_AUTO_IMPORT_SCAN_AT, _LAST_AUTO_IMPORT_SUMMARY

    now = time.monotonic()
    if not force and now - _LAST_AUTO_IMPORT_SCAN_AT < AUTO_IMPORT_SCAN_INTERVAL_SECONDS:
        return dict(_LAST_AUTO_IMPORT_SUMMARY)

    os.makedirs(AUTO_IMPORT_DIR, exist_ok=True)
    existing_paths = {
        _normalize_rel_path(item[0])
        for item in db.query(models.TrainingVideo.file_path).all()
        if item and item[0]
    }

    imported_count = 0
    skipped_count = 0
    detected_count = 0

    for root, _, filenames in os.walk(AUTO_IMPORT_DIR):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_VIDEO_EXTS:
                continue
            full_path = os.path.join(root, filename)
            if not os.path.isfile(full_path):
                continue
            detected_count += 1
            rel_path = _normalize_rel_path(os.path.relpath(full_path, VIDEOS_DIR))
            if rel_path in existing_paths:
                skipped_count += 1
                continue

            duration = _probe_video_duration(full_path)
            duration_seconds = int(round(duration)) if duration else None
            guessed_title = _guess_title_from_filename(filename)
            inferred_type = _infer_video_type_from_path(rel_path)
            if inferred_type == "teaching":
                inferred_type = _infer_video_type_from_name(filename)
            video_obj = models.TrainingVideo(
                title=guessed_title,
                description="\u7cfb\u7edf\u4ece\u81ea\u52a8\u5bfc\u5165\u76ee\u5f55\u68c0\u6d4b\u5230\u8be5\u89c6\u9891\uff0c\u5e76\u5df2\u81ea\u52a8\u5b8c\u6210\u5165\u5e93\u3002",
                briefing=None,
                video_type=inferred_type,
                file_path=rel_path,
                duration=duration_seconds,
                file_size=os.path.getsize(full_path),
                tags=json.dumps(_infer_tags_from_path(rel_path), ensure_ascii=False),
                status=_infer_video_status_from_path(rel_path),
            )
            db.add(video_obj)
            db.flush()
            # 自动导入时只使用本地模板生成节点，不调用外部 AI API，
            # 避免同步 LLM 调用阻塞整个 uvicorn 进程。
            # 管理员可在视频列表中手动触发 AI 分析。
            auto_nodes = _build_default_auto_nodes(video_obj, guessed_title, duration_seconds)
            if auto_nodes:
                db.add_all(auto_nodes)
            _ensure_video_thumbnail(video_obj, db)
            existing_paths.add(rel_path)
            imported_count += 1

    if imported_count:
        db.commit()

    _LAST_AUTO_IMPORT_SCAN_AT = now
    _LAST_AUTO_IMPORT_SUMMARY = {
        "watched_dir": AUTO_IMPORT_DIR,
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "detected_count": detected_count,
    }
    return dict(_LAST_AUTO_IMPORT_SUMMARY)


def _probe_video_duration(video_path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            [
                FFPROBE_BINARY,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        value = (result.stdout or "").strip()
        return float(value) if value else None
    except Exception:
        return None


def _ffmpeg_capture_frame(video_path: str, output_path: str, timestamp: float) -> bool:
    try:
        subprocess.run(
            [
                FFMPEG_BINARY,
                "-y",
                "-ss",
                str(max(0, timestamp)),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=960:-1",
                output_path,
            ],
            capture_output=True,
            check=True,
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def _generate_thumbnail_from_video(video_path: str, output_path: str, duration_hint: Optional[int] = None) -> bool:
    duration = float(duration_hint or 0) or _probe_video_duration(video_path) or 0
    candidates = [3, 5, 8]
    if duration > 1:
        candidates.extend([duration * 0.2, duration * 0.35, duration * 0.5])

    checked = []
    for item in candidates:
        if duration > 0:
            item = min(item, max(duration - 0.2, 0))
        point = round(max(item, 0), 2)
        if point not in checked:
            checked.append(point)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    for point in checked:
        if _ffmpeg_capture_frame(video_path, output_path, point):
            return True

    try:
        subprocess.run(
            [
                FFMPEG_BINARY,
                "-y",
                "-i",
                video_path,
                "-vf",
                "thumbnail=180,scale=960:-1",
                "-frames:v",
                "1",
                output_path,
            ],
            capture_output=True,
            check=True,
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def _ensure_video_thumbnail(video: models.TrainingVideo, db: Session) -> None:
    if not video.file_path:
        return

    video_path = os.path.join(VIDEOS_DIR, video.file_path)
    if not os.path.exists(video_path):
        return

    current_thumbnail_path = os.path.join(THUMBNAILS_DIR, video.thumbnail_path) if video.thumbnail_path else None
    has_valid_thumbnail = (
        video.thumbnail_path
        and current_thumbnail_path
        and os.path.exists(current_thumbnail_path)
        and os.path.getsize(current_thumbnail_path) > 0
    )
    if has_valid_thumbnail:
        return

    thumbnail_name = f"{uuid.uuid4().hex}.jpg"
    thumbnail_path = os.path.join(THUMBNAILS_DIR, thumbnail_name)
    if _generate_thumbnail_from_video(video_path, thumbnail_path, video.duration):
        video.thumbnail_path = thumbnail_name
        db.add(video)
        db.commit()
        db.refresh(video)


def _serialize_video(
    video: models.TrainingVideo,
    include_nodes: bool = False,
    *,
    include_video_url: bool = True,
    teaching_unlocked: Optional[bool] = None,
    lock_reason: Optional[str] = None,
) -> dict:
    tags = []
    try:
        tags = json.loads(video.tags or "[]")
    except Exception:
        pass

    data = {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "briefing": video.briefing,
        "video_type": video.video_type,
        "scenario_type": video.scenario_type,
        "difficulty": video.difficulty or "normal",
        "video_url": _video_url(video.file_path) if include_video_url else None,
        "thumbnail_url": _thumbnail_url(video.thumbnail_path),
        "duration": video.duration,
        "file_size": video.file_size,
        "case_id": video.case_id,
        "tags": tags,
        "status": video.status,
        "sort_order": video.sort_order,
        "uploaded_by": video.uploaded_by,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "updated_at": video.updated_at.isoformat() if video.updated_at else None,
        "node_count": len(video.nodes) if video.nodes else 0,
        "teaching_unlocked": True if teaching_unlocked is None else teaching_unlocked,
        "lock_reason": lock_reason,
    }
    data["ai_analysis_mode"] = _infer_analysis_mode_from_video(data["tags"])
    data["material_metadata"] = _extract_material_metadata(video, data["tags"])
    data["auto_analysis_summary"] = _build_auto_analysis_summary(video, data["ai_analysis_mode"])
    data["auto_analysis"] = {
        "analysis_mode": data["ai_analysis_mode"],
        "frame_count": None,
        "ocr_hints": [],
        "analysis_error": "",
        "suggested_timestamps": [
            int(getattr(node, "trigger_time", 0) or 0)
            for node in (video.nodes or [])
        ],
        "node_generation_mode": (
            "existing_nodes" if video.video_type == "interactive" and (video.nodes or []) else "teaching_no_nodes"
        ),
    }
    if include_nodes:
        data["nodes"] = [_serialize_node(n) for n in (video.nodes or [])]
    return data


def _infer_analysis_mode_from_video(tags: list[str]) -> str:
    if "AI识别" in tags:
        return "llm_vision"
    if "自动建模" in tags or "自动导入" in tags:
        return "template_fallback"
    return ""


def _safe_json_loads(value, default):
    try:
        loaded = json.loads(value or "")
        return loaded if loaded is not None else default
    except Exception:
        return default


def _extract_material_metadata(video: models.TrainingVideo, tags: list[str]) -> dict:
    metadata = {
        "is_police_simulation": "模拟警情" in tags,
        "police_scenario": "",
        "training_variant": "",
        "difficulty_level": "",
        "version_count": 1,
    }
    for node in video.nodes or []:
        config = _safe_json_loads(node.node_config, {})
        if not isinstance(config, dict):
            continue
        metadata["police_scenario"] = metadata["police_scenario"] or str(config.get("police_scenario") or "")
        metadata["training_variant"] = metadata["training_variant"] or str(config.get("training_variant") or "")
        metadata["difficulty_level"] = metadata["difficulty_level"] or str(config.get("difficulty_level") or "")
        if config.get("police_node_type"):
            metadata["is_police_simulation"] = True
    metadata["version_count"] = len({
        str(((_safe_json_loads(node.node_config, {}) or {}).get("training_variant") or "base"))
        for node in (video.nodes or [])
    }) or 1
    return metadata


def _build_auto_analysis_summary(video: models.TrainingVideo, analysis_mode: str) -> dict:
    node_count = len(video.nodes or [])
    missing_items: list[str] = []
    if video.video_type == "interactive" and not node_count:
        missing_items.append("训练节点")
    if video.video_type == "interactive" and not (video.briefing or "").strip():
        missing_items.append("训练简报")
    if video.status != "published":
        missing_items.append("发布状态")

    if video.video_type == "teaching":
        reason = "当前视频被归类为教学素材，系统不会自动生成训练节点。"
    elif node_count:
        reason = f"当前视频已生成 {node_count} 个训练节点，可直接进入节点微调或发布。"
    else:
        reason = "当前视频已归类为互动实训，但还没有生成可用节点，建议重跑 AI 分析或手动补充。"

    return {
        "analysis_mode": analysis_mode,
        "is_interactive": video.video_type == "interactive",
        "node_count": node_count,
        "missing_items": missing_items,
        "reason": reason,
    }


def _serialize_node(node: models.VideoNode) -> dict:
    prompt_content = {}
    node_config = {}
    required_keywords = []
    try:
        prompt_content = json.loads(node.prompt_content or "{}")
    except Exception:
        pass
    try:
        node_config = json.loads(node.node_config or "{}")
    except Exception:
        pass
    try:
        required_keywords = json.loads(node.required_keywords or "[]")
    except Exception:
        pass

    return {
        "id": node.id,
        "video_id": node.video_id,
        "node_index": node.node_index,
        "title": node.title,
        "trigger_time": node.trigger_time,
        "pause_mode": node.pause_mode,
        "prompt_content": prompt_content,
        "timeout_seconds": node.timeout_seconds,
        "retry_score_deduct": node.retry_score_deduct,
        "skip_score_deduct": node.skip_score_deduct,
        "prop_mode": node.prop_mode,
        "node_type": node.node_type,
        "node_interaction_type": node.node_interaction_type or "voice_qa",
        "ai_instructor_hint": node.ai_instructor_hint,
        "choice_options": json.loads(node.choice_options) if node.choice_options else None,
        "correct_answer": node.correct_answer,
        "node_config": node_config,
        "required_gesture": node.required_gesture,
        "required_keywords": required_keywords,
        "score_weight": node.score_weight,
        "created_at": node.created_at.isoformat() if node.created_at else None,
    }


def _apply_ai_analysis_to_video(
    db: Session,
    video: models.TrainingVideo,
    analysis: dict,
    *,
    overwrite_meta: bool = True,
    overwrite_nodes: bool = True,
    locked_video_type: Optional[str] = None,
) -> models.TrainingVideo:
    if overwrite_meta:
        title = str(analysis.get("title") or "").strip()
        if title:
            video.title = title
        video.description = str(analysis.get("description") or video.description or "").strip() or video.description
        video.briefing = str(analysis.get("briefing") or video.briefing or "").strip() or video.briefing
        if locked_video_type in {"teaching", "interactive"}:
            video.video_type = locked_video_type
        else:
            video.video_type = str(analysis.get("video_type") or video.video_type or "teaching")
        status = str(analysis.get("status") or video.status or "draft")
        if status in {"draft", "published", "archived"}:
            video.status = status
        tags = analysis.get("tags")
        if isinstance(tags, list):
            video.tags = json.dumps([str(item).strip() for item in tags if str(item).strip()], ensure_ascii=False)
        # 新字段：场景类型和难度
        scenario_type = str(analysis.get("scenario_type") or "").strip()
        if scenario_type:
            video.scenario_type = scenario_type
        difficulty = str(analysis.get("difficulty") or "").strip().lower()
        if difficulty in {"easy", "normal", "hard"}:
            video.difficulty = difficulty

    if overwrite_nodes:
        db.query(models.VideoNode).filter(models.VideoNode.video_id == video.id).delete()
        analysis_nodes = analysis.get("nodes") or []
        if (locked_video_type == "interactive" or video.video_type == "interactive") and not analysis_nodes:
            fallback_nodes = _build_default_auto_nodes(
                video,
                str(analysis.get("title") or video.title or ""),
                video.duration,
            )
            if fallback_nodes:
                db.add_all(fallback_nodes)
                db.flush()
                return video
        for index, item in enumerate(analysis_nodes):
            if not isinstance(item, dict):
                continue
            # 处理 choice_options：如果是列表则序列化为JSON
            choice_options = item.get("choice_options")
            choice_options_str = json.dumps(choice_options, ensure_ascii=False) if isinstance(choice_options, list) else None
            db.add(
                models.VideoNode(
                    video_id=video.id,
                    node_index=index,
                    title=item.get("title") or f"自动节点{index + 1}",
                    trigger_time=int(item.get("trigger_time") or 0),
                    pause_mode=item.get("pause_mode") or "auto_pause",
                    prompt_content=json.dumps(item.get("prompt_content") or {}, ensure_ascii=False),
                    timeout_seconds=int(item.get("timeout_seconds") or 60),
                    retry_score_deduct=int(item.get("retry_score_deduct") or 5),
                    skip_score_deduct=int(item.get("skip_score_deduct") or 20),
                    prop_mode=item.get("prop_mode") or "auto",
                    node_type=item.get("node_type") or "action",
                    node_interaction_type=item.get("node_interaction_type") or "voice_qa",
                    ai_instructor_hint=item.get("ai_instructor_hint"),
                    choice_options=choice_options_str,
                    correct_answer=str(item.get("correct_answer") or "").strip() or None,
                    node_config=json.dumps(item.get("node_config") or {}, ensure_ascii=False),
                    required_gesture=item.get("required_gesture"),
                    required_keywords=json.dumps(item.get("required_keywords") or [], ensure_ascii=False),
                    score_weight=int(item.get("score_weight") or 10),
                )
            )
    db.flush()
    return video


def _load_video_or_404(db: Session, video_id: int) -> models.TrainingVideo:
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


def _load_finished_interactive_unlock_scope(db: Session, user_id: int) -> tuple[set[int], set[int]]:
    sessions = (
        db.query(models.VideoTrainingSession, models.TrainingVideo)
        .join(models.TrainingVideo, models.TrainingVideo.id == models.VideoTrainingSession.video_id)
        .filter(
            models.VideoTrainingSession.user_id == user_id,
            models.VideoTrainingSession.status == "finished",
            models.TrainingVideo.video_type == "interactive",
        )
        .all()
    )

    completed_case_ids: set[int] = set()
    completed_video_ids: set[int] = set()
    for session, video in sessions:
        completed_video_ids.add(session.video_id)
        if video and video.case_id:
            completed_case_ids.add(video.case_id)
    return completed_case_ids, completed_video_ids


def _get_teaching_unlock_state(
    video: models.TrainingVideo,
    current_user: models.User,
    completed_case_ids: set[int],
    completed_video_ids: set[int],
) -> tuple[bool, Optional[str]]:
    if current_user.role == "admin" or video.video_type != "teaching":
        return True, None
    if video.case_id is None:
        return True, None
    if video.case_id in completed_case_ids or video.id in completed_video_ids:
        return True, None
    return False, "完成对应交互实训后解锁完整教学视频"


def _serialize_video_for_student(
    video: models.TrainingVideo,
    current_user: models.User,
    completed_case_ids: set[int],
    completed_video_ids: set[int],
    *,
    include_nodes: bool = False,
) -> dict:
    unlocked, lock_reason = _get_teaching_unlock_state(
        video,
        current_user,
        completed_case_ids,
        completed_video_ids,
    )
    return _serialize_video(
        video,
        include_nodes=include_nodes,
        include_video_url=(video.video_type != "teaching" or unlocked),
        teaching_unlocked=unlocked,
        lock_reason=lock_reason,
    )


def _get_accessible_video(
    db: Session,
    video_id: int,
    current_user: models.User,
) -> models.TrainingVideo:
    video = _get_video_for_access(db, video_id, current_user)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if current_user.role != "admin" and video.status != "published":
        raise HTTPException(status_code=403, detail="该视频暂未开放")
    return video


def _load_video_for_access(
    db: Session,
    video_id: int,
    current_user: models.User,
) -> models.TrainingVideo:
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if current_user.role != "admin" and video.status != "published":
        raise HTTPException(status_code=403, detail="该视频暂未开放")
    return video


def _get_video_for_access(
    db: Session,
    video_id: int,
    current_user: models.User,
) -> models.TrainingVideo:
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if current_user.role != "admin" and video.status != "published":
        raise HTTPException(status_code=403, detail="该视频暂未开放")
    return video


# ═════════════════════════════════════════════
# 固定路径路由（必须在动态路径之前）
# ═════════════════════════════════════════════

# ─────────────────────────────────────────────
# 管理端：视频上传
# ─────────────────────────────────────────────

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    duration: Optional[int] = Form(None),
    video_type: Optional[str] = Form(None),
    auto_configure: Optional[bool] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """
    极简视频上传（管理端专用）
    只需传入视频文件，标题可选（不填则从文件名自动推断）。
    上传后 AI 自动分析视频内容，生成：类型、简报、标签、难度、训练节点。
    """
    content_type = file.content_type or ""
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if content_type not in ALLOWED_VIDEO_TYPES and file_ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的视频格式：{content_type or file_ext or '未知'}，请上传 mp4/webm/mov",
        )

    # 标题：优先用户提供，否则从文件名推断
    resolved_title = (title or "").strip() or _guess_title_from_filename(file.filename or "video")
    locked_video_type = str(video_type or "").strip()
    if locked_video_type and locked_video_type not in {"teaching", "interactive"}:
        raise HTTPException(status_code=400, detail="video_type must be teaching or interactive")

    video_data = await file.read()
    if len(video_data) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="视频文件不能超过 2GB")

    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    with open(os.path.join(VIDEOS_DIR, filename), "wb") as f:
        f.write(video_data)

    # 封面图：用户可选上传，否则后续自动截取
    thumbnail_filename = None
    if thumbnail and thumbnail.filename:
        thumb_ct = thumbnail.content_type or ""
        thumb_ext_raw = os.path.splitext(thumbnail.filename)[1].lower()
        allowed_thumb_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        is_valid_thumb = thumb_ct in ALLOWED_IMAGE_TYPES or thumb_ext_raw in allowed_thumb_exts
        if is_valid_thumb:
            thumb_data = await thumbnail.read()
            if len(thumb_data) <= MAX_THUMBNAIL_SIZE:
                thumb_ext = thumb_ext_raw or ".jpg"
                thumbnail_filename = f"{uuid.uuid4().hex}{thumb_ext}"
                os.makedirs(THUMBNAILS_DIR, exist_ok=True)
                with open(os.path.join(THUMBNAILS_DIR, thumbnail_filename), "wb") as f:
                    f.write(thumb_data)

    # 探测视频时长（如前端未传）
    resolved_duration = duration
    if not resolved_duration:
        probed = _probe_video_duration(os.path.join(VIDEOS_DIR, filename))
        resolved_duration = int(round(probed)) if probed else None

    # 创建视频记录（状态: analyzing，AI分析在后台执行）
    video_obj = models.TrainingVideo(
        title=resolved_title,
        description=None,
        video_type=locked_video_type or "interactive",
        file_path=filename,
        thumbnail_path=thumbnail_filename,
        file_size=len(video_data),
        duration=resolved_duration,
        case_id=None,
        tags=json.dumps([], ensure_ascii=False),
        status="analyzing" if auto_configure is not False else "draft",
        uploaded_by=current_user.id,
    )
    db.add(video_obj)
    db.commit()
    db.refresh(video_obj)

    # 自动截取封面（同步，很快）
    if not thumbnail_filename:
        _ensure_video_thumbnail(video_obj, db)

    video_id = video_obj.id
    video_path = os.path.join(VIDEOS_DIR, filename)
    locked_type = locked_video_type or None

    if auto_configure is True:
        analysis = video_auto_config_service.analyze_video_file(
            video_path,
            title_hint=resolved_title,
            duration_seconds=resolved_duration,
            preferred_type=locked_type,
            scenario_hint=None,
            training_variant=None,
            difficulty_level=None,
        )
        analysis_error = analysis.get("analysis_error")
        if analysis.get("analysis_mode") == "error" or analysis_error:
            video_obj.status = "draft"
            video_obj.description = f"AI分析失败：{analysis_error or '未知错误'}。可点击重新分析。"
            db.commit()
        else:
            _apply_ai_analysis_to_video(
                db,
                video_obj,
                analysis,
                overwrite_meta=True,
                overwrite_nodes=True,
                locked_video_type=locked_type,
            )
            video_obj.status = "published"
            db.commit()
        db.refresh(video_obj)
        return _serialize_video(video_obj, include_nodes=True)

    if auto_configure is False:
        return _serialize_video(video_obj, include_nodes=False)

    # 后台线程执行 AI 分析
    def _background_analyze():
        from database import SessionLocal
        bg_db = SessionLocal()
        try:
            vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
            if not vid:
                return

            analysis = video_auto_config_service.analyze_video_file(
                video_path,
                title_hint=resolved_title,
                duration_seconds=resolved_duration,
                preferred_type=locked_type,
                scenario_hint=None,
                training_variant=None,
                difficulty_level=None,
            )

            analysis_error = analysis.get("analysis_error")
            if analysis.get("analysis_mode") == "error" or analysis_error:
                vid.status = "draft"
                vid.description = f"AI分析失败：{analysis_error or '未知错误'}。可点击重新分析。"
                bg_db.commit()
                return

            _apply_ai_analysis_to_video(
                bg_db,
                vid,
                analysis,
                overwrite_meta=True,
                overwrite_nodes=True,
                locked_video_type=locked_type,
            )
            vid.status = "published"
            bg_db.commit()
        except Exception as exc:
            try:
                vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
                if vid:
                    vid.status = "draft"
                    vid.description = f"AI分析异常：{exc}"
                    bg_db.commit()
            except Exception:
                pass
        finally:
            bg_db.close()

    threading.Thread(target=_background_analyze, daemon=True).start()

    result = _serialize_video(video_obj, include_nodes=False)
    result["analysis_status"] = "analyzing"
    return result


# ─────────────────────────────────────────────
# 管理端：查询视频分析状态 / 重新分析
# ─────────────────────────────────────────────

@router.get("/status/{video_id}")
def get_video_status(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """查询单个视频的分析状态（前端轮询用）"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    analysis_status = "analyzing" if video.status == "analyzing" else (
        "success" if video.status == "published" else "failed"
    )
    return {
        "id": video.id,
        "status": video.status,
        "analysis_status": analysis_status,
        "title": video.title,
        "node_count": len(video.nodes) if video.nodes else 0,
        "scenario_type": video.scenario_type,
        "difficulty": video.difficulty,
    }


@router.post("/retry-analysis/{video_id}")
def retry_analysis(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """重新触发 AI 分析（用于之前分析失败的视频）"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status == "analyzing":
        raise HTTPException(status_code=400, detail="该视频正在分析中，请稍候")

    video.status = "analyzing"
    video.description = None
    db.commit()

    video_path = os.path.join(VIDEOS_DIR, video.file_path)
    title_hint = video.title or ""
    duration_seconds = video.duration
    vid_id = video.id

    def _background_retry():
        from database import SessionLocal
        bg_db = SessionLocal()
        try:
            vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == vid_id).first()
            if not vid:
                return
            analysis = video_auto_config_service.analyze_video_file(
                video_path,
                title_hint=title_hint,
                duration_seconds=duration_seconds,
                preferred_type=None,
                scenario_hint=None,
                training_variant=None,
                difficulty_level=None,
            )
            analysis_error = analysis.get("analysis_error")
            if analysis.get("analysis_mode") == "error" or analysis_error:
                vid.status = "draft"
                vid.description = f"AI分析失败：{analysis_error or '未知错误'}。可点击重新分析。"
                bg_db.commit()
                return
            _apply_ai_analysis_to_video(
                bg_db,
                vid,
                analysis,
                overwrite_meta=True,
                overwrite_nodes=True,
                locked_video_type=None,
            )
            vid.status = "published"
            bg_db.commit()
        except Exception as exc:
            try:
                vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == vid_id).first()
                if vid:
                    vid.status = "draft"
                    vid.description = f"AI分析异常：{exc}"
                    bg_db.commit()
            except Exception:
                pass
        finally:
            bg_db.close()

    threading.Thread(target=_background_retry, daemon=True).start()
    return {"id": video_id, "status": "analyzing", "message": "已重新触发 AI 分析"}


@router.patch("/{video_id}/toggle-publish")
def toggle_publish(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """切换视频发布/下架状态"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status == "analyzing":
        raise HTTPException(status_code=400, detail="视频正在分析中，无法切换状态")
    video.status = "published" if video.status != "published" else "draft"
    db.commit()
    return {"id": video_id, "status": video.status}


# ─────────────────────────────────────────────
# 管理端：视频列表
# ─────────────────────────────────────────────

@router.get("/admin/list")
def admin_list_videos(
    video_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """管理端视频列表（支持筛选/分页）"""
    auto_import_summary = _sync_auto_import_videos(db)
    query = db.query(models.TrainingVideo)
    if video_type:
        query = query.filter(models.TrainingVideo.video_type == video_type)
    if status:
        query = query.filter(models.TrainingVideo.status == status)
    if keyword:
        query = query.filter(models.TrainingVideo.title.contains(keyword))

    total = query.count()
    videos = (
        query.order_by(
            models.TrainingVideo.sort_order.asc(),
            models.TrainingVideo.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    for video in videos:
        _ensure_video_thumbnail(video, db)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_video(v) for v in videos],
        "auto_import": auto_import_summary,
    }


# ─────────────────────────────────────────────
# 学员端：视频展厅
# ─────────────────────────────────────────────

@router.get("/student/hall")
def student_video_hall(
    video_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """学员端视频展厅：只返回已发布的视频"""
    _sync_auto_import_videos(db)
    query = db.query(models.TrainingVideo).filter(
        models.TrainingVideo.status == "published"
    )
    if video_type:
        query = query.filter(models.TrainingVideo.video_type == video_type)
    if keyword:
        query = query.filter(models.TrainingVideo.title.contains(keyword))

    videos = query.order_by(
        models.TrainingVideo.sort_order.asc(),
        models.TrainingVideo.created_at.desc(),
    ).all()
    completed_case_ids, completed_video_ids = _load_finished_interactive_unlock_scope(db, current_user.id)
    for video in videos:
        _ensure_video_thumbnail(video, db)
    return [
        _serialize_video_for_student(
            video,
            current_user,
            completed_case_ids,
            completed_video_ids,
        )
        for video in videos
    ]


# ═════════════════════════════════════════════
# 动态路径路由（/{video_id} 必须在固定路径之后）
# ═════════════════════════════════════════════

@router.post("/{video_id}/auto-configure")
def auto_configure_video(
    video_id: int,
    payload: Optional[dict] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    video = _load_video_or_404(db, video_id)
    video_path = os.path.join(VIDEOS_DIR, video.file_path or "")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    if video.status == "analyzing":
        raise HTTPException(status_code=400, detail="该视频正在分析中，请稍候")

    payload = payload or {}
    overwrite_meta = bool(payload.get("overwrite_meta", True))
    overwrite_nodes = bool(payload.get("overwrite_nodes", True))
    preferred_type = payload.get("preferred_type")
    if preferred_type not in {None, "", "auto", "teaching", "interactive"}:
        raise HTTPException(status_code=400, detail="preferred_type 必须为 auto / teaching / interactive")
    scenario_hint = str(payload.get("scenario_hint") or "").strip()
    training_variant = str(payload.get("training_variant") or "").strip()
    difficulty_level = str(payload.get("difficulty_level") or "").strip()
    allowed_scenarios = {"", "family_dispute", "alcohol_trouble", "school_conflict", "public_help", "traffic_scene", "unstable_person"}
    if scenario_hint not in allowed_scenarios:
        raise HTTPException(status_code=400, detail="scenario_hint 不合法")

    # 标记为分析中并立即返回，AI 分析在后台执行
    prev_status = video.status
    video.status = "analyzing"
    db.commit()

    vid_id = video.id
    title_hint = video.title
    duration_seconds = video.duration
    locked_type = None if preferred_type in {None, "", "auto"} else str(preferred_type)

    def _background_auto_configure():
        from database import SessionLocal
        bg_db = SessionLocal()
        try:
            vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == vid_id).first()
            if not vid:
                return
            analysis = video_auto_config_service.analyze_video_file(
                video_path,
                title_hint=title_hint,
                duration_seconds=duration_seconds,
                preferred_type=locked_type,
                scenario_hint=scenario_hint,
                training_variant=training_variant,
                difficulty_level=difficulty_level,
            )
            analysis_error = analysis.get("analysis_error")
            if analysis.get("analysis_mode") == "error" or analysis_error:
                vid.status = prev_status if prev_status != "analyzing" else "draft"
                vid.description = f"AI分析失败：{analysis_error or '未知错误'}。可点击重新分析。"
                bg_db.commit()
                return
            _apply_ai_analysis_to_video(
                bg_db,
                vid,
                analysis,
                overwrite_meta=overwrite_meta,
                overwrite_nodes=overwrite_nodes,
                locked_video_type=locked_type,
            )
            vid.status = "published"
            bg_db.commit()
        except Exception as exc:
            try:
                vid = bg_db.query(models.TrainingVideo).filter(models.TrainingVideo.id == vid_id).first()
                if vid:
                    vid.status = prev_status if prev_status != "analyzing" else "draft"
                    vid.description = f"AI分析异常：{exc}"
                    bg_db.commit()
            except Exception:
                pass
        finally:
            bg_db.close()

    _background_auto_configure()
    db.expire_all()
    refreshed = _load_video_or_404(db, video_id)
    return _serialize_video(refreshed, include_nodes=True)
    return {"id": video_id, "status": "analyzing", "message": "AI 分析已在后台启动，请稍后刷新查看结果"}


@router.get("/{video_id}")
def get_video_detail(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取单个视频详情（含节点）"""
    _sync_auto_import_videos(db)
    video = _load_video_or_404(db, video_id)
    if current_user.role != "admin" and video.status != "published":
        raise HTTPException(status_code=403, detail="该视频暂未开放")
    completed_case_ids: set[int] = set()
    completed_video_ids: set[int] = set()
    if current_user.role != "admin" and video.video_type == "teaching":
        completed_case_ids, completed_video_ids = _load_finished_interactive_unlock_scope(db, current_user.id)
        unlocked, _ = _get_teaching_unlock_state(video, current_user, completed_case_ids, completed_video_ids)
        if not unlocked:
            raise HTTPException(status_code=403, detail="完成对应交互实训后解锁完整教学视频")
    _ensure_video_thumbnail(video, db)
    if current_user.role == "admin":
        return _serialize_video(video, include_nodes=True)
    return _serialize_video_for_student(
        video,
        current_user,
        completed_case_ids,
        completed_video_ids,
        include_nodes=True,
    )


@router.patch("/{video_id}")
def update_video_meta(
    video_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """更新视频元信息（标题、描述、状态、类型等）"""
    video = _get_video_for_access(db, video_id, current_user)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    allowed_fields = {"title", "description", "briefing", "video_type", "status", "case_id", "tags", "sort_order", "duration"}
    for key, value in payload.items():
        if key not in allowed_fields:
            continue
        if key == "tags":
            value = json.dumps(value if isinstance(value, list) else [], ensure_ascii=False)
        if key == "video_type" and value not in ("teaching", "interactive"):
            raise HTTPException(status_code=400, detail="video_type 必须为 teaching 或 interactive")
        if key == "status" and value not in ("draft", "published", "archived"):
            raise HTTPException(status_code=400, detail="status 必须为 draft / published / archived")
        setattr(video, key, value)

    db.commit()
    db.refresh(video)
    _ensure_video_thumbnail(video, db)
    return _serialize_video(video, include_nodes=True)


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """删除视频（同时删除节点和文件）"""
    video = _get_video_for_access(db, video_id, current_user)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if video.file_path:
        fp = os.path.join(VIDEOS_DIR, video.file_path)
        if os.path.exists(fp):
            os.remove(fp)
    if video.thumbnail_path:
        tp = os.path.join(THUMBNAILS_DIR, video.thumbnail_path)
        if os.path.exists(tp):
            os.remove(tp)

    db.delete(video)
    db.commit()
    return {"message": "视频已删除", "video_id": video_id}


# ─────────────────────────────────────────────
# 节点配置（/{video_id}/nodes/...）
# 注意：/nodes/reorder 也是固定路径，需在 /nodes/{node_id} 之前
# ─────────────────────────────────────────────

@router.get("/{video_id}/nodes")
def get_video_nodes(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取视频的所有节点"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    _load_video_for_access(db, video_id, current_user)
    nodes = (
        db.query(models.VideoNode)
        .filter(models.VideoNode.video_id == video_id)
        .order_by(models.VideoNode.node_index.asc())
        .all()
    )
    return [_serialize_node(n) for n in nodes]


@router.post("/{video_id}/nodes")
def create_video_node(
    video_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """新增训练节点"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    max_index = (
        db.query(models.VideoNode)
        .filter(models.VideoNode.video_id == video_id)
        .count()
    )
    node = models.VideoNode(
        video_id=video_id,
        node_index=payload.get("node_index", max_index),
        title=payload.get("title", f"节点{max_index + 1}"),
        trigger_time=int(payload.get("trigger_time", 0)),
        pause_mode=payload.get("pause_mode", "auto_pause"),
        prompt_content=json.dumps(payload.get("prompt_content", {}), ensure_ascii=False),
        timeout_seconds=int(payload.get("timeout_seconds", 60)),
        retry_score_deduct=int(payload.get("retry_score_deduct", 5)),
        skip_score_deduct=int(payload.get("skip_score_deduct", 20)),
        prop_mode=payload.get("prop_mode", "auto"),
        node_type=payload.get("node_type", "action"),
        node_config=json.dumps(payload.get("node_config", {}), ensure_ascii=False),
        required_gesture=payload.get("required_gesture"),
        required_keywords=json.dumps(payload.get("required_keywords", []), ensure_ascii=False),
        score_weight=int(payload.get("score_weight", 10)),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return _serialize_node(node)


@router.put("/{video_id}/nodes/reorder")
def reorder_video_nodes(
    video_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """批量重排节点顺序，payload: {"order": [node_id, ...]}"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    for idx, node_id in enumerate(payload.get("order", [])):
        db.query(models.VideoNode).filter(
            models.VideoNode.id == node_id,
            models.VideoNode.video_id == video_id,
        ).update({"node_index": idx})
    db.commit()
    return {"message": "节点顺序已更新"}


@router.patch("/{video_id}/nodes/{node_id}")
def update_video_node(
    video_id: int,
    node_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """更新单个节点配置"""
    node = (
        db.query(models.VideoNode)
        .filter(models.VideoNode.id == node_id, models.VideoNode.video_id == video_id)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    scalar_fields = {
        "node_index", "title", "trigger_time", "pause_mode",
        "timeout_seconds", "retry_score_deduct", "skip_score_deduct",
        "prop_mode", "node_type", "required_gesture", "score_weight",
    }
    json_fields = {"prompt_content", "node_config", "required_keywords"}

    for key, value in payload.items():
        if key in scalar_fields:
            setattr(node, key, value)
        elif key in json_fields:
            setattr(node, key, json.dumps(value, ensure_ascii=False))

    db.commit()
    db.refresh(node)
    return _serialize_node(node)


@router.delete("/{video_id}/nodes/{node_id}")
def delete_video_node(
    video_id: int,
    node_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """删除节点"""
    node = (
        db.query(models.VideoNode)
        .filter(models.VideoNode.id == node_id, models.VideoNode.video_id == video_id)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    db.delete(node)
    db.commit()
    return {"message": "节点已删除", "node_id": node_id}
