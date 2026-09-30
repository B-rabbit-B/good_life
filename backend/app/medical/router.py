import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.medical import items, orders
from app.medical.deps import require_medical_user
from app.medical.models import MedicalEvidence, MedicalItem, MedicalItemEvent, MedicalOrder
from app.medical.schemas import (
    Category,
    ConstraintOut,
    ConstraintsOut,
    ContinueBody,
    EventOut,
    EvidenceOut,
    IgnoredOut,
    ItemOut,
    ItemStatus,
    ItemUpdate,
    ManualItemCreate,
    OrderCreate,
    OrderOut,
    ProposalBody,
    ReasonBody,
)

router = APIRouter(prefix="/api/medical", tags=["medical"])

MedicalUser = Annotated[User, Depends(require_medical_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]


def _order_out(db: Session, user_id: uuid.UUID, order: MedicalOrder) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_date=order.order_date,
        source_text=order.source_text,
        extractor=order.extractor,
        created_at=order.created_at,
        ignored=[IgnoredOut(**ignored) for ignored in order.extraction_notes["ignored"]],
        notes=order.extraction_notes["notes"],
        items=[ItemOut.model_validate(item) for item in orders.list_order_items(db, user_id, order.id)],
        evidence=[EvidenceOut.model_validate(e) for e in orders.list_evidence(db, user_id, order.id)],
    )


@router.post("/orders", status_code=201, response_model=OrderOut)
def create_order(body: OrderCreate, user: MedicalUser, db: DbSession, today: Today) -> OrderOut:
    order = orders.create_order(db, user.id, body.text, body.order_date or today, today)
    return _order_out(db, user.id, order)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(user: MedicalUser, db: DbSession) -> list[OrderOut]:
    return [_order_out(db, user.id, order) for order in orders.list_orders(db, user.id)]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, user: MedicalUser, db: DbSession) -> OrderOut:
    return _order_out(db, user.id, orders.get_order(db, user.id, order_id))


@router.post("/orders/{order_id}/items", status_code=201, response_model=ItemOut)
def add_manual_item(order_id: uuid.UUID, body: ManualItemCreate, user: MedicalUser, db: DbSession) -> MedicalItem:
    return orders.add_manual_item(db, user.id, order_id, body.model_dump())


@router.post("/orders/{order_id}/evidence", status_code=201, response_model=EvidenceOut)
def upload_evidence(order_id: uuid.UUID, file: UploadFile, user: MedicalUser, db: DbSession) -> MedicalEvidence:
    content = file.file.read(orders.MAX_EVIDENCE_BYTES + 1)
    return orders.add_evidence(db, user.id, order_id, file.filename or "", content)


@router.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: uuid.UUID, user: MedicalUser, db: DbSession) -> Response:
    evidence = orders.get_evidence(db, user.id, evidence_id)
    extension = orders.EVIDENCE_EXTENSIONS[evidence.content_type]
    return Response(
        content=evidence.content,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="evidence-{evidence.id}{extension}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/items", response_model=list[ItemOut])
def list_items(
    user: MedicalUser, db: DbSession, status: ItemStatus | None = None, category: Category | None = None
) -> list[MedicalItem]:
    return items.list_items(db, user.id, status=status, category=category)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.get_item(db, user.id, item_id)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID, body: ItemUpdate, user: MedicalUser, db: DbSession, today: Today
) -> MedicalItem:
    return items.update_item(db, user.id, item_id, body.model_dump(exclude_unset=True), today=today)


@router.post("/items/{item_id}/confirm", response_model=ItemOut)
def confirm_item(
    item_id: uuid.UUID, user: MedicalUser, db: DbSession, today: Today, body: ItemUpdate | None = None
) -> MedicalItem:
    changes = body.model_dump(exclude_unset=True) if body else {}
    return items.confirm_item(db, user.id, item_id, changes, today)


@router.post("/items/{item_id}/void", response_model=ItemOut)
def void_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession, body: ReasonBody | None = None) -> MedicalItem:
    return items.void_item(db, user.id, item_id, body.reason if body else None)


@router.post("/items/{item_id}/continue", response_model=ItemOut)
def continue_item(
    item_id: uuid.UUID, body: ContinueBody, user: MedicalUser, db: DbSession, today: Today
) -> MedicalItem:
    return items.continue_item(db, user.id, item_id, body.end_date, body.review_date, today)


@router.post("/items/{item_id}/propose-resolution", response_model=ItemOut)
def propose_resolution(item_id: uuid.UUID, body: ProposalBody, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.propose_resolution(db, user.id, item_id, body.reason, "user")


@router.post("/items/{item_id}/cancel-proposal", response_model=ItemOut)
def cancel_proposal(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.cancel_resolution_proposal(db, user.id, item_id)


@router.post("/items/{item_id}/resolve", response_model=ItemOut)
def resolve_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession, body: ReasonBody | None = None) -> MedicalItem:
    return items.resolve_item(db, user.id, item_id, body.reason if body else None)


@router.get("/items/{item_id}/events", response_model=list[EventOut])
def list_events(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> list[MedicalItemEvent]:
    return items.list_events(db, user.id, item_id)


@router.get("/constraints", response_model=ConstraintsOut)
def get_constraints(
    user: MedicalUser, db: DbSession, today: Today, category: Category | None = None
) -> ConstraintsOut:
    constraints = items.get_current_constraints(db, user.id, today, category=category)
    return ConstraintsOut(
        constraints=[ConstraintOut.model_validate(c) for c in constraints], reminder=items.CONSTRAINT_REMINDER
    )


@router.get("/reviews", response_model=list[ItemOut])
def list_reviews(user: MedicalUser, db: DbSession, today: Today) -> list[MedicalItem]:
    return items.list_reviews(db, user.id, today)
