from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

import models
from services.object_storage_service import (
    MEDIA_BUCKET,
    build_object_key,
    object_storage,
    upsert_media_asset,
)

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AVATAR_BYTES = 3 * 1024 * 1024
MAX_IMAGE_SIDE = 1200
PROFILE_AVATAR_DIR = Path(__file__).resolve().parents[1] / "static" / "profile_avatars"


@dataclass(frozen=True)
class PreparedProfileImage:
    content: bytes
    content_type: str
    suffix: str
    width: int
    height: int


def prepare_profile_image(raw: bytes, *, max_bytes: int = MAX_IMAGE_BYTES) -> PreparedProfileImage:
    if not raw:
        raise HTTPException(status_code=400, detail="请选择图片文件")
    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail=f"图片不能超过 {max_bytes // (1024 * 1024)}MB")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if str(source.format or "").upper() not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(status_code=400, detail="图片仅支持 JPG、JPEG、PNG 或 WebP 格式")
            if source.width * source.height > 40_000_000:
                raise HTTPException(status_code=400, detail="图片像素尺寸过大，请压缩后重试")
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.width < 80 or image.height < 80:
                raise HTTPException(status_code=400, detail="图片尺寸不能小于 80×80 像素")
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return PreparedProfileImage(
                content=output.getvalue(),
                content_type="image/jpeg",
                suffix=".jpg",
                width=image.width,
                height=image.height,
            )
    except HTTPException:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="图片文件损坏或实际格式无效")


def store_user_avatar(
    db: Session,
    user: models.User,
    prepared: PreparedProfileImage,
    *,
    original_filename: str,
) -> str:
    PROFILE_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"user-{user.id}-{uuid4().hex}{prepared.suffix}"
    target = PROFILE_AVATAR_DIR / filename
    target.write_bytes(prepared.content)
    try:
        stored = object_storage.put_file(
            bucket=MEDIA_BUCKET,
            object_key=build_object_key(f"avatars/{user.id}", filename),
            source_path=target,
            content_type=prepared.content_type,
        )
    finally:
        target.unlink(missing_ok=True)
    upsert_media_asset(
        db,
        owner_type="user",
        owner_key=user.id,
        asset_kind="avatar",
        stored=stored,
        original_filename=original_filename or filename,
        content_type=prepared.content_type,
    )
    user.avatar_url = object_storage.url_for(stored)
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.flush()
    return user.avatar_url
