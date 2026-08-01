import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import models
from database import SessionLocal
from services.object_storage_service import (
    MEDIA_BUCKET,
    build_object_key,
    get_media_asset,
    guess_content_type,
    object_storage,
    upsert_media_asset,
)


PLAYBACK_ASSET_KIND = "hls_manifest"
HLS_SEGMENT_SECONDS = max(4, int(os.getenv("VIDEO_HLS_SEGMENT_SECONDS", "10")))
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

_job_queue: queue.Queue[int] = queue.Queue()
_queued_ids: set[int] = set()
_queue_lock = threading.Lock()
_worker_started = False
LEGACY_VIDEO_ROOT = Path(__file__).resolve().parents[1] / "static" / "videos"


def _metadata(asset: models.MediaAsset | None) -> dict:
    if not asset or not asset.extra_json:
        return {}
    try:
        value = json.loads(asset.extra_json)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _source_fingerprint(source: models.MediaAsset) -> str:
    return f"{source.storage_provider}:{source.bucket}:{source.object_key}:{source.file_size or 0}"


def get_playback_status(db, video: models.TrainingVideo) -> dict:
    source = get_media_asset(db, "video", video.id, "source")
    playback = get_media_asset(db, "video", video.id, PLAYBACK_ASSET_KIND)
    metadata = _metadata(playback)
    status = metadata.get("status", "missing")
    if source and metadata.get("source_fingerprint") != _source_fingerprint(source):
        status = "missing"
    return {
        "video_id": video.id,
        "status": status,
        "version": metadata.get("version"),
        "segment_count": int(metadata.get("segment_count") or 0),
        "segment_seconds": int(metadata.get("segment_seconds") or HLS_SEGMENT_SECONDS),
        "error": metadata.get("error") if status == "failed" else None,
    }


def _save_state(db, video_id: int, *, status: str, source: models.MediaAsset, **values) -> models.MediaAsset:
    asset = get_media_asset(db, "video", video_id, PLAYBACK_ASSET_KIND)
    if not asset:
        asset = models.MediaAsset(
            owner_type="video",
            owner_key=str(video_id),
            asset_kind=PLAYBACK_ASSET_KIND,
            object_key="",
        )
    asset.storage_provider = source.storage_provider
    asset.bucket = source.bucket or MEDIA_BUCKET
    asset.content_type = "application/vnd.apple.mpegurl"
    metadata = _metadata(asset)
    metadata.update(values)
    metadata.update({"status": status, "source_fingerprint": _source_fingerprint(source)})
    asset.extra_json = json.dumps(metadata, ensure_ascii=False)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _process_video(video_id: int) -> None:
    db = SessionLocal()
    temp_root: str | None = None
    new_prefix: str | None = None
    source = None
    try:
        video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == video_id).first()
        if not video:
            return
        source = get_media_asset(db, "video", video_id, "source")
        if not source:
            legacy_path = (LEGACY_VIDEO_ROOT / (video.file_path or "")).resolve()
            if LEGACY_VIDEO_ROOT.resolve() not in legacy_path.parents or not legacy_path.is_file():
                return
            stored = object_storage.put_file(
                bucket=MEDIA_BUCKET,
                object_key=build_object_key(f"videos/{video_id}/source", legacy_path.name),
                source_path=legacy_path,
                content_type=guess_content_type(legacy_path.name),
            )
            source = upsert_media_asset(
                db,
                owner_type="video",
                owner_key=video_id,
                asset_kind="source",
                stored=stored,
                original_filename=legacy_path.name,
                content_type=guess_content_type(legacy_path.name),
            )
            video.file_path = stored.object_key
            db.commit()
        current = get_media_asset(db, "video", video_id, PLAYBACK_ASSET_KIND)
        current_meta = _metadata(current)
        if current_meta.get("status") == "ready" and current_meta.get("source_fingerprint") == _source_fingerprint(source):
            return

        version = uuid.uuid4().hex[:12]
        new_prefix = f"videos/{video_id}/hls/{version}"
        old_prefix = current_meta.get("prefix")
        _save_state(db, video_id, status="processing", source=source, version=version, error=None)

        temp_root = tempfile.mkdtemp(prefix=f"video-hls-{video_id}-")
        output_dir = Path(temp_root) / "hls"
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(source.original_filename or source.object_key).suffix or ".mp4"
        with object_storage.local_file(
            bucket=source.bucket,
            object_key=source.object_key,
            provider=source.storage_provider,
            suffix=suffix,
        ) as input_path:
            command = [
                FFMPEG_BINARY,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                input_path,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c",
                "copy",
                "-f",
                "hls",
                "-hls_time",
                str(HLS_SEGMENT_SECONDS),
                "-hls_playlist_type",
                "vod",
                "-hls_segment_type",
                "fmp4",
                "-hls_flags",
                "independent_segments",
                "-hls_fmp4_init_filename",
                "init.mp4",
                "-hls_segment_filename",
                str(output_dir / "segment_%05d.m4s"),
                str(output_dir / "index.m3u8"),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=1800)
            if completed.returncode != 0:
                raise RuntimeError((completed.stderr or "ffmpeg HLS packaging failed")[-2000:])

        files = sorted(path for path in output_dir.iterdir() if path.is_file())
        segments = [path.name for path in files if path.suffix == ".m4s"]
        if not segments or not (output_dir / "index.m3u8").exists():
            raise RuntimeError("HLS packaging produced no playable segments")

        for path in files:
            content_type = {
                ".m3u8": "application/vnd.apple.mpegurl",
                ".m4s": "video/iso.segment",
                ".mp4": "video/mp4",
            }.get(path.suffix.lower(), "application/octet-stream")
            object_storage.put_file(
                bucket=source.bucket or MEDIA_BUCKET,
                object_key=f"{new_prefix}/{path.name}",
                source_path=path,
                content_type=content_type,
                cache_control=IMMUTABLE_CACHE_CONTROL,
            )

        playback = _save_state(
            db,
            video_id,
            status="ready",
            source=source,
            version=version,
            prefix=new_prefix,
            segment_count=len(segments),
            segment_seconds=HLS_SEGMENT_SECONDS,
            error=None,
        )
        playback.object_key = f"{new_prefix}/index.m3u8"
        playback.file_size = (output_dir / "index.m3u8").stat().st_size
        db.commit()
        if old_prefix and old_prefix != new_prefix:
            object_storage.delete_prefix(source.bucket, old_prefix, source.storage_provider)
    except Exception as exc:
        if new_prefix and source:
            object_storage.delete_prefix(source.bucket, new_prefix, source.storage_provider)
        if source:
            _save_state(db, video_id, status="failed", source=source, error=str(exc)[-2000:])
        print(f"[video-playback] video_id={video_id} failed: {exc}")
    finally:
        db.close()
        if temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)


def _worker() -> None:
    while True:
        video_id = _job_queue.get()
        try:
            _process_video(video_id)
        finally:
            with _queue_lock:
                _queued_ids.discard(video_id)
            _job_queue.task_done()


def _ensure_worker() -> None:
    global _worker_started
    with _queue_lock:
        if _worker_started:
            return
        threading.Thread(target=_worker, name="video-playback-worker", daemon=True).start()
        _worker_started = True


def enqueue_playback(video_id: int) -> bool:
    _ensure_worker()
    with _queue_lock:
        if video_id in _queued_ids:
            return False
        _queued_ids.add(video_id)
        _job_queue.put(video_id)
        return True


def enqueue_existing_videos() -> int:
    db = SessionLocal()
    try:
        video_ids = [row[0] for row in db.query(models.TrainingVideo.id).all()]
    finally:
        db.close()
    return sum(1 for video_id in video_ids if enqueue_playback(video_id))


def schedule_existing_videos(delay_seconds: int = 20) -> None:
    timer = threading.Timer(delay_seconds, enqueue_existing_videos)
    timer.name = "video-playback-backfill"
    timer.daemon = True
    timer.start()


def delete_playback_assets(db, video_id: int) -> int:
    asset = get_media_asset(db, "video", video_id, PLAYBACK_ASSET_KIND)
    if not asset:
        return 0
    prefix = _metadata(asset).get("prefix")
    if prefix:
        object_storage.delete_prefix(asset.bucket, prefix, asset.storage_provider)
    db.delete(asset)
    db.flush()
    return 1


def build_signed_manifest(db, video: models.TrainingVideo) -> dict:
    status = get_playback_status(db, video)
    if status["status"] != "ready":
        return status
    asset = get_media_asset(db, "video", video.id, PLAYBACK_ASSET_KIND)
    if not asset or not asset.object_key:
        return {**status, "status": "missing"}
    metadata = _metadata(asset)
    prefix = str(metadata.get("prefix") or "").rstrip("/")
    manifest = object_storage.read_bytes(
        bucket=asset.bucket,
        object_key=asset.object_key,
        provider=asset.storage_provider,
    ).decode("utf-8")

    def signed(name: str) -> str:
        return object_storage.url_for_object(
            bucket=asset.bucket,
            object_key=f"{prefix}/{name.lstrip('/')}",
            provider=asset.storage_provider,
        )

    rewritten = re.sub(r'URI="([^"]+)"', lambda match: f'URI="{signed(match.group(1))}"', manifest)
    lines = []
    for line in rewritten.splitlines():
        stripped = line.strip()
        lines.append(signed(stripped) if stripped and not stripped.startswith("#") else line)
    return {**status, "manifest": "\n".join(lines) + "\n"}
