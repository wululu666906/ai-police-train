from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
import models
from services.object_storage_service import (
    MEDIA_BUCKET,
    build_object_key,
    get_media_asset,
    guess_content_type,
    object_storage,
    upsert_media_asset,
)


LEGACY_VIDEO_DIR = (BACKEND_DIR / "static" / "videos").resolve()
LEGACY_THUMBNAIL_DIR = (BACKEND_DIR / "static" / "thumbnails").resolve()


@dataclass
class MigrationStats:
    source_migrated: int = 0
    thumbnail_migrated: int = 0
    already_migrated: int = 0
    missing_source: int = 0
    missing_thumbnail: int = 0
    cleared_thumbnail: int = 0
    failed: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy training video files to object storage.")
    parser.add_argument("--apply", action="store_true", help="Upload files and update database records.")
    parser.add_argument(
        "--clear-missing-thumbnails",
        action="store_true",
        help="Clear thumbnail paths that have neither a media asset nor a local file.",
    )
    return parser.parse_args()


def resolve_legacy_file(root: Path, value: str | None) -> Path | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("http://", "https://")):
        return None
    candidate = (root / raw.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def migrate_video(db, video: models.TrainingVideo, args: argparse.Namespace, stats: MigrationStats) -> None:
    source_asset = get_media_asset(db, "video", video.id, "source")
    source_path = resolve_legacy_file(LEGACY_VIDEO_DIR, video.file_path)
    thumbnail_asset = get_media_asset(db, "video", video.id, "thumbnail")
    thumbnail_path = resolve_legacy_file(LEGACY_THUMBNAIL_DIR, video.thumbnail_path)

    if source_asset:
        stats.already_migrated += 1
    elif source_path:
        print(f"video={video.id} source={source_path.name} action={'migrate' if args.apply else 'preview'}")
        if args.apply:
            stored = object_storage.put_file(
                bucket=MEDIA_BUCKET,
                object_key=build_object_key(f"videos/{video.id}/source", source_path.name),
                source_path=source_path,
                content_type=guess_content_type(source_path.name),
                cache_control="private, max-age=7200",
            )
            upsert_media_asset(
                db,
                owner_type="video",
                owner_key=video.id,
                asset_kind="source",
                stored=stored,
                original_filename=source_path.name,
                content_type=stored.content_type,
            )
            video.file_path = stored.object_key
            stats.source_migrated += 1
    else:
        stats.missing_source += 1
        print(f"video={video.id} source={video.file_path!r} action=missing")

    if thumbnail_asset or not video.thumbnail_path:
        pass
    elif thumbnail_path:
        print(f"video={video.id} thumbnail={thumbnail_path.name} action={'migrate' if args.apply else 'preview'}")
        if args.apply:
            stored = object_storage.put_file(
                bucket=MEDIA_BUCKET,
                object_key=build_object_key(f"videos/{video.id}/thumbnails", thumbnail_path.name),
                source_path=thumbnail_path,
                content_type=guess_content_type(thumbnail_path.name),
                cache_control="private, max-age=7200",
            )
            upsert_media_asset(
                db,
                owner_type="video",
                owner_key=video.id,
                asset_kind="thumbnail",
                stored=stored,
                original_filename=thumbnail_path.name,
                content_type=stored.content_type,
            )
            video.thumbnail_path = stored.object_key
            stats.thumbnail_migrated += 1
    else:
        stats.missing_thumbnail += 1
        action = "clear" if args.apply and args.clear_missing_thumbnails else "missing"
        print(f"video={video.id} thumbnail={video.thumbnail_path!r} action={action}")
        if args.apply and args.clear_missing_thumbnails:
            video.thumbnail_path = None
            stats.cleared_thumbnail += 1


def main() -> int:
    args = parse_args()
    if object_storage.provider != "minio":
        raise RuntimeError(f"STORAGE_PROVIDER must be minio, got {object_storage.provider!r}")

    stats = MigrationStats()
    db = database.SessionLocal()
    try:
        videos = db.query(models.TrainingVideo).order_by(models.TrainingVideo.id).all()
        for video in videos:
            try:
                migrate_video(db, video, args, stats)
                if args.apply:
                    db.commit()
            except Exception as error:
                db.rollback()
                stats.failed += 1
                print(f"video={video.id} action=failed error={error}")
    finally:
        db.close()

    mode = "apply" if args.apply else "preview"
    print(
        f"mode={mode} source_migrated={stats.source_migrated} "
        f"thumbnail_migrated={stats.thumbnail_migrated} already_migrated={stats.already_migrated} "
        f"missing_source={stats.missing_source} missing_thumbnail={stats.missing_thumbnail} "
        f"cleared_thumbnail={stats.cleared_thumbnail} failed={stats.failed}"
    )
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
