import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.config import get_settings
from app.errors import AppError
from app.llm.adapters import make_adapter
from app.llm.adapters.base import Adapter, ChatMessage, ChatResult, LlmError, ToolSpec
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


# ---------- 调用模型服务：拉取模型、连通性测试、统一调用入口 ----------

AdapterFactory = Callable[[str, str, str], Adapter]  # （服务类型，地址，密钥）→ 适配器


def default_adapter_factory(kind: str, base_url: str, api_key: str) -> Adapter:
    return make_adapter(kind, base_url, api_key, timeout=get_settings().llm_timeout_seconds)


def get_adapter_factory() -> AdapterFactory:
    """接口依赖；测试覆盖它，注入基于 MockTransport 的适配器。"""
    return default_adapter_factory


# 适配器错误码 → （接口状态码，接口错误码）
LLM_ERRORS: dict[str, tuple[int, str]] = {
    "invalid_key": (400, "llm_invalid_key"),
    "unreachable": (400, "llm_bad_url"),
    "not_found": (400, "llm_listing_unsupported_or_bad_url"),
    "model_not_found": (400, "llm_model_unavailable"),
    "quota_exceeded": (402, "llm_quota_exceeded"),
    "rate_limited": (429, "llm_rate_limited"),
    "timeout": (504, "llm_timeout"),
    "bad_request": (400, "llm_bad_request"),
    "provider_error": (502, "llm_provider_error"),
}
_NEXT_STEPS = {
    "invalid_key": "请检查密钥是否复制完整、是否属于这个服务，以及账户是否开通了相应权限。",
    "unreachable": "请检查服务地址是否拼写正确、本机网络能否访问这个服务。",
    "not_found": "这个服务可能不提供模型列表接口，也可能是服务地址写错了（例如少了或多了 /v1）；"
                 "请核对服务地址，或直接手动添加模型编号。",
    "model_not_found": "请确认模型编号拼写正确、账户已开通这个模型；可以先点“获取模型”看看有哪些可用的模型。",
    "quota_exceeded": "请到服务商的控制台查看余额或额度，充值或提升额度后再试。",
    "rate_limited": "请稍等一会儿再试；如果经常出现，请到服务商的控制台提高调用频率上限。",
    "timeout": "请检查网络后重试；服务繁忙时也可以稍后再试。",
    "bad_request": "请检查模型编号与提问内容；如果一直出现，请换一个模型试试。",
    "provider_error": "这通常是服务商那边的临时问题，请稍后再试，或换一个模型。",
}
# 对话时遇到与模型无关的 404，说明对话接口的地址不对，而不是“不支持拉取模型列表”
_CHAT_NOT_FOUND = (400, "llm_bad_url", "请核对服务地址（例如是否少了或多了 /v1），也请确认模型编号正确。")


def _with_detail(text: str, exc: LlmError) -> str:
    """附上服务返回的原始信息；detail 在适配器里已经去掉密钥并截断。"""
    return f"{text}（原始信息：{exc.detail}）" if exc.detail else text


def _describe(exc: LlmError, during: str) -> tuple[int, str, str]:
    """把适配器错误转成（接口状态码，接口错误码，中文说明与下一步建议）。"""
    if during == "chat" and exc.code == "not_found":
        status, code, next_step = _CHAT_NOT_FOUND
    else:
        (status, code), next_step = LLM_ERRORS[exc.code], _NEXT_STEPS[exc.code]
    return status, code, _with_detail(f"{exc.message.rstrip('。')}。{next_step}", exc)


def _app_error(exc: LlmError, during: str) -> AppError:
    return AppError(*_describe(exc, during))


@dataclass(frozen=True)
class FetchResult:
    added: int  # 本次新增的模型数
    total: int  # 服务这次返回的模型数
    models: list[LlmModel]  # 该服务下现有的全部模型（含手动添加的）


MAX_MODEL_ID_CHARS = 200


def fetch_models(
    db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, factory: AdapterFactory
) -> FetchResult:
    """拉取模型列表并新增 source=fetched 的模型；已有模型（含手动添加的）与能力标注不动，列表里消失的模型也不删。"""
    provider = get_provider(db, user_id, provider_id)
    base_url = _check_url(provider.base_url)  # 出站前再查一次，防止域名解析结果在保存后变成内网
    try:
        listed = factory(provider.kind, base_url, provider.api_key).list_models()
    except LlmError as exc:
        raise _app_error(exc, "list") from None
    rows = [
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "provider_id": provider.id,
            "model_id": item.model_id,
            "display_name": item.display_name[:200] if item.display_name else None,
            "source": "fetched",
        }
        for item in listed
        if 0 < len(item.model_id) <= MAX_MODEL_ID_CHARS
    ]
    added = 0
    if rows:
        insert = pg_insert(LlmModel).values(rows).on_conflict_do_nothing(constraint="uq_llm_models_provider_model")
        added = len(db.execute(insert.returning(LlmModel.id)).all())
    db.commit()
    return FetchResult(added=added, total=len(listed), models=list_models(db, user_id, provider.id))


@dataclass(frozen=True)
class StepReport:
    ok: bool
    code: str | None  # 失败时为接口错误码（llm_ 开头）
    message: str


@dataclass(frozen=True)
class ConnectionReport:
    conclusion: str
    ok: bool
    message: str
    listing: StepReport
    chat: StepReport | None  # 没有给模型编号，或拉取时就连不上服务时，不做对话测试
    models_found: int | None
    sample_models: list[str]


TEST_PROMPT = "请只回复：好"
TEST_MAX_TOKENS = 16
SAMPLE_MODELS = 10
_OK_CONCLUSIONS = ("ok", "ok_listing_unsupported")
_CONCLUSIONS = {
    "invalid_key": "invalid_key",
    "unreachable": "bad_url",
    "not_found": "bad_url",
    "model_not_found": "model_unavailable",
    "quota_exceeded": "quota_exceeded",
    "rate_limited": "rate_limited",
    "timeout": "timeout",
    "bad_request": "bad_request",
    "provider_error": "provider_error",
}
_MISSING = ("not_found", "model_not_found")


def _from_error(exc: LlmError, during: str) -> tuple[str, str]:
    return _CONCLUSIONS[exc.code], _describe(exc, during)[2]


def _model_unavailable(model_id: str, exc: LlmError) -> tuple[str, str]:
    text = (f"模型 {model_id} 不存在或没有使用权限。请确认模型编号拼写正确、账户已开通这个模型；"
            "可以先点“获取模型”看看有哪些可用的模型。")
    return "model_unavailable", _with_detail(text, exc)


def _judge(
    list_error: LlmError | None, chat_error: LlmError | None, model_id: str | None, chat_ran: bool, count: int
) -> tuple[str, str]:
    """按“关键决策”里的判定表给出结论与说明。

    Claude 在路径写错时对话也报 not_found_error（归为模型不存在），单看对话的错误码分不清是地址错还是模型错，
    所以“地址错误”要求两步都失败且 HTTP 状态都是 404：列表 404（not_found）加对话 404（not_found 或 model_not_found）。
    """
    if list_error is None:
        if not chat_ran:
            return "ok", f"连接正常，拉取到 {count} 个模型。建议再选一个模型测试对话，确认模型确实可以使用。"
        if chat_error is None:
            return "ok", f"连接正常：拉取到 {count} 个模型，模型 {model_id} 对话成功。"
        if chat_error.code in _MISSING:  # 列表拉得到，说明地址与密钥没问题；对话说不存在或 404 就是模型不可用
            return _model_unavailable(model_id, chat_error)
        return _from_error(chat_error, "chat")
    if not chat_ran:
        if list_error.code == "not_found":
            return "bad_url", _with_detail(
                "拉取模型列表返回 404：可能是服务地址写错了（例如少了或多了 /v1），也可能这个服务不支持拉取模型列表。"
                "请核对服务地址，或填一个模型编号再测一次对话来确认。", list_error)
        return _from_error(list_error, "list")
    if chat_error is None:
        return "ok_listing_unsupported", (
            f"模型 {model_id} 对话成功，但该服务不支持拉取模型列表（或当前密钥无权拉取），请手动添加模型编号。")
    if chat_error.code in _MISSING:
        if list_error.status == 404 and chat_error.status == 404:
            return "bad_url", _with_detail(
                "拉取模型列表和对话都返回 404，多半是服务地址写错了（例如少了或多了 /v1），请对照服务商文档核对地址；"
                "如果地址确认无误，再检查模型编号是否正确。", chat_error)
        return _model_unavailable(model_id, chat_error)
    return _from_error(chat_error, "chat")


def _failed_step(exc: LlmError, during: str) -> StepReport:
    _status, code, message = _describe(exc, during)
    return StepReport(ok=False, code=code, message=message)


def _run_test(adapter: Adapter, model_id: str | None) -> ConnectionReport:
    """步骤一拉取模型列表；步骤二（给了模型编号时）发一次最小对话。拉取时就连不上服务的，不再白等一次对话。"""
    listed = []
    list_error = chat_error = None
    try:
        listed = adapter.list_models()
    except LlmError as exc:
        list_error = exc
    chat_ran = model_id is not None and not (list_error is not None and list_error.code in ("unreachable", "timeout"))
    if chat_ran:
        try:
            adapter.chat(model_id, [ChatMessage("user", TEST_PROMPT)], max_tokens=TEST_MAX_TOKENS)
        except LlmError as exc:
            chat_error = exc
    conclusion, message = _judge(list_error, chat_error, model_id, chat_ran, len(listed))
    if list_error is None:
        listing = StepReport(ok=True, code=None, message=f"拉取到 {len(listed)} 个模型")
    else:
        listing = _failed_step(list_error, "list")
    chat = None
    if chat_ran:
        if chat_error is None:
            chat = StepReport(ok=True, code=None, message=f"模型 {model_id} 对话成功")
        else:
            chat = _failed_step(chat_error, "chat")
    return ConnectionReport(
        conclusion=conclusion,
        ok=conclusion in _OK_CONCLUSIONS,
        message=message,
        listing=listing,
        chat=chat,
        models_found=None if list_error else len(listed),
        sample_models=[item.model_id for item in listed[:SAMPLE_MODELS]],
    )


def test_connection(
    kind: str, base_url: str, api_key: str, model_id: str | None, factory: AdapterFactory
) -> ConnectionReport:
    """测试还没保存的服务；地址不合格时直接抛 llm_invalid_url，不发任何请求。"""
    return _run_test(factory(kind, _check_url(base_url), api_key), model_id)


def test_saved_provider(
    db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, model_id: str | None, factory: AdapterFactory
) -> ConnectionReport:
    provider = get_provider(db, user_id, provider_id)
    base_url = _check_url(provider.base_url)
    return _run_test(factory(provider.kind, base_url, provider.api_key), model_id)


@dataclass(frozen=True)
class CompletionResult:
    result: ChatResult
    provider_name: str
    model_pk: uuid.UUID
    model_id: str


def complete(
    db: Session,
    user_id: uuid.UUID,
    purpose: str,
    messages: Sequence[ChatMessage],
    *,
    tools: Sequence[ToolSpec] = (),
    max_tokens: int = 1024,
    factory: AdapterFactory,
) -> CompletionResult:
    """统一调用入口：按用途找到分配的模型，调用前再查一遍能力，最后才读取密钥并调用服务。"""
    _check_purpose(purpose)
    query = (
        owned_by(LlmAssignment, user_id)
        .add_columns(LlmModel, LlmProvider)
        .join(LlmModel, LlmModel.id == LlmAssignment.llm_model_id)
        .join(LlmProvider, LlmProvider.id == LlmModel.provider_id)
        .where(LlmAssignment.purpose == purpose)
    )
    row = db.execute(query).first()
    label = PURPOSE_LABELS[purpose]
    if row is None:
        raise AppError(409, "llm_not_configured",
                       f"还没有为“{label}”选择模型：请先到设置页的“模型服务”里，为“日常对话”或“看图识别”选择一个模型，再来使用。")
    _assignment, model, provider = row
    caps = model_capabilities(model)[0]
    if caps.vision is not True and (purpose == "vision" or any(m.images for m in messages)):
        raise AppError(422, "llm_model_lacks_vision",
                       f"当前模型 {model.model_id} 不支持看图（对照表标明不支持，或无法确认）。请到设置页换一个支持看图的模型；"
                       "如果你确认它能看图，可以在模型上手动标注“支持看图”；也可以不传图片，改为手动填写。")
    if tools and caps.tools is False:
        raise AppError(422, "llm_model_lacks_tools",
                       f"当前模型 {model.model_id} 被标明不支持工具调用。请到设置页换一个支持工具调用的模型，"
                       "或在模型上手动标注“支持工具调用”。")
    if caps.chat is False:
        raise AppError(422, "llm_model_not_chat",
                       f"当前模型 {model.model_id} 被标明不是对话模型（例如向量、语音、绘图模型），不能用于“{label}”。"
                       "请到设置页换一个对话模型，或在模型上手动标注“支持对话”。")
    base_url = _check_url(provider.base_url)
    adapter = factory(provider.kind, base_url, provider.api_key)  # 只有到这一步才读取（解密）密钥
    try:
        result = adapter.chat(model.model_id, messages, tools=tools, max_tokens=max_tokens)
    except LlmError as exc:
        raise _app_error(exc, "chat") from None
    return CompletionResult(result=result, provider_name=provider.name, model_pk=model.id, model_id=model.model_id)
