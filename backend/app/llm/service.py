import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.config import get_settings
from app.errors import AppError
from app.llm.capabilities import Capabilities, effective, table_capabilities
from app.llm.models import LlmAssignment, LlmModel, LlmProvider
from app.llm.urls import validate_base_url

MAX_PROVIDERS = 20
PURPOSES = ("chat", "vision")
PURPOSE_LABELS = {"chat": "日常对话", "vision": "看图识别"}
OVERRIDE_FIELDS = ("vision", "tools", "chat")


def key_hint(api_key: str) -> str:
    """只给掩码：末 4 位；不足 8 位时一位都不露。"""
    return "****" + api_key[-4:] if len(api_key) >= 8 else "****"


def _check_url(url: str) -> str:
    return validate_base_url(url, allow_private=get_settings().llm_allow_private_hosts)


def _provider_exists() -> AppError:
    return AppError(409, "llm_provider_exists", "已有同名的模型服务，请换一个名称或直接修改原来的服务")


def _commit_or_raise(db: Session, error: AppError) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise error from None


def _name_taken(db: Session, user_id: uuid.UUID, name: str, ignore_id: uuid.UUID | None = None) -> bool:
    query = owned_by(LlmProvider, user_id).where(LlmProvider.name == name)
    if ignore_id is not None:
        query = query.where(LlmProvider.id != ignore_id)
    return db.scalar(query) is not None


def create_provider(db: Session, user_id: uuid.UUID, name: str, kind: str, base_url: str, api_key: str) -> LlmProvider:
    base_url = _check_url(base_url)
    count = db.scalar(select(func.count()).select_from(LlmProvider).where(LlmProvider.user_id == user_id))
    if count >= MAX_PROVIDERS:
        raise AppError(409, "llm_too_many_providers", f"模型服务最多 {MAX_PROVIDERS} 个，请先删除不用的服务")
    if _name_taken(db, user_id, name):
        raise _provider_exists()
    provider = LlmProvider(
        user_id=user_id, name=name, kind=kind, base_url=base_url, api_key=api_key, key_hint=key_hint(api_key)
    )
    db.add(provider)
    _commit_or_raise(db, _provider_exists())
    return provider


def list_providers(db: Session, user_id: uuid.UUID) -> list[LlmProvider]:
    return list(db.scalars(owned_by(LlmProvider, user_id).order_by(LlmProvider.name, LlmProvider.id)))


def get_provider(db: Session, user_id: uuid.UUID, provider_id: uuid.UUID) -> LlmProvider:
    return get_owned_or_404(db, LlmProvider, user_id, provider_id)


def update_provider(db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, changes: dict[str, Any]) -> LlmProvider:
    """只能改名称、地址、密钥；服务类型不可改。密钥缺省保持原值。"""
    provider = get_provider(db, user_id, provider_id)
    if "name" in changes and changes["name"] != provider.name:
        if _name_taken(db, user_id, changes["name"], provider.id):
            raise _provider_exists()
        provider.name = changes["name"]
    if "base_url" in changes:
        provider.base_url = _check_url(changes["base_url"])
    if "api_key" in changes:
        provider.api_key = changes["api_key"]
        provider.key_hint = key_hint(changes["api_key"])
    _commit_or_raise(db, _provider_exists())
    return provider


def delete_provider(db: Session, user_id: uuid.UUID, provider_id: uuid.UUID) -> None:
    db.delete(get_provider(db, user_id, provider_id))
    db.commit()


def add_manual_model(
    db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, model_id: str, display_name: str | None = None
) -> LlmModel:
    provider = get_provider(db, user_id, provider_id)
    exists = AppError(409, "llm_model_exists", f"该服务下已有模型 {model_id}，无需重复添加")
    taken = owned_by(LlmModel, user_id).where(LlmModel.provider_id == provider.id, LlmModel.model_id == model_id)
    if db.scalar(taken) is not None:
        raise exists
    model = LlmModel(
        user_id=user_id, provider_id=provider.id, model_id=model_id, display_name=display_name, source="manual"
    )
    db.add(model)
    _commit_or_raise(db, exists)
    return model


def list_models(db: Session, user_id: uuid.UUID, provider_id: uuid.UUID) -> list[LlmModel]:
    provider = get_provider(db, user_id, provider_id)
    query = owned_by(LlmModel, user_id).where(LlmModel.provider_id == provider.id)
    return list(db.scalars(query.order_by(LlmModel.model_id, LlmModel.id)))


def get_model(db: Session, user_id: uuid.UUID, model_pk: uuid.UUID) -> LlmModel:
    return get_owned_or_404(db, LlmModel, user_id, model_pk)


def model_capabilities(model: LlmModel) -> tuple[Capabilities, Capabilities, str | None]:
    """返回（有效能力，对照表能力，命中规则的说明）。"""
    table, note = table_capabilities(model.model_id)
    overrides = Capabilities(model.vision_override, model.tools_override, model.chat_override)
    return effective(table, overrides), table, note


def update_model_overrides(
    db: Session, user_id: uuid.UUID, model_pk: uuid.UUID, overrides: dict[str, Any]
) -> LlmModel:
    """overrides 里出现的项才会改；值为 true、false 或 null（null 表示回到对照表）。"""
    model = get_model(db, user_id, model_pk)
    for name in OVERRIDE_FIELDS:
        if name in overrides:
            setattr(model, f"{name}_override", overrides[name])
    db.commit()
    return model


def _requirement_error(purpose: str, caps: Capabilities) -> AppError | None:
    if purpose == "vision" and caps.vision is not True:
        return AppError(
            422,
            "llm_model_lacks_vision",
            "这个模型的看图能力不是“支持”（对照表标明不支持，或查不到、无法确认）。"
            "如果你确认它能看图，请先在模型上手动标注“支持看图”，再分配到看图识别。",
        )
    if purpose == "chat" and caps.chat is False:
        return AppError(
            422,
            "llm_model_not_chat",
            "这个模型被标明不是对话模型（例如向量、语音、绘图模型），不能用于日常对话。"
            "如果标注有误，请先在模型上手动标注“支持对话”，再分配。",
        )
    return None


def assignment_warnings(db: Session, user_id: uuid.UUID, model: LlmModel) -> list[str]:
    """改能力之后，已分配到该模型的用途若不再满足要求，给出提醒（仍允许保存）。"""
    caps = model_capabilities(model)[0]
    query = owned_by(LlmAssignment, user_id).where(LlmAssignment.llm_model_id == model.id)
    warnings = []
    for assignment in db.scalars(query.order_by(LlmAssignment.purpose)):
        if _requirement_error(assignment.purpose, caps) is not None:
            warnings.append(
                f"该模型已分配为“{PURPOSE_LABELS[assignment.purpose]}”，但现在的能力标注不满足要求，"
                "使用时会报错；请重新分配其他模型，或把标注改回来。"
            )
    return warnings


def delete_model(db: Session, user_id: uuid.UUID, model_pk: uuid.UUID) -> None:
    db.delete(get_model(db, user_id, model_pk))
    db.commit()


def _check_purpose(purpose: str) -> None:
    if purpose not in PURPOSES:
        raise AppError(422, "llm_unknown_purpose", f"不支持的用途 {purpose}，可选：{'、'.join(PURPOSES)}")


def assign(db: Session, user_id: uuid.UUID, purpose: str, model_pk: uuid.UUID) -> LlmAssignment:
    _check_purpose(purpose)
    model = get_model(db, user_id, model_pk)
    error = _requirement_error(purpose, model_capabilities(model)[0])
    if error is not None:
        raise error
    upsert = pg_insert(LlmAssignment).values(id=uuid.uuid4(), user_id=user_id, purpose=purpose, llm_model_id=model.id)
    db.execute(
        upsert.on_conflict_do_update(
            constraint="uq_llm_assignments_user_purpose",
            set_={"llm_model_id": upsert.excluded.llm_model_id, "updated_at": func.now()},
        )
    )
    db.commit()
    query = owned_by(LlmAssignment, user_id).where(LlmAssignment.purpose == purpose)
    return db.scalars(query.execution_options(populate_existing=True)).one()


def unassign(db: Session, user_id: uuid.UUID, purpose: str) -> None:
    _check_purpose(purpose)
    assignment = db.scalar(owned_by(LlmAssignment, user_id).where(LlmAssignment.purpose == purpose))
    if assignment is None:
        raise AppError(404, "not_found", "这个用途还没有分配模型")
    db.delete(assignment)
    db.commit()


def list_assignments(db: Session, user_id: uuid.UUID) -> list[tuple[LlmAssignment, LlmModel, str]]:
    """每项为（分配，模型，服务名称），按用途排序。"""
    query = (
        owned_by(LlmAssignment, user_id)
        .add_columns(LlmModel, LlmProvider.name)
        .join(LlmModel, LlmModel.id == LlmAssignment.llm_model_id)
        .join(LlmProvider, LlmProvider.id == LlmModel.provider_id)
        .order_by(LlmAssignment.purpose)
    )
    return [(assignment, model, name) for assignment, model, name in db.execute(query)]
