from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import require_admin_user
from services.student_import_service import (
    MAX_PHOTO_BYTES,
    cleanup_expired_batches,
    commit_batch,
    create_batch,
    create_zip_batch,
    get_owned_batch,
    remove_item,
    replace_item_photo,
    serialize_batch,
    update_item,
    valid_student_no,
)

router = APIRouter(prefix="/student-imports", tags=["Student imports"])


@router.post("/preview", response_model=schemas.StudentImportPreviewResponse)
async def preview_student_import(
    archive: UploadFile | None = File(default=None),
    roster: UploadFile | None = File(default=None),
    photos: list[UploadFile] = File(default=[]),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    cleanup_expired_batches(db)
    if archive:
        if roster or photos:
            raise HTTPException(status_code=400, detail="ZIP模式与多文件模式不能同时上传")
        if Path(archive.filename or "").suffix.lower() != ".zip":
            raise HTTPException(status_code=400, detail="压缩包必须为 ZIP 格式")
        batch = create_zip_batch(db, actor=current_user, filename=archive.filename or "import.zip", content=await archive.read())
        return serialize_batch(db, batch)
    if not roster:
        raise HTTPException(status_code=400, detail="请选择ZIP压缩包或学员名单.xlsx")
    if Path(roster.filename or "").suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="学员名单必须为 xlsx 格式")
    photo_map: dict[str, bytes] = {}
    for photo in photos:
        path = Path(photo.filename or "")
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} or not path.stem.strip():
            raise HTTPException(status_code=400, detail=f"人脸图片必须按“学号.图片后缀”命名：{path.name}")
        if path.stem in photo_map:
            raise HTTPException(status_code=400, detail=f"学号 {path.stem} 存在重复人脸图片")
        raw = await photo.read()
        if not valid_student_no(path.stem):
            raise HTTPException(status_code=400, detail=f"照片文件名中的学号格式无效：{path.stem}")
        if not raw or len(raw) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=400, detail=f"{path.name} 为空或超过 8MB 限制")
        photo_map[path.stem] = raw
    batch = create_batch(
        db,
        actor=current_user,
        source_mode="files",
        source_name=roster.filename or "学员名单.xlsx",
        roster_content=await roster.read(),
        photos=photo_map,
    )
    return serialize_batch(db, batch)


@router.get("/{batch_id}", response_model=schemas.StudentImportPreviewResponse)
def get_student_import(
    batch_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    return serialize_batch(db, get_owned_batch(db, batch_id, current_user))


@router.patch("/{batch_id}/items/{item_id}", response_model=schemas.StudentImportPreviewResponse)
def patch_student_import_item(
    batch_id: str,
    item_id: int,
    payload: schemas.StudentImportItemUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    batch = get_owned_batch(db, batch_id, current_user)
    update_item(db, batch, item_id, payload.model_dump())
    db.refresh(batch)
    return serialize_batch(db, batch)


@router.delete("/{batch_id}/items/{item_id}", response_model=schemas.StudentImportPreviewResponse)
def delete_student_import_item(
    batch_id: str,
    item_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    batch = get_owned_batch(db, batch_id, current_user)
    remove_item(db, batch, item_id)
    db.refresh(batch)
    return serialize_batch(db, batch)


@router.get("/{batch_id}/items/{item_id}/photo")
def get_student_import_photo(
    batch_id: str,
    item_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    batch = get_owned_batch(db, batch_id, current_user)
    item = next((row for row in batch.items if row.id == item_id and row.status != "removed"), None)
    if not item or not item.photo_path or not Path(item.photo_path).is_file():
        raise HTTPException(status_code=404, detail="人脸照片不存在")
    return FileResponse(item.photo_path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/{batch_id}/items/{item_id}/photo", response_model=schemas.StudentImportPreviewResponse)
async def replace_student_import_photo(
    batch_id: str,
    item_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    batch = get_owned_batch(db, batch_id, current_user)
    replace_item_photo(db, batch, item_id, filename=photo.filename or "", raw=await photo.read())
    db.refresh(batch)
    return serialize_batch(db, batch)


@router.post("/{batch_id}/commit", response_model=schemas.StudentImportCommitResponse)
def commit_student_import(
    batch_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    batch = get_owned_batch(db, batch_id, current_user)
    return commit_batch(db, batch, current_user)
