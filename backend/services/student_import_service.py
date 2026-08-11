from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from routers.auth import hash_password, write_account_audit
from routers.classes import deactivate_other_student_memberships, generate_invite_code
from services.face_service import apply_prepared_profile, prepare_profile
from services.profile_image_service import prepare_profile_image
from services.tabular_import_service import ExcelImportError, clean_cell_text, parse_excel_table

IMPORT_ROOT = Path(__file__).resolve().parents[1] / "data" / "student_imports"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 300 * 1024 * 1024
MAX_ROSTER_BYTES = 15 * 1024 * 1024
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTOS = 2000
DEFAULT_PASSWORD = "123456"
STUDENT_NO_PATTERN = re.compile(r"^[0-9A-Za-z._-]{1,50}$")

HEADER_ALIASES = {
    "student_no": {"学号", "学生学号", "学员学号", "student_id", "student_no", "studentno", "username", "账号"},
    "real_name": {"姓名", "名字", "real_name", "name"},
    "gender": {"性别", "gender", "sex"},
    "unit": {"单位", "学校", "unit", "organization"},
    "department": {"院系", "系部", "部门", "单位/院系", "单位／院系", "department", "college"},
    "class_name": {"班级", "所属班级", "class", "class_name"},
}


def _json(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return fallback


def _cell(value: Any) -> str:
    return clean_cell_text(value)


def parse_roster(content: bytes) -> list[dict[str, str]]:
    try:
        parsed = parse_excel_table(
            content,
            aliases=HEADER_ALIASES,
            required_field="student_no",
            allowed_fields=HEADER_ALIASES.keys(),
            max_bytes=MAX_ROSTER_BYTES,
        )
    except ExcelImportError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return [
        {key: value for key, value in record.items() if key != "sheet_name"}
        for record in parsed.records
    ]


def _safe_zip_members(content: bytes) -> tuple[bytes, dict[str, bytes]]:
    if not content or len(content) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=400, detail="ZIP 文件为空或超过 100MB 限制")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP 压缩包格式无效")
    members = [item for item in archive.infolist() if not item.is_dir()]
    if len(members) > MAX_PHOTOS + 1 or sum(item.file_size for item in members) > MAX_EXTRACTED_BYTES:
        raise HTTPException(status_code=400, detail="ZIP 文件数量或解压后总体积超过限制")

    roster: bytes | None = None
    photos: dict[str, bytes] = {}
    for member in members:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise HTTPException(status_code=400, detail="ZIP 中存在不安全的文件路径")
        if len(path.parts) == 1 and path.name == "学员名单.xlsx":
            roster = archive.read(member)
            continue
        if len(path.parts) == 2 and path.parts[0].lower() == "photos" and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            student_no = path.stem.strip()
            if not student_no:
                continue
            if student_no in photos:
                raise HTTPException(status_code=400, detail=f"学号 {student_no} 存在重复人脸图片")
            raw = archive.read(member)
            if len(raw) > MAX_PHOTO_BYTES:
                raise HTTPException(status_code=400, detail=f"{path.name} 超过 8MB 限制")
            photos[student_no] = raw
    if roster is None:
        raise HTTPException(status_code=400, detail="ZIP 根目录缺少“学员名单.xlsx”")
    return roster, photos


def _normalize_gender(value: str) -> str:
    aliases = {"male": "男", "m": "男", "1": "男", "female": "女", "f": "女", "2": "女"}
    return aliases.get(value.strip().lower(), value.strip())


def valid_student_no(value: str) -> bool:
    return bool(STUDENT_NO_PATTERN.fullmatch(value)) and value not in {".", ".."}


def _stage_photos(batch_id: str, photos: dict[str, bytes]) -> dict[str, str]:
    batch_dir = IMPORT_ROOT / batch_id / "photos"
    batch_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for student_no, raw in photos.items():
        if not valid_student_no(student_no):
            raise HTTPException(status_code=400, detail=f"照片文件名中的学号格式无效：{student_no}")
        prepared = prepare_profile_image(raw, max_bytes=MAX_PHOTO_BYTES)
        target = batch_dir / f"{student_no}.jpg"
        target.write_bytes(prepared.content)
        paths[student_no] = str(target)
    return paths


def _validate_item(db: Session, item: models.StudentImportItem) -> None:
    data = _json(item.data_json, {})
    student_no = _cell(data.get("student_no"))
    data["student_no"] = student_no
    data["gender"] = _normalize_gender(_cell(data.get("gender")))
    if data.get("source_kind") == "orphan_photo":
        item.student_no = student_no
        item.matched_user_id = None
        item.data_json = json.dumps(data, ensure_ascii=False)
        item.errors_json = json.dumps(["图片文件名中的学号未在Excel名单中找到"], ensure_ascii=False)
        item.warnings_json = "[]"
        item.status = "error"
        return
    errors: list[str] = []
    warnings: list[str] = []
    if not student_no:
        errors.append("学号不能为空")
    elif len(student_no) > 50:
        errors.append("学号不能超过 50 个字符")
    elif not valid_student_no(student_no):
        errors.append("学号只能包含字母、数字、点、横线或下划线")
    if data["gender"] and data["gender"] not in {"男", "女", "其他"}:
        errors.append("性别仅支持男、女或其他")

    user = db.query(models.User).filter(models.User.username == student_no).first() if student_no else None
    if user and user.role != "student":
        errors.append("该学号已被非学员账号占用")
        user = None
    item.matched_user_id = user.id if user else None

    photo_file = Path(item.photo_path) if item.photo_path else None
    if photo_file and photo_file.exists() and not item.face_embedding_json:
        try:
            extraction = prepare_profile(photo_file.read_bytes())
            item.face_embedding_json = json.dumps(extraction.embedding)
            item.face_quality_json = json.dumps(extraction.quality, ensure_ascii=False)
        except HTTPException as error:
            errors.append(str(error.detail))
            item.face_embedding_json = None
            item.face_quality_json = None
        except Exception:
            errors.append("人脸照片无法识别")
            item.face_embedding_json = None
            item.face_quality_json = None
    elif not user:
        errors.append("新建学员必须提供以学号命名的有效人脸照片")
    else:
        warnings.append("未提供新照片，将保留原人脸档案")
        item.replace_face = False

    item.student_no = student_no
    item.data_json = json.dumps(data, ensure_ascii=False)
    item.errors_json = json.dumps(list(dict.fromkeys(errors)), ensure_ascii=False)
    item.warnings_json = json.dumps(list(dict.fromkeys(warnings)), ensure_ascii=False)
    item.status = "error" if errors else "pending"


def _mark_duplicate_rows(items: list[models.StudentImportItem]) -> None:
    counts: dict[str, int] = {}
    for item in items:
        if item.student_no:
            counts[item.student_no] = counts.get(item.student_no, 0) + 1
    for item in items:
        if item.status == "removed":
            continue
        errors = [error for error in _json(item.errors_json, []) if error != "名单中存在重复学号"]
        item.errors_json = json.dumps(errors, ensure_ascii=False)
        item.status = "error" if errors else "pending"
        if item.student_no and counts.get(item.student_no, 0) > 1:
            if "名单中存在重复学号" not in errors:
                errors.append("名单中存在重复学号")
            item.errors_json = json.dumps(errors, ensure_ascii=False)
            item.status = "error"


def create_batch(
    db: Session,
    *,
    actor: models.User,
    source_mode: str,
    source_name: str,
    roster_content: bytes,
    photos: dict[str, bytes],
) -> models.StudentImportBatch:
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail="人脸图片不能超过 2000 张")
    records = parse_roster(roster_content)
    batch_id = uuid4().hex
    staged_paths = _stage_photos(batch_id, photos)
    batch = models.StudentImportBatch(
        id=batch_id,
        created_by=actor.id,
        source_mode=source_mode,
        source_name=source_name,
        status="preview",
    )
    db.add(batch)
    db.flush()
    items: list[models.StudentImportItem] = []
    for record in records:
        student_no = _cell(record.get("student_no"))
        item = models.StudentImportItem(
            batch_id=batch_id,
            row_number=int(record.pop("row_number")),
            student_no=student_no,
            data_json=json.dumps(record, ensure_ascii=False),
            photo_path=staged_paths.get(student_no),
            photo_filename=f"{student_no}.jpg" if student_no in staged_paths else None,
        )
        db.add(item)
        db.flush()
        _validate_item(db, item)
        items.append(item)
    roster_student_nos = {_cell(record.get("student_no")) for record in records if _cell(record.get("student_no"))}
    next_row_number = max((item.row_number for item in items), default=0) + 1
    for offset, student_no in enumerate(sorted(set(staged_paths) - roster_student_nos)):
        item = models.StudentImportItem(
            batch_id=batch_id,
            row_number=next_row_number + offset,
            student_no=student_no,
            data_json=json.dumps({"student_no": student_no, "source_kind": "orphan_photo"}, ensure_ascii=False),
            photo_path=staged_paths[student_no],
            photo_filename=f"{student_no}.jpg",
            replace_face=False,
            replace_class=False,
        )
        db.add(item)
        db.flush()
        _validate_item(db, item)
        items.append(item)
    _mark_duplicate_rows(items)
    batch.summary_json = json.dumps(build_summary(db, items), ensure_ascii=False)
    db.commit()
    db.refresh(batch)
    return batch


def create_zip_batch(db: Session, *, actor: models.User, filename: str, content: bytes) -> models.StudentImportBatch:
    roster, photos = _safe_zip_members(content)
    return create_batch(
        db,
        actor=actor,
        source_mode="zip",
        source_name=filename,
        roster_content=roster,
        photos=photos,
    )


def build_summary(db: Session, items: list[models.StudentImportItem]) -> dict[str, int]:
    valid = [item for item in items if not _json(item.errors_json, []) and item.status not in {"removed", "failed"}]
    class_names = {_cell(_json(item.data_json, {}).get("class_name")) for item in valid}
    class_names.discard("")
    existing_names = {
        classroom.name.strip()
        for classroom in db.query(models.TrainingClass).filter(models.TrainingClass.name.in_(class_names)).all()
    } if class_names else set()
    return {
        "total": len([item for item in items if item.status != "removed"]),
        "new_students": len([item for item in valid if not item.matched_user_id]),
        "matched": len([item for item in valid if item.matched_user_id]),
        "new_classes": len(class_names - existing_names),
        "skipped": len([item for item in items if item.status == "removed"]),
        "errors": len([item for item in items if (_json(item.errors_json, []) or item.status == "failed") and item.status != "removed"]),
        "ready": len([item for item in valid if item.status == "pending"]),
        "synced": len([item for item in items if item.status == "synced"]),
    }


def get_owned_batch(db: Session, batch_id: str, actor: models.User) -> models.StudentImportBatch:
    batch = db.query(models.StudentImportBatch).filter(
        models.StudentImportBatch.id == batch_id,
        models.StudentImportBatch.created_by == actor.id,
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="导入批次不存在或无权访问")
    return batch


def serialize_item(item: models.StudentImportItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "row_number": item.row_number,
        "student_no": item.student_no or "",
        "matched_user_id": item.matched_user_id,
        "is_new": item.matched_user_id is None,
        "data": _json(item.data_json, {}),
        "source_kind": _json(item.data_json, {}).get("source_kind", "roster"),
        "errors": _json(item.errors_json, []),
        "warnings": _json(item.warnings_json, []),
        "has_photo": bool(item.photo_path and Path(item.photo_path).exists()),
        "photo_url": f"/student-imports/{item.batch_id}/items/{item.id}/photo" if item.photo_path else None,
        "replace_face": bool(item.replace_face),
        "replace_class": bool(item.replace_class),
        "status": item.status,
        "result": _json(item.result_json, None),
    }


def serialize_batch(db: Session, batch: models.StudentImportBatch) -> dict[str, Any]:
    items = sorted(
        batch.items,
        key=lambda item: (0 if (_json(item.errors_json, []) or item.status == "failed") and item.status != "removed" else 1 if not item.matched_user_id else 2, item.row_number),
    )
    stored_summary = _json(batch.summary_json, {})
    summary = build_summary(db, items)
    if batch.status == "completed" and "created_classes" in stored_summary:
        summary["created_classes"] = int(stored_summary["created_classes"] or 0)
    batch.summary_json = json.dumps(summary, ensure_ascii=False)
    return {
        "batch_id": batch.id,
        "source_mode": batch.source_mode,
        "source_name": batch.source_name,
        "status": batch.status,
        "summary": summary,
        "items": [serialize_item(item) for item in items if item.status != "removed"],
    }


def update_item(db: Session, batch: models.StudentImportBatch, item_id: int, payload: dict[str, Any]) -> None:
    if batch.status != "preview":
        raise HTTPException(status_code=409, detail="该批次已结束，不能继续修改")
    item = next((row for row in batch.items if row.id == item_id), None)
    if not item or item.status == "removed":
        raise HTTPException(status_code=404, detail="导入条目不存在")
    data = _json(item.data_json, {})
    for field in ("student_no", "real_name", "gender", "unit", "department", "class_name"):
        if field in payload and payload[field] is not None:
            data[field] = _cell(payload[field])
    item.replace_face = bool(payload.get("replace_face", item.replace_face))
    item.replace_class = bool(payload.get("replace_class", item.replace_class))
    student_no = _cell(data.get("student_no"))
    if data.get("source_kind") == "orphan_photo":
        target = next(
            (
                row
                for row in batch.items
                if row.id != item.id
                and row.status != "removed"
                and _json(row.data_json, {}).get("source_kind") != "orphan_photo"
                and row.student_no == student_no
            ),
            None,
        )
        if target:
            target.photo_path = item.photo_path
            target.photo_filename = item.photo_filename
            target.face_embedding_json = None
            target.face_quality_json = None
            target.replace_face = True
            item.status = "removed"
            item.result_json = json.dumps({"merged_into_item_id": target.id}, ensure_ascii=False)
            _validate_item(db, target)
            _mark_duplicate_rows([row for row in batch.items if row.status != "removed"])
            db.commit()
            return
    candidate = IMPORT_ROOT / batch.id / "photos" / f"{student_no}.jpg" if valid_student_no(student_no) else None
    candidate_path = str(candidate) if candidate and candidate.exists() else None
    if item.photo_path != candidate_path:
        item.face_embedding_json = None
        item.face_quality_json = None
    item.photo_path = candidate_path
    item.photo_filename = candidate.name if candidate_path and candidate else None
    item.data_json = json.dumps(data, ensure_ascii=False)
    _validate_item(db, item)
    _mark_duplicate_rows([row for row in batch.items if row.status != "removed"])
    db.commit()


def remove_item(db: Session, batch: models.StudentImportBatch, item_id: int) -> None:
    if batch.status != "preview":
        raise HTTPException(status_code=409, detail="该批次已结束，不能继续修改")
    item = next((row for row in batch.items if row.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="导入条目不存在")
    item.status = "removed"
    db.commit()


def replace_item_photo(
    db: Session,
    batch: models.StudentImportBatch,
    item_id: int,
    *,
    filename: str,
    raw: bytes,
) -> None:
    if batch.status != "preview":
        raise HTTPException(status_code=409, detail="该批次已结束，不能继续修改")
    item = next((row for row in batch.items if row.id == item_id and row.status != "removed"), None)
    if not item:
        raise HTTPException(status_code=404, detail="导入条目不存在")
    path = Path(filename)
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} or path.stem != item.student_no:
        raise HTTPException(status_code=400, detail=f"照片必须以学号命名，并使用 JPG、PNG 或 WebP 格式")
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="人脸图片为空或超过 8MB 限制")
    target = IMPORT_ROOT / batch.id / "photos" / f"{item.student_no}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    prepared = prepare_profile_image(raw, max_bytes=MAX_PHOTO_BYTES)
    target.write_bytes(prepared.content)
    item.photo_path = str(target)
    item.photo_filename = target.name
    item.face_embedding_json = None
    item.face_quality_json = None
    item.replace_face = True
    _validate_item(db, item)
    _mark_duplicate_rows([row for row in batch.items if row.status != "removed"])
    db.commit()


def _get_or_create_class(db: Session, name: str, actor_id: int) -> tuple[models.TrainingClass, bool]:
    normalized = name.strip()
    classroom = db.query(models.TrainingClass).filter(models.TrainingClass.name == normalized).first()
    if classroom:
        return classroom, False
    classroom = models.TrainingClass(
        name=normalized,
        description="由学员批量导入自动创建",
        invite_code=generate_invite_code(db),
        muted=True,
        created_by=actor_id,
    )
    db.add(classroom)
    db.flush()
    return classroom, True


def commit_batch(db: Session, batch: models.StudentImportBatch, actor: models.User) -> dict[str, Any]:
    if batch.status != "preview":
        raise HTTPException(status_code=409, detail="该批次已经执行或不可重复同步")
    created_classes = 0
    for item in sorted(batch.items, key=lambda row: row.row_number):
        errors = _json(item.errors_json, [])
        if item.status == "removed" or errors:
            continue
        try:
            data = _json(item.data_json, {})
            user = db.query(models.User).filter(models.User.username == item.student_no).first()
            created = user is None
            if created:
                user = models.User(username=item.student_no, hashed_password=hash_password(DEFAULT_PASSWORD), role="student")
                db.add(user)
                db.flush()
            if not user or user.role != "student":
                raise ValueError("目标账号不是学员账号")
            for field in ("real_name", "gender", "unit", "department"):
                value = _cell(data.get(field))
                if value:
                    setattr(user, field, value)
            if created and user.real_name:
                user.display_name = user.real_name

            class_name = _cell(data.get("class_name"))
            class_changed = False
            if class_name and item.replace_class:
                classroom, class_created = _get_or_create_class(db, class_name, actor.id)
                created_classes += int(class_created)
                deactivate_other_student_memberships(db, user.id, classroom.id)
                membership = db.query(models.ClassMembership).filter(
                    models.ClassMembership.class_id == classroom.id,
                    models.ClassMembership.user_id == user.id,
                ).first()
                if membership:
                    membership.status = "active"
                    membership.role = "student"
                else:
                    db.add(models.ClassMembership(class_id=classroom.id, user_id=user.id, role="student", status="active"))
                class_changed = True

            face_changed = False
            if item.photo_path and item.replace_face:
                raw = Path(item.photo_path).read_bytes()
                apply_prepared_profile(
                    db,
                    user,
                    raw,
                    embedding=_json(item.face_embedding_json, []),
                    quality=_json(item.face_quality_json, {}),
                    commit=False,
                )
                face_changed = True
            db.flush()
            write_account_audit(
                db,
                actor=actor,
                action="admin_import_student_profile",
                target_user=user,
                detail={"username": user.username, "created": created, "class_changed": class_changed, "face_changed": face_changed},
            )
            item.matched_user_id = user.id
            item.status = "synced"
            item.result_json = json.dumps(
                {"created": created, "profile_updated": True, "class_updated": class_changed, "face_updated": face_changed},
                ensure_ascii=False,
            )
            db.commit()
        except Exception as error:
            db.rollback()
            item = db.query(models.StudentImportItem).filter(models.StudentImportItem.id == item.id).first()
            if item:
                item.status = "failed"
                item.result_json = json.dumps({"message": str(error) or "同步失败"}, ensure_ascii=False)
                db.commit()
    batch = db.query(models.StudentImportBatch).filter(models.StudentImportBatch.id == batch.id).first()
    batch.status = "completed"
    batch.completed_at = datetime.utcnow()
    summary = build_summary(db, batch.items)
    summary["created_classes"] = created_classes
    batch.summary_json = json.dumps(summary, ensure_ascii=False)
    db.commit()
    return serialize_batch(db, batch)


def cleanup_expired_batches(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=48)
    expired = db.query(models.StudentImportBatch).filter(
        models.StudentImportBatch.created_at < cutoff,
        models.StudentImportBatch.status == "preview",
    ).all()
    for batch in expired:
        batch.status = "expired"
        shutil.rmtree(IMPORT_ROOT / batch.id, ignore_errors=True)
    if expired:
        db.commit()
