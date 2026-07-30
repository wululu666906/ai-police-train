import io
import mimetypes
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy.orm import Session

import models


@dataclass
class StoredObject:
    provider: str
    bucket: str
    object_key: str
    content_type: str | None = None
    file_size: int | None = None


PROJECT_BACKEND_DIR = Path(__file__).resolve().parents[1]
LOCAL_OBJECT_ROOT = Path(os.getenv("LOCAL_OBJECT_STORAGE_DIR", PROJECT_BACKEND_DIR / "data" / "object_storage")).resolve()
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").strip().lower() or "local"
MEDIA_BUCKET = os.getenv("MINIO_BUCKET_MEDIA", "ai-police-media")
PRIVATE_BUCKET = os.getenv("MINIO_BUCKET_PRIVATE", "ai-police-private")
SIGNED_URL_EXPIRE_SECONDS = int(os.getenv("OBJECT_SIGNED_URL_EXPIRE_SECONDS", "3600"))


def _safe_filename(filename: str | None, fallback_ext: str = "") -> str:
    raw = Path(filename or "").name.strip()
    if not raw:
        raw = f"file{fallback_ext}"
    return "".join(ch if ch.isalnum() or ch in ".-_ " else "_" for ch in raw).strip() or f"file{fallback_ext}"


def build_object_key(prefix: str, filename: str | None) -> str:
    safe_name = _safe_filename(filename)
    return f"{prefix.strip('/')}/{uuid4().hex}-{safe_name}"


def guess_content_type(filename: str | None, provided: str | None = None) -> str:
    if provided:
        return provided
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "application/octet-stream"


class ObjectStorage:
    def __init__(self) -> None:
        self.provider = STORAGE_PROVIDER
        self._client = None
        self._public_client = None

    @property
    def is_minio(self) -> bool:
        return self.provider == "minio"

    def _minio_client(self):
        if self._client is not None:
            return self._client
        try:
            from minio import Minio
        except Exception as exc:
            raise RuntimeError("minio package is not installed") from exc
        endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000").replace("http://", "").replace("https://", "")
        self._client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "ai-police"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "ai-police-secret"),
            secure=os.getenv("MINIO_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"},
        )
        return self._client

    def _public_minio_client(self):
        if self._public_client is not None:
            return self._public_client
        from minio import Minio

        configured = os.getenv("MINIO_PUBLIC_ENDPOINT", "").strip().rstrip("/")
        if not configured:
            return self._minio_client()
        parsed = urlsplit(configured if "://" in configured else f"http://{configured}")
        endpoint = parsed.netloc or parsed.path
        if parsed.path not in {"", "/"}:
            raise RuntimeError("MINIO_PUBLIC_ENDPOINT must not contain a path")
        self._public_client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "ai-police"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "ai-police-secret"),
            secure=parsed.scheme == "https",
            region=os.getenv("MINIO_REGION", "us-east-1"),
        )
        return self._public_client

    def _ensure_bucket(self, bucket: str) -> None:
        if not self.is_minio:
            return
        client = self._minio_client()
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    def put_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        if self.is_minio:
            self._ensure_bucket(bucket)
            client = self._minio_client()
            client.put_object(
                bucket,
                object_key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type or "application/octet-stream",
            )
        else:
            target = LOCAL_OBJECT_ROOT / bucket / object_key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return StoredObject(self.provider, bucket, object_key, content_type, len(data))

    def put_file(
        self,
        *,
        bucket: str,
        object_key: str,
        source_path: str | os.PathLike[str],
        content_type: str | None = None,
    ) -> StoredObject:
        path = Path(source_path)
        size = path.stat().st_size
        if self.is_minio:
            self._ensure_bucket(bucket)
            self._minio_client().fput_object(bucket, object_key, str(path), content_type=content_type)
        else:
            target = LOCAL_OBJECT_ROOT / bucket / object_key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        return StoredObject(self.provider, bucket, object_key, content_type, size)

    def delete_object(self, bucket: str | None, object_key: str | None, provider: str | None = None) -> None:
        if not object_key:
            return
        active_provider = provider or self.provider
        if active_provider == "minio":
            try:
                self._minio_client().remove_object(bucket or MEDIA_BUCKET, object_key)
            except Exception:
                pass
        else:
            path = LOCAL_OBJECT_ROOT / (bucket or MEDIA_BUCKET) / object_key
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def url_for(self, asset: models.MediaAsset | StoredObject | None) -> str | None:
        if not asset:
            return None
        provider = getattr(asset, "storage_provider", getattr(asset, "provider", self.provider))
        bucket = getattr(asset, "bucket", None) or MEDIA_BUCKET
        object_key = getattr(asset, "object_key", "")
        if not object_key:
            return None
        if provider == "minio":
            from datetime import timedelta

            return self._public_minio_client().presigned_get_object(
                bucket,
                object_key,
                expires=timedelta(seconds=SIGNED_URL_EXPIRE_SECONDS),
            )
        base = os.getenv("LOCAL_OBJECT_PUBLIC_BASE", "/object-storage").rstrip("/")
        return f"{base}/{bucket}/{object_key}"

    @contextmanager
    def local_file(self, *, bucket: str | None, object_key: str, provider: str | None = None, suffix: str = "") -> Iterator[str]:
        active_provider = provider or self.provider
        if active_provider == "local":
            local = LOCAL_OBJECT_ROOT / (bucket or MEDIA_BUCKET) / object_key
            yield str(local)
            return

        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            self._minio_client().fget_object(bucket or MEDIA_BUCKET, object_key, tmp_path)
            yield tmp_path
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass


object_storage = ObjectStorage()


def upsert_media_asset(
    db: Session,
    *,
    owner_type: str,
    owner_key: str | int,
    asset_kind: str,
    stored: StoredObject,
    original_filename: str | None = None,
    content_type: str | None = None,
    replace_existing: bool = True,
) -> models.MediaAsset:
    owner_key_text = str(owner_key)
    asset = (
        db.query(models.MediaAsset)
        .filter(
            models.MediaAsset.owner_type == owner_type,
            models.MediaAsset.owner_key == owner_key_text,
            models.MediaAsset.asset_kind == asset_kind,
        )
        .first()
    )
    if asset and replace_existing:
        object_storage.delete_object(asset.bucket, asset.object_key, asset.storage_provider)
    if not asset:
        asset = models.MediaAsset(owner_type=owner_type, owner_key=owner_key_text, asset_kind=asset_kind)
    asset.storage_provider = stored.provider
    asset.bucket = stored.bucket
    asset.object_key = stored.object_key
    asset.original_filename = original_filename
    asset.content_type = content_type or stored.content_type
    asset.file_size = stored.file_size
    db.add(asset)
    db.flush()
    return asset


def get_media_asset(db: Session, owner_type: str, owner_key: str | int, asset_kind: str) -> models.MediaAsset | None:
    return (
        db.query(models.MediaAsset)
        .filter(
            models.MediaAsset.owner_type == owner_type,
            models.MediaAsset.owner_key == str(owner_key),
            models.MediaAsset.asset_kind == asset_kind,
        )
        .first()
    )


def delete_media_assets(db: Session, *, owner_type: str, owner_key: str | int | None = None, asset_kind: str | None = None) -> int:
    query = db.query(models.MediaAsset).filter(models.MediaAsset.owner_type == owner_type)
    if owner_key is not None:
        query = query.filter(models.MediaAsset.owner_key == str(owner_key))
    if asset_kind is not None:
        query = query.filter(models.MediaAsset.asset_kind == asset_kind)
    assets = query.all()
    for asset in assets:
        object_storage.delete_object(asset.bucket, asset.object_key, asset.storage_provider)
        db.delete(asset)
    db.flush()
    return len(assets)
