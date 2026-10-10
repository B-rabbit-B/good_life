import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.llm.service import AdapterFactory, get_adapter_factory
from app.nutrition.catalog import Catalog, load_catalog
from app.nutrition.deps import require_nutrition_user
from app.photos import service
from app.photos.images import MAX_UPLOAD_BYTES
from app.photos.matching import needs_review, totals
from app.photos.models import PhotoRecognition
from app.photos.schemas import ConfirmIn, ItemsUpdate, RecognitionOut, RecognitionSummaryOut

router = APIRouter(prefix="/api/photos", tags=["photos"])

PhotoUser = Annotated[User, Depends(require_nutrition_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]
Factory = Annotated[AdapterFactory, Depends(get_adapter_factory)]


def _fields(record: PhotoRecognition, items: list[dict[str, Any]], catalog: Catalog) -> dict[str, Any]:
    return {
        "id": record.id,
        "status": record.status,
        "items": items,
        "totals": totals(items, catalog),
        "needs_review": needs_review(items),
        "disclaimer": service.DISCLAIMER,
        "note": record.note,
        "image_kept": record.image_kept,
        "model_id": record.model_id,
        "eaten_on": record.eaten_on,
        "meal_type": record.meal_type,
        "meal_entry_ids": record.meal_entry_ids,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _out(db: Session, user_id: uuid.UUID, record: PhotoRecognition, today: date) -> RecognitionOut:
    """草稿才带评价：确认后这一餐已计入当日摄入，再评价会重复计算。"""
    catalog = load_catalog()
    items = service.current_items(record.items, catalog)
    evaluation = service.evaluate(db, user_id, items, today) if record.status == service.DRAFT else None
    return RecognitionOut(**_fields(record, items, catalog), evaluation=evaluation)


@router.post("/recognitions", status_code=201, response_model=RecognitionOut)
def create_recognition(
    file: UploadFile,
    user: PhotoUser,
    db: DbSession,
    today: Today,
    factory: Factory,
    keep_image: Annotated[bool, Form()] = False,
) -> RecognitionOut:
    """上传一张餐食照片识别为草稿。先结束自己的读事务再识别，调用模型期间不占数据库事务。"""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    user_id = user.id
    db.close()
    rec_id = service.recognize(user_id, content, keep_image, factory=factory)
    return _out(db, user_id, service.get_recognition(db, user_id, rec_id), today)


@router.get("/recognitions", response_model=list[RecognitionSummaryOut])
def list_recognitions(user: PhotoUser, db: DbSession) -> list[RecognitionSummaryOut]:
    catalog = load_catalog()
    return [
        RecognitionSummaryOut(**_fields(record, service.current_items(record.items, catalog), catalog))
        for record in service.list_recognitions(db, user.id)
    ]


@router.get("/recognitions/{rec_id}", response_model=RecognitionOut)
def get_recognition(rec_id: uuid.UUID, user: PhotoUser, db: DbSession, today: Today) -> RecognitionOut:
    return _out(db, user.id, service.get_recognition(db, user.id, rec_id), today)


@router.put("/recognitions/{rec_id}/items", response_model=RecognitionOut)
def update_items(
    rec_id: uuid.UUID, body: ItemsUpdate, user: PhotoUser, db: DbSession, today: Today
) -> RecognitionOut:
    items = [item.model_dump(exclude_unset=True) for item in body.items]
    return _out(db, user.id, service.update_items(db, user.id, rec_id, items), today)


@router.post("/recognitions/{rec_id}/confirm", response_model=RecognitionOut)
def confirm(rec_id: uuid.UUID, body: ConfirmIn, user: PhotoUser, db: DbSession, today: Today) -> RecognitionOut:
    record = service.confirm(db, user.id, rec_id, body.eaten_on, body.meal_type, today)
    return _out(db, user.id, record, today)


@router.post("/recognitions/{rec_id}/discard", response_model=RecognitionOut)
def discard(rec_id: uuid.UUID, user: PhotoUser, db: DbSession, today: Today) -> RecognitionOut:
    return _out(db, user.id, service.discard(db, user.id, rec_id), today)


@router.delete("/recognitions/{rec_id}", status_code=204)
def delete_recognition(rec_id: uuid.UUID, user: PhotoUser, db: DbSession) -> Response:
    service.delete_recognition(db, user.id, rec_id)
    return Response(status_code=204)


@router.get("/recognitions/{rec_id}/image")
def get_image(rec_id: uuid.UUID, user: PhotoUser, db: DbSession) -> Response:
    return Response(
        content=service.get_image(db, user.id, rec_id),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
