"""导出我的数据：在内存里生成一个压缩包，每个模块一份 JSON、医嘱原件与保留的照片各放一个文件夹、一份中文说明。

- 各模块的内容一律用对应读取接口的同名响应模型、经同一个组装函数序列化（与接口逐项一致，tests/test_account_export.py
  逐项比对）；接口有条数上限的部分（档案修改记录、医嘱事件、识别记录、调用审计）这里导出全部。
- 接口没有的部分：对话的全部消息（含工具调用与工具结果，去掉 provider_state）、开场记录、全部免责确认记录。
- 不导出密码哈希、令牌版本号、授权令牌的哈希与模型服务的密钥原文（ProviderOut 只有 key_hint）；只查本人的数据。
- 原件放在 evidence/<证据编号>.<扩展名>，保留的照片放在 photos/<识别编号>.jpg，原始文件名只写在 medical.json。
- 读医嘱前按接口的做法先刷新到期状态（refresh_statuses），导出里的状态与界面看到的一致。
- 原件与照片合计超过 MAX_EXPORT_FILE_BYTES 时先拒绝（413 export_too_large），不读任何文件内容：
  整个压缩包在内存里生成，峰值约为文件总量的三倍。
"""

import io
import json
import uuid
import zipfile
from datetime import date, datetime
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import func
from sqlalchemy.orm import Session, undefer

from app.agent import conversations as agent_conversations
from app.agent import preferences as agent_preferences
from app.agent.models import AgentMessage, AgentOpening, AgentSettings
from app.agent.router import _visible_messages
from app.agent.schemas import ConversationDetailOut, ConversationOut, PreferenceOut, SettingsOut
from app.agent_grants.models import AgentGrant, SdkCallAudit
from app.agent_grants.router import _out as _grant_out
from app.agent_grants.schemas import AuditOut
from app.auth.models import User
from app.auth.schemas import UserOut
from app.common.ownership import owned_by
from app.consents import service as consents_service
from app.cycle import records as cycle_records
from app.cycle.models import CycleDayLog, CycleSettings
from app.cycle.schemas import CycleSettingsOut, DayLogOut, PeriodOut
from app.disclaimer.content import DISCLAIMER_VERSION
from app.disclaimer.models import DisclaimerAcceptance
from app.disclaimer.router import DisclaimerStatus
from app.errors import AppError
from app.fitness import workouts as fitness_workouts
from app.fitness.models import Workout
from app.fitness.router import _exercise_detail, _workouts_out
from app.llm import service as llm_service
from app.llm.router import _assignment_out, _model_out
from app.llm.schemas import ProviderOut
from app.medical import items as medical_items
from app.medical import orders as medical_orders
from app.medical.models import MedicalEvidence, MedicalItem, MedicalItemEvent
from app.medical.router import _order_out
from app.medical.schemas import EventOut, ItemOut, MedicalEventOut
from app.nutrition.meals import MEAL_TYPES
from app.nutrition.models import MealEntry
from app.nutrition.router import _meal_out
from app.photos.models import PhotoRecognition
from app.photos.router import _out as _recognition_out
from app.profile.models import Profile, ProfileChange
from app.profile.schemas import ProfileChangeOut, ProfileOut
from app.restaurants.models import RestaurantSettings
from app.restaurants.router import _settings_out

EXPORT_FILES = (
    "account.json",
    "profile.json",
    "cycle.json",
    "medical.json",
    "nutrition.json",
    "fitness.json",
    "conversations.json",
    "preferences_and_openings.json",
    "photos.json",
    "llm.json",
    "agent_grants.json",
    "restaurants.json",
    "disclaimer_and_consents.json",
)
README_NAME = "说明.txt"
EVIDENCE_DIR = "evidence"
PHOTO_DIR = "photos"
HIDDEN_MESSAGE_KEYS = ("provider_state",)
MAX_EXPORT_FILE_BYTES = 200 * 1024 * 1024  # 原件与保留照片的原始字节合计上限
# 照片没有存大小，按 Fernet 密文长度推算原始大小：base64 解码后减去版本、时间戳、初始向量、签名与至少 1 字节的补位，
# 结果不小于原始大小，最多多算 17 字节
_FERNET_OVERHEAD = 58

README_TEXT = f"""好生活 数据导出说明

这个压缩包是你在“好生活”里保存的全部数据，在你重新输入密码后当场生成，只含你本人的数据。
每个 .json 文件都是 UTF-8 编码的 JSON，可以用任何文本编辑器打开；时间带时区，日期写成“年-月-日”，编号是程序生成的随机编号。
各模块的内容与 App 里对应页面读到的一致；App 里只显示最近若干条的部分（档案修改记录、医嘱事件、调用审计），这里是全部。

密钥只含掩码：模型服务只导出 key_hint（密钥末尾几位的掩码），不含密钥原文。
不含密码与授权令牌：不导出登录密码的哈希、登录令牌，也不导出智能体授权令牌及其哈希。
对话里可能有其他模块数据的副本：你在对话里提到的、或智能体调用工具读到的经期、医嘱、饮食等内容会作为对话的一部分保存，删除单条记录或撤回同意不会删掉对话里的副本。

各文件的内容：

account.json：账号。id 是账号编号，username 是用户名，created_at 是注册时间。
profile.json：档案。profile 是当前档案（gender 性别、birth_year 出生年份、height_cm 身高厘米、weight_kg 体重千克、activity_level 活动水平、goal 目标、diet_preferences 饮食偏好、food_avoidances 忌口、health_conditions 健康情况、notes 备注、cycle_tracking_opt_out 是否关闭经期记录）；changes 是全部修改记录，新的在前，每条的 changes 写出每个字段的 old 旧值与 new 新值。
cycle.json：经期。periods 是经期记录（start_date 开始、end_date 结束）；day_logs 是每日记录（log_date 日期、flow 流量、pain 疼痛 0 至 3、mood 情绪、symptoms 症状、note 备注）；settings 是经期状态（status：tracking 记录中、pregnant 孕期、paused 暂停）。
medical.json：医嘱。orders 是医嘱单（source_text 原文、order_date 日期、items 从中整理出的条目、evidence 上传的原件清单，filename 是原件的原始文件名）；items 是全部条目（category 类别、status 状态、content 内容、subjects 涉及的食物或动作、start_date 开始、end_date 预计结束、review_date 复查日）；events 是全部条目的状态变化记录（action 动作、from_status 原状态、to_status 新状态、source 来源、detail 说明）。
nutrition.json：饮食。meals 是全部饮食记录（eaten_on 日期、meal_type 餐次、food_name 食物、grams 克数、nutrients 按克数算出的营养、note 备注）。
fitness.json：训练。workouts 是全部训练（performed_on 日期、strength 力量动作与每一组、cardio 有氧、conflicts 与今天生效的运动限制医嘱的冲突提示）；custom_exercises 是你自己添加的动作。
conversations.json：与智能体的对话。conversations 里每段对话有 messages（App 里看得到的用户与助手消息）与 transcript（全部消息，含智能体的工具调用 tool_calls 与工具结果 role 为 tool 的消息；position 是消息在对话里的顺序）。
preferences_and_openings.json：偏好记忆与主动开场。preferences 是偏好（source：user 你自己添加、agent 智能体记下）；settings 是智能体设置（openings_enabled 是否主动开场）；openings 是智能体每天主动问过的问题（day 日期、kind 类别、status：asked 已问、declined 已拒绝、answered 已回答、question 问题原文）。
photos.json：拍照识别。recognitions 是全部识别记录（status 草稿、已确认或已放弃，items 识别出的菜品与份量，image_kept 是否保留了图片）。
llm.json：模型服务。providers 是你配置的服务（key_hint 是密钥掩码），models 是各服务下的模型，assignments 是“日常对话”“看图识别”等用途选用的模型。
agent_grants.json：智能体授权与调用审计。grants 是你签发过的授权（access 读写级别、status 状态、expires_at 到期时间）；audits 是全部调用审计（capability 调用的能力、outcome 结果、error_code 错误码、client_name 客户端名称），不含参数与返回内容。
restaurants.json：附近餐厅设置。settings 里 location_consent 是定位授权状态，area 是你选择记住的大致区域（只有区域名称与保存时间）。
disclaimer_and_consents.json：免责声明与单独同意。disclaimer 是当前版本免责声明的确认状态，disclaimer_acceptances 是全部确认记录（version 版本、accepted_at 确认时间）；consents 是经期与医嘱两项单独同意（granted 是否同意、granted_at 同意时间、granted_version 同意的文案版本、withdrawn_at 撤回时间）。

文件夹：
{EVIDENCE_DIR}/：医嘱原件，文件名是“证据编号.扩展名”，原始文件名写在 medical.json 的 evidence 里。
{PHOTO_DIR}/：选择了保留的餐食照片（处理后的 JPEG），文件名是“识别编号.jpg”。
"""


def _profile(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    profile = db.scalar(owned_by(Profile, user_id))
    changes = db.scalars(owned_by(ProfileChange, user_id)
                         .order_by(ProfileChange.changed_at.desc(), ProfileChange.seq.desc()))
    return {"profile": ProfileOut.model_validate(profile) if profile else None,
            "changes": [ProfileChangeOut.model_validate(change) for change in changes]}


def _cycle(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    settings = db.scalar(owned_by(CycleSettings, user_id))
    return {
        "periods": [PeriodOut.model_validate(period) for period in cycle_records.list_periods(db, user_id)],
        "day_logs": [DayLogOut.from_record(log)
                     for log in db.scalars(owned_by(CycleDayLog, user_id).order_by(CycleDayLog.log_date))],
        "settings": CycleSettingsOut.model_validate(settings) if settings else None,
    }


def _medical(db: Session, user_id: uuid.UUID, today: date) -> dict[str, Any]:
    medical_items.refresh_statuses(db, user_id, today)
    events = db.execute(
        owned_by(MedicalItemEvent, user_id)
        .add_columns(MedicalItem)
        .join(MedicalItem, (MedicalItem.id == MedicalItemEvent.item_id) & (MedicalItem.user_id == user_id))
        .order_by(MedicalItemEvent.occurred_at.desc(), MedicalItemEvent.seq.desc())
    )
    return {
        "orders": [_order_out(db, user_id, order) for order in medical_orders.list_orders(db, user_id)],
        "items": [ItemOut.model_validate(item) for item in medical_items.list_items(db, user_id)],
        "events": [MedicalEventOut(**EventOut.model_validate(event).model_dump(), item_id=item.id,
                                   item_category=item.category, item_content=item.content)
                   for event, item in events],
    }


def _nutrition(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    entries = db.scalars(owned_by(MealEntry, user_id)).all()
    ordered = sorted(entries, key=lambda e: (e.eaten_on, MEAL_TYPES.index(e.meal_type), e.created_at, str(e.id)))
    return {"meals": [_meal_out(entry) for entry in ordered]}


def _fitness(db: Session, user: User, today: date) -> dict[str, Any]:
    found = list(db.scalars(owned_by(Workout, user.id)
                            .order_by(Workout.performed_on.desc(), Workout.created_at.desc(), Workout.id)))
    return {"workouts": _workouts_out(db, user, today, found),
            "custom_exercises": [_exercise_detail(e) for e in fitness_workouts.user_custom_exercises(db, user.id)]}


def _transcript(message: AgentMessage) -> dict[str, Any]:
    content = {key: value for key, value in message.content.items() if key not in HIDDEN_MESSAGE_KEYS}
    if "tool_calls" in content:
        content["tool_calls"] = [{key: value for key, value in call.items() if key not in HIDDEN_MESSAGE_KEYS}
                                 for call in content["tool_calls"] or []]
    return {"id": message.id, "position": message.position, "role": message.role,
            "created_at": message.created_at, **content}


def _conversations(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    out = []
    for conversation in agent_conversations.list_conversations(db, user_id):
        detail = ConversationDetailOut(**ConversationOut.model_validate(conversation).model_dump(),
                                       messages=_visible_messages(db, user_id, conversation.id))
        transcript = [_transcript(m) for m in agent_conversations.messages(db, user_id, conversation.id)]
        out.append({**detail.model_dump(), "transcript": transcript})
    return {"conversations": out}


def _preferences_and_openings(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    settings = db.scalar(owned_by(AgentSettings, user_id))
    openings = db.scalars(owned_by(AgentOpening, user_id).order_by(AgentOpening.created_at, AgentOpening.id))
    return {
        "preferences": [PreferenceOut.model_validate(p) for p in agent_preferences.list_preferences(db, user_id)],
        "settings": SettingsOut.model_validate(settings) if settings else None,
        "openings": [{"id": o.id, "day": o.day, "kind": o.kind, "status": o.status, "question": o.question,
                      "created_at": o.created_at} for o in openings],
    }


def _photos(db: Session, user_id: uuid.UUID, today: date) -> dict[str, Any]:
    records = db.scalars(owned_by(PhotoRecognition, user_id)
                         .order_by(PhotoRecognition.created_at.desc(), PhotoRecognition.id.desc()))
    return {"recognitions": [_recognition_out(db, user_id, record, today) for record in records]}


def _llm(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    providers = llm_service.list_providers(db, user_id)
    return {
        "providers": [ProviderOut.model_validate(provider) for provider in providers],
        "models": [_model_out(model) for provider in providers
                   for model in llm_service.list_models(db, user_id, provider.id)],
        "assignments": [_assignment_out(*item) for item in llm_service.list_assignments(db, user_id)],
    }


def _agent_grants(db: Session, user_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    grants = db.scalars(owned_by(AgentGrant, user_id).order_by(AgentGrant.created_at.desc(), AgentGrant.id))
    audits = db.scalars(owned_by(SdkCallAudit, user_id).order_by(SdkCallAudit.created_at.desc(), SdkCallAudit.id))
    return {"grants": [_grant_out(grant, now) for grant in grants],
            "audits": [AuditOut.model_validate(audit) for audit in audits]}


def _restaurants(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    settings = db.scalar(owned_by(RestaurantSettings, user_id))
    return {"settings": _settings_out(settings) if settings else None}


def _disclaimer_and_consents(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    acceptances = list(db.scalars(owned_by(DisclaimerAcceptance, user_id)
                                  .order_by(DisclaimerAcceptance.accepted_at, DisclaimerAcceptance.id)))
    current = next((a for a in acceptances if a.version == DISCLAIMER_VERSION), None)
    return {
        "disclaimer": DisclaimerStatus(current_version=DISCLAIMER_VERSION, accepted=current is not None,
                                       accepted_at=current.accepted_at if current else None),
        "disclaimer_acceptances": [{"version": a.version, "accepted_at": a.accepted_at} for a in acceptances],
        "consents": consents_service.list_statuses(db, user_id),
    }


def _files(db: Session, user_id: uuid.UUID) -> list[tuple[str, bytes]]:
    """原件与保留的照片，条目名只由程序生成的编号与扩展名组成。"""
    evidence = db.scalars(owned_by(MedicalEvidence, user_id).options(undefer(MedicalEvidence.content))
                          .order_by(MedicalEvidence.created_at, MedicalEvidence.id))
    files = [(f"{EVIDENCE_DIR}/{e.id}{medical_orders.EVIDENCE_EXTENSIONS[e.content_type]}", e.content)
             for e in evidence]
    photos = db.scalars(owned_by(PhotoRecognition, user_id).options(undefer(PhotoRecognition.image))
                        .where(PhotoRecognition.image_kept.is_(True))
                        .order_by(PhotoRecognition.created_at, PhotoRecognition.id))
    files += [(f"{PHOTO_DIR}/{p.id}.jpg", p.image) for p in photos if p.image is not None]
    return files


def _file_bytes(db: Session, user_id: uuid.UUID) -> int:
    """原件与保留照片的原始字节合计，只在数据库里求和，不读文件内容。"""
    evidence = db.scalar(owned_by(MedicalEvidence, user_id)
                         .with_only_columns(func.coalesce(func.sum(MedicalEvidence.size_bytes), 0)))
    photos = db.scalar(owned_by(PhotoRecognition, user_id)
                       .with_only_columns(func.coalesce(
                           func.sum(func.octet_length(PhotoRecognition.image) * 3 / 4 - _FERNET_OVERHEAD), 0))
                       .where(PhotoRecognition.image_kept.is_(True), PhotoRecognition.image.is_not(None)))
    return int(evidence) + int(photos)


def _encode(content: Any) -> bytes:
    return json.dumps(to_jsonable_python(content), ensure_ascii=False, indent=2).encode("utf-8")


def build_export(db: Session, user: User, now: datetime, *, today: date | None = None) -> tuple[str, bytes]:
    """返回（文件名 good-life-export-年月日.zip，压缩包字节）。全部在内存里完成，不写任何临时文件。

    today 是路由取的“今天”（get_today），用于医嘱到期刷新、训练的冲突提示与草稿识别的评价；不传时取 now 的本地日期。
    """
    today = today or now.astimezone().date()
    user_id = user.id
    if _file_bytes(db, user_id) > MAX_EXPORT_FILE_BYTES:
        raise AppError(413, "export_too_large",
                       f"医嘱原件与保留的餐食照片合计超过 {MAX_EXPORT_FILE_BYTES // (1024 * 1024)} MB，无法一次导出；"
                       "请先删除部分医嘱原件或不需要的餐食照片后再试")
    contents: dict[str, Any] = {
        "account.json": UserOut.model_validate(user),
        "profile.json": _profile(db, user_id),
        "cycle.json": _cycle(db, user_id),
        "medical.json": _medical(db, user_id, today),
        "nutrition.json": _nutrition(db, user_id),
        "fitness.json": _fitness(db, user, today),
        "conversations.json": _conversations(db, user_id),
        "preferences_and_openings.json": _preferences_and_openings(db, user_id),
        "photos.json": _photos(db, user_id, today),
        "llm.json": _llm(db, user_id),
        "agent_grants.json": _agent_grants(db, user_id, now),
        "restaurants.json": _restaurants(db, user_id),
        "disclaimer_and_consents.json": _disclaimer_and_consents(db, user_id),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, _encode(content))
        archive.writestr(README_NAME, README_TEXT.encode("utf-8"))
        for name, data in _files(db, user_id):
            archive.writestr(name, data)
    return f"good-life-export-{today:%Y%m%d}.zip", buffer.getvalue()
