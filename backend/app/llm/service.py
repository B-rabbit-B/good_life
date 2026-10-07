import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.config import get_settings
from app.db import get_sessionmaker
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


def _origin(url: str) -> tuple[str, str | None, int | None]:
    """（协议，主机，端口）；没写端口时按协议的默认端口算。地址已通过 validate_base_url，可以直接解析。"""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    return scheme, parts.hostname, parts.port or {"http": 80, "https": 443}.get(scheme)


def update_provider(db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, changes: dict[str, Any]) -> LlmProvider:
    """只能改名称、地址、密钥；服务类型不可改。密钥缺省保持原值。

    地址的协议、主机或端口变了时，必须在同一次修改里重新填写密钥，否则拒绝（llm_key_required_for_new_url）：
    防止拿到登录状态的人把地址改到自己的服务器，再借测试或拉取把已保存的密钥发过去。只改路径时保留原密钥。
    """
    provider = get_provider(db, user_id, provider_id)
    new_url = _check_url(changes["base_url"]) if "base_url" in changes else None
    if new_url is not None and "api_key" not in changes and _origin(new_url) != _origin(provider.base_url):
        raise AppError(422, "llm_key_required_for_new_url",
                       "服务地址的协议、主机或端口变了，为了不把已保存的密钥发到新地址，请在同一次修改里重新填写密钥；"
                       "只改地址里的路径时不需要重填。")
    if "name" in changes and changes["name"] != provider.name:
        if _name_taken(db, user_id, changes["name"], provider.id):
            raise _provider_exists()
        provider.name = changes["name"]
    if new_url is not None:
        provider.base_url = new_url
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
    skipped: int  # 超出上限或编号过长而没有收录的模型数
    models: list[LlmModel]  # 该服务下现有的全部模型（含手动添加的）


MAX_MODEL_ID_CHARS = 200
MAX_FETCHED_MODELS = 500


@dataclass(frozen=True)
class _Target:
    """调用服务所需的全部字段；先读出来再结束数据库事务，调用服务期间不占着事务。"""

    kind: str
    base_url: str
    api_key: str = field(repr=False)  # 不出现在 repr、日志与异常信息里


def _target(db: Session, provider: LlmProvider) -> _Target:
    """读取地址与密钥（只有这里访问延迟加载的密钥列），结束只读事务，再校验地址（域名解析也是网络操作）。"""
    kind, base_url, api_key = provider.kind, provider.base_url, provider.api_key
    db.commit()
    # 出站前再查一次地址，防止域名解析结果在保存后变成内网
    return _Target(kind=kind, base_url=_check_url(base_url), api_key=api_key)


def fetch_models(
    db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, factory: AdapterFactory
) -> FetchResult:
    """拉取模型列表并新增 source=fetched 的模型；已有模型（含手动添加的）与能力标注不动，列表里消失的模型也不删。

    每次最多收录排序后的前 500 个模型，其余计入 skipped。
    """
    provider = get_provider(db, user_id, provider_id)
    provider_pk = provider.id
    target = _target(db, provider)
    try:
        listed = factory(target.kind, target.base_url, target.api_key).list_models()
    except LlmError as exc:
        raise _app_error(exc, "list") from None
    eligible = [item for item in listed if 0 < len(item.model_id) <= MAX_MODEL_ID_CHARS][:MAX_FETCHED_MODELS]
    rows = [
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "provider_id": provider_pk,
            "model_id": item.model_id,
            "display_name": item.display_name[:200] if item.display_name else None,
            "source": "fetched",
        }
        for item in eligible
    ]
    added = 0
    if rows:
        insert = pg_insert(LlmModel).values(rows).on_conflict_do_nothing(constraint="uq_llm_models_provider_model")
        added = len(db.execute(insert.returning(LlmModel.id)).all())
    db.commit()
    return FetchResult(added=added, total=len(listed), skipped=len(listed) - len(eligible),
                       models=list_models(db, user_id, provider_pk))


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
    chat: StepReport | None  # 没有给模型编号，或拉取失败的原因不是 404 时，不做对话测试
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
# 结论 → 接口错误码；对话一步决定结论时，对话步骤的 code 与结论一致
_CONCLUSION_CODES = {
    "invalid_key": "llm_invalid_key",
    "bad_url": "llm_bad_url",
    "model_unavailable": "llm_model_unavailable",
    "quota_exceeded": "llm_quota_exceeded",
    "rate_limited": "llm_rate_limited",
    "timeout": "llm_timeout",
    "bad_request": "llm_bad_request",
    "provider_error": "llm_provider_error",
}
_MISSING = ("not_found", "model_not_found")
_CHAT_AFTER_LIST_ERRORS = ("not_found", "invalid_key")  # 拉取遇到这些错误时仍做对话测试


def _model_unavailable(model_id: str, exc: LlmError) -> tuple[str, str]:
    text = (f"模型 {model_id} 不存在或没有使用权限。请确认模型编号拼写正确、账户已开通这个模型；"
            "可以先点“获取模型”看看有哪些可用的模型。")
    return "model_unavailable", _with_detail(text, exc)


def _judge_chat(list_error: LlmError | None, chat_error: LlmError, model_id: str) -> tuple[str, str]:
    """对话失败时的结论（此时拉取要么成功，要么是 404）。

    Claude 在路径写错时对话也报 not_found_error（归为模型不存在），单看对话的错误码分不清是地址错还是模型错，
    所以“地址错误”要求两步都失败且 HTTP 状态都是 404：列表 404（not_found）加对话 404（not_found 或 model_not_found）。
    """
    if chat_error.code in _MISSING:
        if list_error is not None and list_error.status == 404 and chat_error.status == 404:
            return "bad_url", _with_detail(
                "拉取模型列表和对话都返回 404，多半是服务地址写错了（例如少了或多了 /v1），请对照服务商文档核对地址；"
                "如果地址确认无误，再检查模型编号是否正确。", chat_error)
        # 列表拉得到（或列表只是不支持），对话说模型不存在或 404，就是模型不可用
        return _model_unavailable(model_id, chat_error)
    return _CONCLUSIONS[chat_error.code], _describe(chat_error, "chat")[2]


def _run_test(adapter: Adapter, model_id: str | None) -> ConnectionReport:
    """步骤一拉取模型列表；步骤二（给了模型编号时）发一次最小对话，再按“关键决策”里的判定表给出结论。

    拉取 404 时靠对话区分“不支持拉取列表”（对话成功）与“地址错误”（对话也 404）；
    拉取报密钥错误时也做对话：有的密钥无权拉列表却能对话，对话成功给 ok_listing_unsupported，对话失败结论跟随拉取；
    其它拉取错误（额度、限流、超时、不可达、服务出错、请求被拒）结论跟随拉取，不再做对话。
    """
    listed = []
    list_error = chat_error = None
    try:
        listed = adapter.list_models()
    except LlmError as exc:
        list_error = exc
    chat_ran = model_id is not None and (list_error is None or list_error.code in _CHAT_AFTER_LIST_ERRORS)
    if chat_ran:
        try:
            adapter.chat(model_id, [ChatMessage("user", TEST_PROMPT)], max_tokens=TEST_MAX_TOKENS)
        except LlmError as exc:
            chat_error = exc

    if list_error is None:
        listing = StepReport(ok=True, code=None, message=f"拉取到 {len(listed)} 个模型")
    else:
        _status, code, text = _describe(list_error, "list")
        listing = StepReport(ok=False, code=code, message=text)
    chat = None
    if chat_error is not None and list_error is not None and list_error.code == "invalid_key":
        _status, code, text = _describe(chat_error, "chat")
        chat = StepReport(ok=False, code=code, message=text)
        conclusion, message = "invalid_key", listing.message
    elif chat_error is not None:
        conclusion, message = _judge_chat(list_error, chat_error, model_id)
        chat = StepReport(ok=False, code=_CONCLUSION_CODES[conclusion], message=message)
    elif chat_ran:
        chat = StepReport(ok=True, code=None, message=f"模型 {model_id} 对话成功")
        if list_error is None:
            conclusion, message = "ok", f"连接正常：拉取到 {len(listed)} 个模型，模型 {model_id} 对话成功。"
        elif list_error.code == "invalid_key":
            conclusion, message = "ok_listing_unsupported", (
                f"模型 {model_id} 对话成功，但当前密钥没有拉取模型列表的权限，请手动添加模型编号。")
        else:
            conclusion, message = "ok_listing_unsupported", (
                f"模型 {model_id} 对话成功，但该服务不支持拉取模型列表，请手动添加模型编号。")
    elif list_error is None:
        conclusion, message = "ok", f"连接正常，拉取到 {len(listed)} 个模型。建议再选一个模型测试对话，确认模型确实可以使用。"
    elif list_error.code == "not_found":
        conclusion, message = "bad_url", _with_detail(
            "拉取模型列表返回 404：可能是服务地址写错了（例如少了或多了 /v1），也可能这个服务不支持拉取模型列表。"
            "请核对服务地址，或填一个模型编号再测一次对话来确认。", list_error)
    else:
        conclusion, message = _CONCLUSIONS[list_error.code], listing.message
    return ConnectionReport(
        conclusion=conclusion,
        ok=conclusion in _OK_CONCLUSIONS,
        message=message,
        listing=listing,
        chat=chat,
        models_found=None if list_error else len(listed),
        sample_models=[item.model_id for item in listed[:SAMPLE_MODELS]],
    )


def check_connection(
    kind: str, base_url: str, api_key: str, model_id: str | None, factory: AdapterFactory
) -> ConnectionReport:
    """测试还没保存的服务；地址不合格时直接抛 llm_invalid_url，不发任何请求。"""
    return _run_test(factory(kind, _check_url(base_url), api_key), model_id)


def check_saved_provider(
    db: Session, user_id: uuid.UUID, provider_id: uuid.UUID, model_id: str | None, factory: AdapterFactory
) -> ConnectionReport:
    target = _target(db, get_provider(db, user_id, provider_id))
    return _run_test(factory(target.kind, target.base_url, target.api_key), model_id)


@dataclass(frozen=True)
class CompletionResult:
    result: ChatResult
    provider_name: str
    model_pk: uuid.UUID
    model_id: str


MAX_IMAGES_PER_REQUEST = 8
MAX_IMAGE_BYTES_PER_REQUEST = 20 * 1024 * 1024


def _decoded_size(data_base64: str) -> int:
    """合法 base64 解码后的字节数（不必真的解码）。"""
    return len(data_base64) * 3 // 4 - data_base64[-2:].count("=")


def _check_images(messages: Sequence[ChatMessage]) -> None:
    """只有用户消息可以带图片（适配器不会静默丢图）；一次最多 8 张、解码后合计不超过 20 MB。"""
    if any(m.images and m.role != "user" for m in messages):
        raise AppError(422, "llm_invalid_images", "只有用户消息可以附带图片，系统消息与助手消息不能带图片，请调整后再试。")
    images = [image for m in messages for image in m.images]
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise AppError(422, "llm_invalid_images",
                       f"一次最多发送 {MAX_IMAGES_PER_REQUEST} 张图片，这次有 {len(images)} 张，请减少图片后再试。")
    if sum(_decoded_size(image.data_base64) for image in images) > MAX_IMAGE_BYTES_PER_REQUEST:
        raise AppError(422, "llm_invalid_images", "这次发送的图片合计超过 20 MB，请压缩图片或减少图片数量后再试。")


def complete(
    user_id: uuid.UUID,
    purpose: str,
    messages: Sequence[ChatMessage],
    *,
    tools: Sequence[ToolSpec] = (),
    max_tokens: int = 1024,
    factory: AdapterFactory,
) -> CompletionResult:
    """统一调用入口：按用途找到分配的模型，调用前再查一遍能力，最后才读取密钥并调用服务。

    complete 不接收调用方的数据库会话，而是自己开一个短会话：分配、能力、地址与密钥都在里面读取（同样按 user_id 过滤），
    读完就关闭，调用服务期间不占任何事务。调用方也不要在调用 complete 时开着自己的事务，
    以免调用服务期间（最长约 20 秒）一直占着数据库连接。
    """
    _check_purpose(purpose)
    _check_images(messages)
    query = (
        owned_by(LlmAssignment, user_id)
        .add_columns(LlmModel, LlmProvider)
        .join(LlmModel, LlmModel.id == LlmAssignment.llm_model_id)
        .join(LlmProvider, LlmProvider.id == LlmModel.provider_id)
        .where(LlmAssignment.purpose == purpose)
    )
    label = PURPOSE_LABELS[purpose]
    with get_sessionmaker()() as session:
        row = session.execute(query).first()
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
        model_pk, model_id, provider_name = model.id, model.model_id, provider.name
        kind, base_url = provider.kind, provider.base_url
        api_key = provider.api_key  # 只有到这一步才读取（解密）密钥
    base_url = _check_url(base_url)  # 出站前再查一次地址；此时短会话已关闭
    try:
        result = factory(kind, base_url, api_key).chat(model_id, messages, tools=tools, max_tokens=max_tokens)
    except LlmError as exc:
        raise _app_error(exc, "chat") from None
    return CompletionResult(result=result, provider_name=provider_name, model_pk=model_pk, model_id=model_id)
