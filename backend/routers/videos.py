"""
视频实训模块 - 后端路由
第一阶段：视频上传、管理、节点配置、学员端视频展厅

路由顺序说明：固定路径必须定义在动态路径（/{video_id}）之前，
否则 FastAPI 会把固定路径段（如 "upload"、"admin"、"student"）当整数解析而报错。
"""
import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user

router = APIRouter(prefix="/videos", tags=["Videos"])

# 静态文件存储根目录
VIDEOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "videos")
THUMBNAILS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "thumbnails")

ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024   # 2 GB
MAX_THUMBNAIL_SIZE = 10 * 1024 * 1024      # 10 MB


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


def _serialize_video(video: models.TrainingVideo, include_nodes: bool = False) -> dict:
    tags = []
    try:
        tags = json.loads(video.tags or "[]")
    except Exception:
        pass

    data = {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "video_type": video.video_type,
        "video_url": _video_url(video.file_path),
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
    }
    if include_nodes:
        data["nodes"] = [_serialize_node(n) for n in (video.nodes or [])]
    return data


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
        "node_config": node_config,
        "required_gesture": node.required_gesture,
        "required_keywords": required_keywords,
        "score_weight": node.score_weight,
        "created_at": node.created_at.isoformat() if node.created_at else None,
    }


# ═════════════════════════════════════════════
# 固定路径路由（必须在动态路径之前）
# ═════════════════════════════════════════════

# ─────────────────────────────────────────────
# 管理端：视频上传
# ─────────────────────────────────────────────

@router.post("/upload")
async def upload_video(
    title: str = Form(...),
    video_type: str = Form("teaching"),
    description: Optional[str] = Form(None),
    case_id: Optional[int] = Form(None),
    tags: Optional[str] = Form("[]"),
    duration: Optional[int] = Form(None),        # 前端提取的视频时长（秒）
    file: UploadFile = File(...),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """上传视频文件（管理端专用）"""
    content_type = file.content_type or ""
    # Windows 上部分浏览器对本地文件上报 application/octet-stream 或空，
    # 用扩展名做二次兜底判断
    allowed_exts = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if content_type not in ALLOWED_VIDEO_TYPES and file_ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的视频格式：{content_type or file_ext or '未知'}，请上传 mp4/webm/mov",
        )
    if video_type not in ("teaching", "interactive"):
        raise HTTPException(status_code=400, detail="video_type 必须为 teaching 或 interactive")

    video_data = await file.read()
    if len(video_data) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="视频文件不能超过 2GB")

    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    with open(os.path.join(VIDEOS_DIR, filename), "wb") as f:
        f.write(video_data)

    thumbnail_filename = None
    if thumbnail and thumbnail.filename:
        thumb_ct = thumbnail.content_type or ""
        thumb_ext_raw = os.path.splitext(thumbnail.filename)[1].lower()
        allowed_thumb_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        # 兼容 content-type 为 octet-stream 的情况，用扩展名兜底
        is_valid_thumb = thumb_ct in ALLOWED_IMAGE_TYPES or thumb_ext_raw in allowed_thumb_exts
        if is_valid_thumb:
            thumb_data = await thumbnail.read()
            if len(thumb_data) <= MAX_THUMBNAIL_SIZE:
                thumb_ext = thumb_ext_raw or ".jpg"
                thumbnail_filename = f"{uuid.uuid4().hex}{thumb_ext}"
                os.makedirs(THUMBNAILS_DIR, exist_ok=True)
                with open(os.path.join(THUMBNAILS_DIR, thumbnail_filename), "wb") as f:
                    f.write(thumb_data)

    try:
        tags_list = json.loads(tags or "[]")
        if not isinstance(tags_list, list):
            tags_list = []
    except Exception:
        tags_list = []

    video_obj = models.TrainingVideo(
        title=title.strip(),
        description=description,
        video_type=video_type,
        file_path=filename,
        thumbnail_path=thumbnail_filename,
        file_size=len(video_data),
        duration=duration,
        case_id=case_id,
        tags=json.dumps(tags_list, ensure_ascii=False),
        status="draft",
        uploaded_by=current_user.id,
    )
    db.add(video_obj)
    db.commit()
    db.refresh(video_obj)
    return _serialize_video(video_obj)


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
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_video(v) for v in videos],
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
    return [_serialize_video(v) for v in videos]


# ═════════════════════════════════════════════
# 动态路径路由（/{video_id} 必须在固定路径之后）
# ═════════════════════════════════════════════

@router.get("/{video_id}")
def get_video_detail(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取单个视频详情（含节点）"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if current_user.role != "admin" and video.status != "published":
        raise HTTPException(status_code=403, detail="该视频暂未开放")
    return _serialize_video(video, include_nodes=True)


@router.patch("/{video_id}")
def update_video_meta(
    video_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """更新视频元信息（标题、描述、状态、类型等）"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    allowed_fields = {"title", "description", "video_type", "status", "case_id", "tags", "sort_order", "duration"}
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
    return _serialize_video(video, include_nodes=True)


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(_require_admin),
):
    """删除视频（同时删除节点和文件）"""
    video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
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
