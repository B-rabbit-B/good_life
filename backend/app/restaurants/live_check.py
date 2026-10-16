"""附近餐厅实测脚本：用户在本机用服务端配置的真实高德密钥把验证场景跑一遍，结果写到 restaurant_live_result.md。

运行方式（在 backend 目录，数据库在运行且已建表）：uv run python -m app.restaurants.live_check
高德配置与正式服务相同，来自 backend/.env 的 AMAP_KEY、AMAP_BASE_URL、AMAP_TIMEOUT_SECONDS；没有配置密钥时给出说明并退出。
脚本不打印密钥，结果文件与屏幕输出都按密钥脱敏。

脚本在开发库里建立 3 个临时用户（普通、忌辛辣医嘱已确认、减脂目标），用户名形如 live_1a2b3c4d_ordinary
（live_ 加 8 位十六进制随机编号再加下划线，后面是用户类别），用正式的检索流程（service.search 与真实的
get_amap_client）依次检索：北京国贸、上海人民广场、成都春熙路三个手动地点，每个地点三类用户各一次；再用公开地标的
GPS 坐标检索一次（并记住大致区域，验证逆地理只得到区县名称）；再带一句话需求检索一次。每个场景记录中心、需求、
前 10 家（名称、类型、距离、结论、评分，以及高德原始的类别编码与类别名称，用来核对类型表里凭记忆写的编码）、
被避开的类型与原因、各类型的到店建议与耗时。不论成功、失败还是被中断，最后都按用户名前缀删除这些用户
（设置、医嘱随之级联删除）。自动化测试用模拟高德驱动本模块，绝不访问真实网络。
"""

import secrets
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.auth.models import User
from app.auth.service import register_user
from app.consents import service as consents_service
from app.consents.content import CONSENT_KINDS, CONSENT_VERSION
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.errors import AppError
from app.llm.live_check import scrub
from app.medical import items, orders
from app.nutrition.engine import SOURCE_NAMES
from app.profile.service import update_profile
from app.restaurants import amap, service
from app.restaurants.amap import AmapClient, Place, Poi
from app.restaurants.schemas import Coordinate, SearchIn

BACKEND_DIR = Path(__file__).resolve().parents[2]
RESULT_FILE = BACKEND_DIR / "restaurant_live_result.md"

USERNAME_PREFIX = "live_"
TOP_N = 10
NO_SPICY_ORDER = "一周内忌食辛辣。"
PROFILE = {"gender": "male", "birth_year": 1990, "height_cm": 175, "weight_kg": 70, "activity_level": "moderate",
           "goal": "maintain"}

# 三个临时用户：键 → 显示名（也是结果里的小标题）
USER_LABELS = {
    "ordinary": "普通用户",
    "no_spicy": "忌辛辣医嘱用户",
    "fat_loss": "减脂目标用户",
}
USER_NOTES = {
    "ordinary": "没有医嘱，目标为维持体重",
    "no_spicy": f"一条“{NO_SPICY_ORDER.rstrip('。')}”的医嘱，条目已确认",
    "fat_loss": "没有医嘱，目标为减脂",
}
PLACES = (("北京国贸", "国贸", "北京"), ("上海人民广场", "人民广场", "上海"), ("成都春熙路", "春熙路", "成都"))
# 公开地标的大致 GPS（WGS-84）坐标，脚本按正式流程换算成高德坐标再检索
GPS_LANDMARK = ("北京天安门广场", 116.39125, 39.90784)
GPS_USER = "no_spicy"
NEED_TEXT = "想吃点清淡少油的"
NEED_PLACE = PLACES[2]
NEED_USER = "fat_loss"

CONCLUSION_NAMES = {"suitable": "适合", "caution": "需要注意", "not_recommended": "建议避开", "unchecked": "未核对"}
SOURCE_LABELS = {"gps": "GPS 坐标", "place": "手动地点", "saved_area": "已保存的大致区域"}

Progress = Callable[[str], None]


class RecordingClient:
    """包一层真实的高德客户端：请求原样转发，顺带按店铺编号记下周边搜索返回的原始数据（类别编码与类别名称）。"""

    def __init__(self, client: AmapClient):
        self._client = client
        self.pois: dict[str, Poi] = {}

    def around(self, lng: float, lat: float, *, keywords: str | None, radius: int) -> list[Poi]:
        pois = self._client.around(lng, lat, keywords=keywords, radius=radius)
        for poi in pois:
            self.pois.setdefault(poi.id, poi)
        return pois

    def geocode(self, address: str, city: str | None) -> Place | None:
        return self._client.geocode(address, city)

    def regeo(self, lng: float, lat: float) -> Place:
        return self._client.regeo(lng, lat)


@dataclass
class Record:
    section: str
    user: str
    how: str  # 检索方式的说明
    result: dict[str, Any] | None = None
    pois: dict[str, Poi] = field(default_factory=dict)
    saved_area: str = ""
    seconds: float | None = None
    error: str = ""


# ---------- 临时用户 ----------


def _register(db, prefix: str, key: str, profile: dict) -> uuid.UUID:
    user = register_user(db, f"{prefix}{key}", secrets.token_urlsafe(16))
    disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
    for kind in CONSENT_KINDS:
        consents_service.grant(db, user.id, kind, CONSENT_VERSION)
    update_profile(db, user.id, dict(profile))
    return user.id


def create_users(prefix: str, today: date) -> dict[str, uuid.UUID]:
    """建立三个临时用户；用户名都以 prefix 开头，清理时按这个前缀删除。做 GPS 检索的用户已授权定位。"""
    ids: dict[str, uuid.UUID] = {}
    with get_sessionmaker()() as db:
        ids["ordinary"] = _register(db, prefix, "ordinary", PROFILE)
        ids["no_spicy"] = _register(db, prefix, "no_spicy", PROFILE)
        order = orders.create_order(db, ids["no_spicy"], NO_SPICY_ORDER, today, today)
        for item in orders.list_order_items(db, ids["no_spicy"], order.id):
            items.confirm_item(db, ids["no_spicy"], item.id, {}, today)
        ids["fat_loss"] = _register(db, prefix, "fat_loss", {**PROFILE, "goal": "lose_fat"})
        service.set_consent(db, ids[GPS_USER], service.GRANTED)
    return ids


def delete_users(prefix: str) -> int:
    """按用户名前缀删除临时用户，返回删除的人数。餐厅设置、医嘱随用户级联删除。"""
    with get_sessionmaker()() as db:
        result = db.execute(delete(User).where(User.username.startswith(prefix, autoescape=True)))
        db.commit()
        return result.rowcount


# ---------- 场景 ----------


class _Runner:
    def __init__(self, ids: dict[str, uuid.UUID], client: RecordingClient, today: date, secrets_: list[str],
                 records: list[Record], progress: Progress):
        self.ids = ids
        self.client = client
        self.today = today
        self.secrets = secrets_
        self.records = records
        self.progress = progress

    def _error_text(self, exc: Exception) -> str:
        if isinstance(exc, AppError):
            return scrub(f"{exc.code}：{exc.message}", self.secrets)
        return f"脚本内部出错：{type(exc).__name__}"  # 只记异常类名，不带异常文字，避免带出密钥

    def search(self, record: Record, user: str, request: SearchIn) -> None:
        """用正式的检索流程查一次；出错时记下错误并继续，不让一个场景中断整个脚本。"""
        user_id = self.ids[user]
        start = time.perf_counter()
        try:
            with get_sessionmaker()() as db:
                record.result = service.search(db, user_id, request, self.today, client=self.client, factory=None)
                if request.remember_area:
                    area = service.get_settings(db, user_id).area
                    record.saved_area = area["name"] if area else "（没有保存）"
            record.pois = dict(self.client.pois)
        except Exception as exc:
            record.error = self._error_text(exc)
        record.seconds = time.perf_counter() - start
        self.records.append(record)
        status = f"出错（{record.error}）" if record.error else "完成"
        self.progress(scrub(f"  {record.section} · {record.user}：{status}，{record.seconds:.1f} 秒", self.secrets))

    def places(self) -> None:
        for title, place, city in PLACES:
            for user, label in USER_LABELS.items():
                record = Record(f"手动地点：{title}", label, f"手动地点：{place}（城市：{city}）")
                self.search(record, user, SearchIn(place=place, city=city))

    def gps(self) -> None:
        title, lng, lat = GPS_LANDMARK
        record = Record(f"GPS 坐标：{title}", USER_LABELS[GPS_USER],
                        f"GPS 坐标（WGS-84）：{lng}, {lat}；已授权定位，勾选记住大致区域")
        request = SearchIn(location=Coordinate(lng=lng, lat=lat, coord_type="gps"), remember_area=True)
        self.search(record, GPS_USER, request)

    def need(self) -> None:
        title, place, city = NEED_PLACE
        record = Record(f"一句话需求：{title}", USER_LABELS[NEED_USER],
                        f"手动地点：{place}（城市：{city}），一句话需求：“{NEED_TEXT}”")
        self.search(record, NEED_USER, SearchIn(place=place, city=city, need=NEED_TEXT))


def run_scenarios(client: RecordingClient, today: date, prefix: str, secrets_: list[str], records: list[Record],
                  progress: Progress) -> None:
    """建立临时用户、依次跑场景。清理不在这里做：调用方用 delete_users 在 finally 里删。"""
    progress("建立 3 个临时用户")
    ids = create_users(prefix, today)
    runner = _Runner(ids, client, today, secrets_, records, progress)
    runner.places()
    runner.gps()
    runner.need()


# ---------- 结果文件 ----------


def _cell(value: Any) -> str:
    """表格单元格：空值写“无”，竖线换成全角，换行换成空格。"""
    if value is None or value == "":
        return "无"
    return str(value).replace("|", "｜").replace("\n", " ")


def _names(values: list[str]) -> str:
    return "、".join(values) or "无"


def _shop_rows(record: Record) -> list[str]:
    lines = ["| 序号 | 名称 | 类型 | 距离（米） | 结论 | 评分 | 高德类别编码 | 高德类别名称 |", "|---|---|---|---|---|---|---|---|"]
    for number, shop in enumerate(record.result["restaurants"][:TOP_N], start=1):
        poi = record.pois.get(shop["id"])
        type_name = shop["type_name"] or "未知类型（请到店自行留意）"
        lines.append(" | ".join([
            f"| {number}", _cell(shop["name"]), _cell(type_name), _cell(shop["distance_m"]),
            CONCLUSION_NAMES[shop["conclusion"]], _cell(shop["rating"]), _cell(poi.typecode if poi else None),
            _cell(poi.type_text if poi else None),
        ]) + " |")
    return lines


def _reason_lines(reasons: list[dict]) -> list[str]:
    return [f"  - {reason['food_name']}：{reason['message']}（来源：{SOURCE_NAMES.get(reason['source'], reason['source'])}）"
            for reason in reasons]


def _record_lines(record: Record) -> list[str]:
    lines = [f"### {record.user}", "", f"- 检索方式：{record.how}"]
    seconds = "" if record.seconds is None else f"{record.seconds:.1f} 秒"
    if record.error:
        return lines + [f"- 耗时：{seconds}", f"- 错误：{record.error}", ""]
    result = record.result
    center, needs = result["center"], result["needs"]
    lines += [f"- 中心：{center['name']}（来源：{SOURCE_LABELS[center['source']]}）",
              f"- 需求：{_names(needs['names']) if needs['names'] else '不限'}（来源：{needs['source']}）"]
    if record.saved_area:
        lines.append(f"- 保存的大致区域：{record.saved_area}")
    shown = min(len(result["restaurants"]), TOP_N)
    lines += [f"- 推荐列表：共 {len(result['restaurants'])} 家，下面列出前 {shown} 家", f"- 耗时：{seconds}", ""]
    lines += _shop_rows(record) + [""]
    if result["avoided_types"]:
        lines.append("被避开的类型：")
        for group in result["avoided_types"]:
            lines.append(f"- {group['type_name']}（避开的店：{_names(group['restaurants'])}）")
            lines += _reason_lines(group["reasons"])
    else:
        lines.append("被避开的类型：无")
    lines += ["", "各类型的到店建议（基于类别的一般性建议，不代表该店真实菜单）："]
    for advice in result["type_advice"]:
        lines.append(f"- {advice['type_name']}：{CONCLUSION_NAMES[advice['conclusion']]}；可点：{_names(advice['order'])}；"
                     f"适量：{_names(advice['moderate'])}；应避开：{_names(advice['avoid'])}")
    return lines + [""]


def render_markdown(records: list[Record], secrets_: list[str], today: date, *, interrupted: bool = False,
                    cleanup: str = "") -> str:
    """生成结果文件；整份文本输出前按密钥去掉原文，不截断。"""
    lines = ["# 附近餐厅实测结果", "", f"运行日期：{today.isoformat()}", "",
             "本文件不含高德密钥；店名、地址与类别来自高德的真实检索结果，用户只有脚本建立的临时用户。", ""]
    if interrupted:
        lines += ["注意：本次运行中途被中断或出错，下面只有中断之前已经完成的场景，请重新完整运行一次。", ""]
    lines += ["临时用户：" + "；".join(f"{USER_LABELS[key]}（{USER_NOTES[key]}）" for key in USER_LABELS) + "。", ""]
    failed = sum(1 for record in records if record.error)
    lines += [f"合计：成功 {len(records) - failed} 项，出错 {failed} 项。", ""]
    if cleanup:
        lines += [cleanup, ""]
    lines += ["高德类别编码与类别名称是高德返回的原文，用来核对类型表里的编码（类型表里的编码凭记忆写成，店名关键词优先）。", ""]
    for section in dict.fromkeys(record.section for record in records):
        lines += [f"## {section}", ""]
        for record in (r for r in records if r.section == section):
            lines += _record_lines(record)
    return scrub("\n".join(lines), list(secrets_))


def main(result_path: Path = RESULT_FILE, today: date | None = None, progress: Progress = print) -> int:
    if not amap.amap_configured():
        print("backend/.env 里没有配置 AMAP_KEY，无法运行。请在高德开放平台申请“Web 服务”类型的密钥，填到 backend/.env "
              "的 AMAP_KEY 后再运行（.env 不要提交，密钥也不要发给任何人）。")
        return 1
    secrets_ = [amap.get_settings().amap_key]
    client = RecordingClient(amap.get_amap_client())

    today = today or date.today()
    prefix = f"{USERNAME_PREFIX}{uuid.uuid4().hex[:8]}_"
    records: list[Record] = []
    code, finished = 0, False
    try:
        run_scenarios(client, today, prefix, secrets_, records, progress)
        finished = True
    except KeyboardInterrupt:
        print("已中断：中断之前已经完成的场景会写入结果文件。")
        code = 130
    except Exception as exc:  # 建用户这类准备工作出错；已完成的场景仍然写入
        print(scrub(f"运行出错：{type(exc).__name__}：{exc}", secrets_))
        code = 1
    finally:
        try:  # 不论正常结束、失败还是被中断，都删除本次建立的临时用户
            removed = delete_users(prefix)
            cleanup = f"临时用户已全部删除（本次共 {removed} 个）。"
        except Exception as exc:
            cleanup = f"警告：临时用户没有删除成功（{type(exc).__name__}）。请在数据库里删除用户名以 {prefix} 开头的用户。"
            code = code or 1
        report = render_markdown(records, secrets_, today, interrupted=not finished, cleanup=cleanup)
        result_path.write_text(report, encoding="utf-8")
        print(cleanup)
        print(f"结果已写入 {result_path.name}（不含密钥，但也请先看一遍再决定是否分享）。")
    return code


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # 终端编码不认识某个字符时不要中断
    sys.exit(main())
