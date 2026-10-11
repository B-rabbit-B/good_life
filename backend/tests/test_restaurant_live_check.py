"""附近餐厅实测脚本：用 MockTransport 驱动的模拟高德跑完整个脚本，绝不访问真实网络，也不读取真实的 .env 密钥。"""

import io
import tempfile
from contextlib import redirect_stdout
from datetime import date
from inspect import signature
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.config import Settings
from app.db import get_sessionmaker
from app.medical.models import MedicalItem, MedicalOrder
from app.profile.service import get_or_create_profile
from app.restaurants import amap, live_check
from app.restaurants import service as restaurant_service
from app.restaurants.amap import use_transport
from app.restaurants.coords import wgs84_to_gcj02
from app.restaurants.live_check import GPS_LANDMARK, NEED_TEXT, PLACES, TOP_N, USER_LABELS
from app.restaurants.models import RestaurantSettings
from app.restaurants.needs import match_rules

BACKEND = Path(__file__).resolve().parents[1]
KEY = "amap-live-key-0123456789abcdef"
BASE = "https://amap.example.com"
TODAY = date.today()


def _poi(index: int, name: str, typecode: str, type_text: str, distance: int) -> dict:
    return {"id": f"P{index:03d}", "name": name, "location": f"{116.40 + index / 1000:.6f},39.910000",
            "typecode": typecode, "type": type_text, "address": f"某某路 {index} 号", "distance": str(distance),
            "business": {"rating": "4.5"}}


# 13 家店：多于前 10 家；有川菜、麻辣烫（忌辛辣会避开）、火锅（忌辛辣是“需要注意”）与判断不出类别的店
POIS = [
    _poi(1, "老川菜馆", "050102", "餐饮服务;中餐厅;四川菜(川菜)", 120),
    _poi(2, "张记粥铺", "050100", "餐饮服务;中餐厅;中餐厅", 300),
    _poi(3, "绿叶轻食", "050000", "餐饮服务;餐饮相关场所;餐饮相关", 450),
    _poi(4, "老码头火锅", "050117", "餐饮服务;中餐厅;火锅店", 200),
    _poi(5, "杨记麻辣烫", "050000", "餐饮服务;餐饮相关场所;餐饮相关", 150),
    _poi(6, "张姐面馆", "050100", "餐饮服务;中餐厅;中餐厅", 600),
    _poi(7, "某某餐厅", "050000", "餐饮服务;餐饮相关场所;餐饮相关", 80),
    _poi(8, "阿香饺子馆", "050100", "餐饮服务;中餐厅;中餐厅", 700),
    _poi(9, "海边渔港", "050119", "餐饮服务;中餐厅;海鲜酒楼", 800),
    _poi(10, "素心蔬食", "050120", "餐饮服务;中餐厅;素菜馆", 900),
    _poi(11, "广式茶餐厅", "050103", "餐饮服务;中餐厅;广东菜(粤菜)", 1000),
    _poi(12, "街角咖啡", "050500", "餐饮服务;咖啡厅;咖啡厅", 1100),
    _poi(13, f"调试粥铺 {KEY}", "050000", "餐饮服务", 1200),  # 店名里回显了密钥，检验结果文件会把它去掉
]
GEOCODES = {
    ("国贸", "北京"): {"formatted_address": "北京市朝阳区国贸", "district": "朝阳区", "adcode": "110105", "city": [],
                     "province": "北京市", "location": "116.458000,39.908000"},
    ("人民广场", "上海"): {"formatted_address": "上海市黄浦区人民广场", "district": "黄浦区", "adcode": "310101",
                       "city": [], "province": "上海市", "location": "121.475000,31.232000"},
    ("春熙路", "成都"): {"formatted_address": "四川省成都市锦江区春熙路", "district": "锦江区", "adcode": "510104",
                      "city": "成都市", "province": "四川省", "location": "104.080000,30.657000"},
}
REGEO = {"formatted_address": "北京市东城区东华门街道天安门", "addressComponent": {
    "district": "东城区", "adcode": "110101", "city": [], "province": "北京市"}}


def ok(body: dict) -> httpx2.Response:
    return httpx2.Response(200, json={"status": "1", "info": "OK", "infocode": "10000", **body})


class FakeAmap:
    def __init__(self, failure: httpx2.Response | None = None):
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.failure = failure

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        params = {k: v[0] for k, v in parse_qs(urlsplit(str(request.url)).query).items()}
        self.requests.append((request.url.path, params))
        assert params["key"] == KEY
        if self.failure is not None:
            return self.failure
        if request.url.path == "/v5/place/around":
            return ok({"count": str(len(POIS)), "pois": POIS})
        if request.url.path == "/v3/geocode/geo":
            found = GEOCODES.get((params["address"], params.get("city")))
            return ok({"count": "1" if found else "0", "geocodes": [found] if found else []})
        if request.url.path == "/v3/geocode/regeo":
            return ok({"regeocode": REGEO})
        return httpx2.Response(404)

    def calls(self, path: str) -> list[dict[str, str]]:
        return [params for request_path, params in self.requests if request_path == path]


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, database_url="postgresql+psycopg://u:p@localhost:5433/db", jwt_secret="x" * 32,
                    field_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=", **overrides)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url=BASE))
    restaurant_service.reset_rate_limit()
    yield
    restaurant_service.reset_rate_limit()


def _run(fake: FakeAmap | None = None, progress=None) -> tuple[int, str, str, FakeAmap]:
    """运行 main，返回（退出码，结果文件正文，屏幕输出，模拟高德）；结果文件写在临时目录里，用完删除。"""
    fake = fake or FakeAmap()
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as directory:
        result = Path(directory) / "restaurant_live_result.md"
        with use_transport(httpx2.MockTransport(fake)), redirect_stdout(out):
            kwargs = {"progress": progress} if progress else {}
            code = live_check.main(result, today=TODAY, **kwargs)
        written = result.read_text(encoding="utf-8") if result.exists() else ""
    return code, written, out.getvalue(), fake


def _count(model) -> int:
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(model))


def _assert_nothing_left() -> None:
    """临时用户及其设置、医嘱都已删除。"""
    for table in (User, RestaurantSettings, MedicalOrder, MedicalItem):
        assert _count(table) == 0, table.__name__


def _block(written: str, section: str, user: str) -> str:
    """某一节里某个用户的那一段。"""
    return written.split(f"## {section}")[1].split("\n## ")[0].split(f"### {USER_LABELS[user]}")[1].split("\n### ")[0]


# ---------- 场景齐全 ----------


def test_full_run_covers_every_scenario_and_deletes_the_users(configured):
    code, written, out, fake = _run()
    assert code == 0
    _assert_nothing_left()
    assert "临时用户已全部删除（本次共 3 个）" in written and "临时用户已全部删除" in out
    assert written.startswith("# 附近餐厅实测结果")
    assert f"运行日期：{TODAY.isoformat()}" in written and "本文件不含高德密钥" in written

    # 三个地点各一节，每节三类用户；另有 GPS 坐标一节与一句话需求一节
    for title, place, city in PLACES:
        section = written.split(f"## 手动地点：{title}")[1].split("\n## ")[0]
        for label in USER_LABELS.values():
            assert f"### {label}" in section, (title, label)
        assert f"手动地点：{place}（城市：{city}）" in section
    assert f"## GPS 坐标：{GPS_LANDMARK[0]}" in written and "## 一句话需求" in written
    assert written.count("\n### ") == 3 * 3 + 2
    assert "合计：成功 11 项，出错 0 项。" in written

    geo = [(call["address"], call["city"]) for call in fake.calls("/v3/geocode/geo")]
    assert sorted(geo) == sorted([(place, city) for _, place, city in PLACES] * 3 + [("春熙路", "成都")])


def test_each_scenario_records_center_needs_top_shops_with_raw_typecodes_avoided_types_and_time(configured):
    _, written, _, _ = _run()
    block = _block(written, f"手动地点：{PLACES[0][0]}", "ordinary")
    for field in ("- 中心：北京市朝阳区国贸（来源：手动地点）", "- 需求：不限（来源：none）", "- 耗时：", "- 推荐列表：共 "):
        assert field in block, field
    assert "| 序号 | 名称 | 类型 | 距离（米） | 结论 | 评分 | 高德类别编码 | 高德类别名称 |" in block
    rows = [line for line in block.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert len(rows) == TOP_N == 10  # 13 家店里只列出前 10 家
    assert "| 1 | 张记粥铺 | 粥铺 | 300 | 适合 | 4.5 | 050100 | 餐饮服务;中餐厅;中餐厅 |" in block
    assert "| 老川菜馆 | 川菜 | 120 |" in block and "| 050102 | 餐饮服务;中餐厅;四川菜(川菜) |" in block
    assert "被避开的类型：无" in block


def test_spicy_user_avoids_sichuan_and_malatang_but_hotpot_is_only_caution(configured):
    _, written, _, _ = _run()
    spicy = _block(written, f"手动地点：{PLACES[0][0]}", "no_spicy")
    assert "老川菜馆 |" not in spicy and "杨记麻辣烫 |" not in spicy
    assert "- 川菜（避开的店：老川菜馆）" in spicy and "- 麻辣烫与串串（避开的店：杨记麻辣烫）" in spicy
    assert "麻婆豆腐：" in spicy and "医嘱" in spicy  # 原因原样来自引擎，带出给出原因的代表菜
    assert "| 老码头火锅 | 火锅 | 200 | 需要注意 |" in spicy
    assert "- 火锅：需要注意；" in spicy and "应避开：火锅" in spicy
    ordinary = _block(written, f"手动地点：{PLACES[0][0]}", "ordinary")
    assert "被避开的类型：无" in ordinary and "老川菜馆 |" in ordinary


def test_gps_scenario_converts_the_landmark_and_saves_only_a_rough_area(configured):
    _, written, _, fake = _run()
    _, lng, lat = GPS_LANDMARK
    gcj = wgs84_to_gcj02(lng, lat)
    assert f"{gcj[0]:.6f},{gcj[1]:.6f}" in [call["location"] for call in fake.calls("/v5/place/around")]
    assert fake.calls("/v3/geocode/regeo") == [{"key": KEY, "location": f"{gcj[0]:.6f},{gcj[1]:.6f}"}]
    block = written.split(f"## GPS 坐标：{GPS_LANDMARK[0]}")[1].split("\n## ")[0]
    assert "- 中心：你的当前位置（来源：GPS 坐标）" in block
    assert "- 保存的大致区域：东城区" in block


def test_need_scenario_resolves_the_sentence_by_rules_and_sends_its_keywords(configured):
    _, written, _, fake = _run()
    keys = match_rules(NEED_TEXT)
    assert keys  # 一句话需求能被规则命中，不需要模型
    block = written.split("## 一句话需求")[1].split("\n## ")[0]
    assert f"“{NEED_TEXT}”" in block and "（来源：rules）" in block
    assert {call.get("keywords") for call in fake.calls("/v5/place/around")} - {None}


# ---------- 不泄露密钥、出错也清理 ----------


def test_no_key_appears_in_the_file_or_on_screen(configured):
    lines: list[str] = []
    code, written, out, _ = _run(progress=lines.append)
    assert code == 0
    assert "调试粥铺 ****" in written
    for text in (written, out, "\n".join(lines)):
        assert KEY not in text


def test_amap_failures_are_recorded_per_scenario_without_the_key(configured):
    failure = httpx2.Response(200, json={"status": "0", "info": f"INVALID_USER_KEY {KEY}", "infocode": "10001"})
    code, written, out, _ = _run(FakeAmap(failure))
    assert code == 0
    _assert_nothing_left()
    assert "合计：成功 0 项，出错 11 项。" in written
    assert "- 错误：restaurant_service_failed：服务端配置的高德密钥无效" in written
    assert KEY not in written and KEY not in out


def test_interrupted_run_still_deletes_the_users_and_writes_the_partial_result(configured, monkeypatch):
    real_search = restaurant_service.search
    calls = {"count": 0}

    def search(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 4:  # 跑到一半，用户按下 Ctrl+C
            raise KeyboardInterrupt
        return real_search(*args, **kwargs)

    monkeypatch.setattr(live_check.service, "search", search)
    code, written, out, _ = _run()
    assert code == 130
    _assert_nothing_left()
    assert "中断" in written and "中断" in out
    assert written.count("\n### ") == 3
    assert KEY not in written and KEY not in out


def test_setup_failure_still_deletes_the_users_that_were_created(configured, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError(f"setup failed with {KEY}")

    monkeypatch.setattr(live_check.orders, "create_order", boom)
    code, written, out, _ = _run()
    assert code == 1
    _assert_nothing_left()
    assert "运行出错：RuntimeError" in out and KEY not in out and KEY not in written
    assert "中断或出错" in written


def test_cleanup_failure_is_reported_with_the_prefix_and_the_exit_code_is_not_zero(configured, monkeypatch):
    def broken(prefix):
        raise RuntimeError("db down")

    monkeypatch.setattr(live_check, "delete_users", broken)
    code, written, out, _ = _run()
    assert code == 1
    assert "警告：临时用户没有删除成功" in written and "live_" in out


def test_usernames_carry_a_unique_prefix_and_only_those_users_are_deleted():
    with get_sessionmaker()() as db:
        bystander = live_check.register_user(db, "live", "pass-word-123")
        keep = bystander.id
    ids = live_check.create_users("live_aaaaaaaa_", TODAY)
    assert set(ids) == set(USER_LABELS)
    with get_sessionmaker()() as db:
        names = set(db.scalars(select(User.username)))
        assert {f"live_aaaaaaaa_{key}" for key in USER_LABELS} <= names
        goals = {key: get_or_create_profile(db, ids[key]).goal for key in USER_LABELS}
        consent = db.scalar(select(RestaurantSettings.location_consent).where(
            RestaurantSettings.user_id == ids[live_check.GPS_USER]))
    assert goals["fat_loss"] == "lose_fat" and goals["ordinary"] == goals["no_spicy"] == "maintain"
    assert consent == "granted"  # GPS 坐标检索的用户已授权定位
    assert _count(MedicalItem) >= 1
    assert live_check.delete_users("live_aaaaaaaa_") == 3
    with get_sessionmaker()() as db:
        assert db.get(User, keep) is not None and _count(RestaurantSettings) == 0


# ---------- 入口与文件 ----------


def test_main_without_an_amap_key_explains_what_to_do(monkeypatch, capsys):
    monkeypatch.setattr(amap, "get_settings", lambda: _settings())
    with tempfile.TemporaryDirectory() as directory:
        result = Path(directory) / "restaurant_live_result.md"
        assert live_check.main(result, today=TODAY) == 1
        assert not result.exists()
    out = capsys.readouterr().out
    assert "AMAP_KEY" in out and "Web 服务" in out and ".env" in out
    _assert_nothing_left()


def test_defaults_use_the_server_config_and_a_git_ignored_result_file():
    params = signature(live_check.main).parameters
    assert params["result_path"].default == BACKEND / "restaurant_live_result.md"
    entries = (BACKEND / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "restaurant_live_result.md" in entries
