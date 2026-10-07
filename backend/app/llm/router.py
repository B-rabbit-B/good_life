import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.llm import service
from app.llm.kinds import PRESETS
from app.llm.models import LlmAssignment, LlmModel
from app.llm.schemas import (
    AssignmentOut,
    AssignmentSet,
    CapabilitiesOut,
    ModelCreate,
    ModelOut,
    ModelUpdatedOut,
    OverridesUpdate,
    PresetOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)

router = APIRouter(prefix="/api/llm", tags=["llm"])

LlmUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


def _model_out(model: LlmModel) -> ModelOut:
    effective, table, note = service.model_capabilities(model)
    return ModelOut(
        id=model.id,
        provider_id=model.provider_id,
        model_id=model.model_id,
        display_name=model.display_name,
        source=model.source,
        capabilities=CapabilitiesOut(**asdict(effective)),
        table_capabilities=CapabilitiesOut(**asdict(table)),
        overrides=CapabilitiesOut(vision=model.vision_override, tools=model.tools_override, chat=model.chat_override),
        capability_note=note,
    )


def _assignment_out(assignment: LlmAssignment, model: LlmModel, provider_name: str) -> AssignmentOut:
    return AssignmentOut(purpose=assignment.purpose, model=_model_out(model), provider_name=provider_name)


@router.get("/presets", response_model=list[PresetOut])
def list_presets(user: LlmUser) -> list[PresetOut]:
    return [PresetOut(id=p.id, name=p.name, kind=p.kind, base_url=p.base_url) for p in PRESETS]


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(user: LlmUser, db: DbSession) -> list[ProviderOut]:
    return [ProviderOut.model_validate(p) for p in service.list_providers(db, user.id)]


@router.post("/providers", status_code=201, response_model=ProviderOut)
def create_provider(body: ProviderCreate, user: LlmUser, db: DbSession) -> ProviderOut:
    provider = service.create_provider(db, user.id, body.name, body.kind, body.base_url, body.api_key)
    return ProviderOut.model_validate(provider)


@router.get("/providers/{provider_id}", response_model=ProviderOut)
def get_provider(provider_id: uuid.UUID, user: LlmUser, db: DbSession) -> ProviderOut:
    return ProviderOut.model_validate(service.get_provider(db, user.id, provider_id))


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(provider_id: uuid.UUID, body: ProviderUpdate, user: LlmUser, db: DbSession) -> ProviderOut:
    provider = service.update_provider(db, user.id, provider_id, body.model_dump(exclude_none=True))
    return ProviderOut.model_validate(provider)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: uuid.UUID, user: LlmUser, db: DbSession) -> Response:
    service.delete_provider(db, user.id, provider_id)
    return Response(status_code=204)


@router.get("/providers/{provider_id}/models", response_model=list[ModelOut])
def list_models(provider_id: uuid.UUID, user: LlmUser, db: DbSession) -> list[ModelOut]:
    return [_model_out(m) for m in service.list_models(db, user.id, provider_id)]


@router.post("/providers/{provider_id}/models", status_code=201, response_model=ModelOut)
def add_model(provider_id: uuid.UUID, body: ModelCreate, user: LlmUser, db: DbSession) -> ModelOut:
    return _model_out(service.add_manual_model(db, user.id, provider_id, body.model_id, body.display_name))


@router.patch("/models/{model_pk}", response_model=ModelUpdatedOut)
def update_model(model_pk: uuid.UUID, body: OverridesUpdate, user: LlmUser, db: DbSession) -> ModelUpdatedOut:
    model = service.update_model_overrides(db, user.id, model_pk, body.model_dump(exclude_unset=True))
    warnings = service.assignment_warnings(db, user.id, model)
    return ModelUpdatedOut(**_model_out(model).model_dump(), assignment_warnings=warnings)


@router.delete("/models/{model_pk}", status_code=204)
def delete_model(model_pk: uuid.UUID, user: LlmUser, db: DbSession) -> Response:
    service.delete_model(db, user.id, model_pk)
    return Response(status_code=204)


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(user: LlmUser, db: DbSession) -> list[AssignmentOut]:
    return [_assignment_out(*item) for item in service.list_assignments(db, user.id)]


@router.put("/assignments/{purpose}", response_model=AssignmentOut)
def set_assignment(purpose: str, body: AssignmentSet, user: LlmUser, db: DbSession) -> AssignmentOut:
    service.assign(db, user.id, purpose, body.model_id)
    items = service.list_assignments(db, user.id)
    return next(_assignment_out(*item) for item in items if item[0].purpose == purpose)


@router.delete("/assignments/{purpose}", status_code=204)
def clear_assignment(purpose: str, user: LlmUser, db: DbSession) -> Response:
    service.unassign(db, user.id, purpose)
    return Response(status_code=204)
