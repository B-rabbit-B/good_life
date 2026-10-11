import math
from urllib.parse import parse_qs, unquote, urlsplit

import httpx2
import pytest

from app.config import Settings
from app.errors import AppError
from app.restaurants import amap
from app.restaurants.amap import AmapClient, Place, Poi, get_amap_client, navigation_url, use_transport
from app.restaurants.coords import coarse, wgs84_to_gcj02

KEY = "amap-test-key-0123456789abcdef"
BASE = "https://amap.example.com"
GOOD_ENV = {
    "database_url": "postgresql+psycopg://u:p@localhost:5433/db",
    "jwt_secret": "x" * 32,
    "field_encryption_key": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}


def _meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    mean_lat = math.radians((a[1] + b[1]) / 2)
    dx = (a[0] - b[0]) * 111_320 * math.cos(mean_lat)
    dy = (a[1] - b[1]) * 110_540
    return math.hypot(dx, dy)


class Recorder:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item

    def client(self) -> AmapClient:
        return AmapClient(KEY, BASE, 5.0, transport=httpx2.MockTransport(self))

    @property
    def params(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(str(self.requests[-1].url)).query).items()}


def ok(body: dict) -> httpx2.Response:
    return httpx2.Response(200, json={"status": "1", "info": "OK", "infocode": "10000", **body})


def fail(infocode: str) -> httpx2.Response:
    return httpx2.Response(200, json={"status": "0", "info": f"INFO {KEY}", "infocode": infocode})


POIS = {
    "count": "3",
    "pois": [
        {"id": "B001", "name": "老川菜馆", "location": "116.4600,39.9100", "typecode": "050118",
         "type": "餐饮服务;中餐厅;四川菜(川菜)", "address": "建国路1号", "distance": "320",
         "business": {"rating": "4.6"}},
        {"id": "B002", "name": "张记粥铺", "location": "116.4610,39.9110", "typecode": "050100",
         "type": "餐饮服务;中餐厅", "address": [], "distance": "", "business": []},
        {"id": "B003", "name": "无评分店", "location": "116.4620,39.9120", "typecode": "050000",
         "type": "餐饮服务", "address": "某路", "distance": "abc", "business": {"rating": []}},
    ],
}


# ---------- 坐标 ----------

def test_beijing_point_shifts_by_hundreds_of_meters_deterministically():
    wgs = (116.397428, 39.90923)
    gcj = wgs84_to_gcj02(*wgs)
    assert gcj == wgs84_to_gcj02(*wgs)
    assert 100 < _meters(wgs, gcj) < 800
    assert gcj[0] > wgs[0] and gcj[1] > wgs[1]  # 北京一带 GCJ-02 偏向东北


@pytest.mark.parametrize("point", [(139.6917, 35.6895), (-74.006, 40.7128)])
def test_points_outside_china_are_unchanged(point):
    assert wgs84_to_gcj02(*point) == point


def test_coarse_rounds_to_two_decimals():
    assert coarse(116.397428, 39.90923) == (116.4, 39.91)
    assert coarse(121.4737, 31.2304) == (121.47, 31.23)


# ---------- 配置 ----------

def test_amap_settings_defaults_and_empty_key_is_none():
    settings = Settings(_env_file=None, **GOOD_ENV)
    assert settings.amap_key is None
    assert settings.amap_base_url == "https://restapi.amap.com"
    assert settings.amap_timeout_seconds == 8.0
    assert Settings(_env_file=None, amap_key="", **GOOD_ENV).amap_key is None
    assert Settings(_env_file=None, amap_key="abc", **GOOD_ENV).amap_key == "abc"


# ---------- around ----------

def test_around_sends_expected_request_and_parses_pois():
    rec = Recorder(ok(POIS))
    pois = rec.client().around(116.46, 39.91, keywords="粥", radius=2000)
    request = rec.requests[0]
    assert request.method == "GET"
    assert request.url.path == "/v5/place/around"
    assert rec.params == {
        "key": KEY, "location": "116.460000,39.910000", "types": "050000", "radius": "2000",
        "sortrule": "distance", "page_size": "25", "page_num": "1", "show_fields": "business", "keywords": "粥",
    }
    assert pois[0] == Poi("B001", "老川菜馆", 116.46, 39.91, "050118", "餐饮服务;中餐厅;四川菜(川菜)", "建国路1号", 320, 4.6)
    assert isinstance(pois[0].distance_m, int)
    assert pois[1].rating is None and pois[1].distance_m is None and pois[1].address == ""
    assert pois[2].rating is None and pois[2].distance_m is None


def test_around_without_keywords_omits_the_parameter():
    rec = Recorder(ok({"count": "0", "pois": []}))
    assert rec.client().around(116.46, 39.91, keywords=None, radius=500) == []
    assert "keywords" not in rec.params


def test_around_without_pois_field_returns_empty_list():
    rec = Recorder(ok({"count": "0"}))
    assert rec.client().around(116.46, 39.91, keywords=None, radius=500) == []


def test_around_skips_pois_without_usable_location():
    body = {"pois": [{"id": "X", "name": "坏店", "location": "", "typecode": "050000"}, POIS["pois"][0]]}
    pois = Recorder(ok(body)).client().around(116.46, 39.91, keywords=None, radius=500)
    assert [p.id for p in pois] == ["B001"]


# ---------- geocode / regeo ----------

def test_geocode_returns_first_result():
    rec = Recorder(ok({"count": "1", "geocodes": [
        {"formatted_address": "北京市朝阳区国贸", "location": "116.4600,39.9100", "district": "朝阳区",
         "adcode": "110105"},
        {"formatted_address": "别处", "location": "1,2", "district": "x", "adcode": "1"},
    ]}))
    place = rec.client().geocode("国贸", "北京")
    assert place == Place("北京市朝阳区国贸", 116.46, 39.91, "朝阳区", "110105")
    assert rec.requests[0].url.path == "/v3/geocode/geo"
    assert rec.params == {"key": KEY, "address": "国贸", "city": "北京"}


def test_geocode_without_city_omits_it_and_no_result_is_none():
    rec = Recorder(ok({"count": "0", "geocodes": []}))
    assert rec.client().geocode("不存在的地方", None) is None
    assert "city" not in rec.params


def test_regeo_reads_district_and_adcode():
    rec = Recorder(ok({"regeocode": {"formatted_address": "北京市朝阳区建国路", "addressComponent": {
        "district": "朝阳区", "adcode": "110105"}}}))
    place = rec.client().regeo(116.46, 39.91)
    assert place == Place("北京市朝阳区建国路", 116.46, 39.91, "朝阳区", "110105")
    assert rec.requests[0].url.path == "/v3/geocode/regeo"
    assert rec.params["location"] == "116.460000,39.910000"
    assert rec.params["key"] == KEY


def test_regeo_with_empty_district_array_gives_empty_text():
    rec = Recorder(ok({"regeocode": {"formatted_address": [], "addressComponent": {"district": [], "adcode": []}}}))
    place = rec.client().regeo(116.46, 39.91)
    assert place.district == "" and place.adcode == ""


# ---------- 错误映射 ----------

def _call(client: AmapClient):
    return client.around(116.46, 39.91, keywords=None, radius=500)


@pytest.mark.parametrize("infocode", ["10003", "10004", "10014", "10019", "10020", "10021", "10044", "10045"])
def test_quota_and_rate_infocodes_map_to_busy(infocode):
    with pytest.raises(AppError) as info:
        _call(Recorder(fail(infocode)).client())
    assert (info.value.status_code, info.value.code) == (503, "restaurant_service_busy")
    assert "稍后" in info.value.message


@pytest.mark.parametrize("infocode", ["10001", "10009", "10010", "10012"])
def test_key_infocodes_map_to_failed_with_key_hint(infocode):
    with pytest.raises(AppError) as info:
        _call(Recorder(fail(infocode)).client())
    assert (info.value.status_code, info.value.code) == (502, "restaurant_service_failed")
    assert "Web 服务" in info.value.message


@pytest.mark.parametrize(
    "response",
    [
        fail("20003"),
        fail("99999"),
        httpx2.Response(500, text=f"boom {KEY}"),
        httpx2.Response(404, text="nope"),
        httpx2.Response(200, text=f"<html>{KEY}</html>"),
        httpx2.Response(200, json=["not", "an", "object"]),
        httpx2.Response(200, json={"status": "1", "pois": "oops"}),
        httpx2.Response(200, json={"status": "weird"}),
        httpx2.ConnectError(f"cannot connect with {KEY}"),
        httpx2.ReadTimeout(f"timed out {KEY}"),
    ],
)
def test_other_failures_map_to_service_failed_without_leaking_key(response):
    with pytest.raises(AppError) as info:
        _call(Recorder(response).client())
    error = info.value
    assert (error.status_code, error.code) == (502, "restaurant_service_failed")
    assert KEY not in error.message and KEY not in repr(error) and KEY not in str(error)
    assert error.__cause__ is None and (error.__context__ is None or error.__suppress_context__)


def test_busy_and_key_errors_do_not_leak_key_either():
    for infocode in ("10003", "10009"):
        with pytest.raises(AppError) as info:
            _call(Recorder(fail(infocode)).client())
        assert KEY not in info.value.message and KEY not in repr(info.value)


def test_geocode_and_regeo_share_the_error_mapping():
    with pytest.raises(AppError) as info:
        Recorder(fail("10003")).client().geocode("国贸", None)
    assert info.value.code == "restaurant_service_busy"
    with pytest.raises(AppError) as info:
        Recorder(fail("10009")).client().regeo(116.46, 39.91)
    assert info.value.code == "restaurant_service_failed"
    with pytest.raises(AppError) as info:
        Recorder(ok({"regeocode": "oops"})).client().regeo(116.46, 39.91)
    assert info.value.code == "restaurant_service_failed"


def test_client_repr_does_not_contain_key():
    assert KEY not in repr(AmapClient(KEY, BASE, 5.0))


# ---------- get_amap_client / use_transport ----------

def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**GOOD_ENV, **overrides})


def test_get_amap_client_without_key_is_503_not_configured(monkeypatch):
    monkeypatch.setattr(amap, "get_settings", lambda: _settings())
    with pytest.raises(AppError) as info:
        get_amap_client()
    assert (info.value.status_code, info.value.code) == (503, "restaurant_not_configured")
    assert "高德" in info.value.message


def test_get_amap_client_uses_settings_and_transport_override(monkeypatch):
    monkeypatch.setattr(
        amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url="https://mock.test/", amap_timeout_seconds=3)
    )
    rec = Recorder(ok({"count": "0", "pois": []}))
    assert amap._transport_override is None
    with use_transport(httpx2.MockTransport(rec)):
        client = get_amap_client()
        assert client.around(116.46, 39.91, keywords=None, radius=500) == []
    assert amap._transport_override is None
    assert str(rec.requests[0].url).startswith("https://mock.test/v5/place/around?")
    assert rec.params["key"] == KEY


def test_use_transport_restores_previous_value_on_error():
    first, second = httpx2.MockTransport(lambda r: httpx2.Response(200)), httpx2.MockTransport(lambda r: httpx2.Response(200))
    with use_transport(first):
        with pytest.raises(RuntimeError):
            with use_transport(second):
                assert amap._transport_override is second
                raise RuntimeError
        assert amap._transport_override is first
    assert amap._transport_override is None


# ---------- 导航链接 ----------

def test_navigation_url_encodes_name_and_sets_fixed_parameters():
    poi = Poi("B1", "老川 菜馆&分店", 116.46, 39.91, "050118", "", "", None, None)
    url = navigation_url(poi)
    assert url.startswith("https://uri.amap.com/navigation?to=116.460000,39.910000,")
    assert " " not in url and "&分" not in url
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert query["mode"] == ["walk"] and query["src"] == ["good-life"]
    assert query["coordinate"] == ["gaode"] and query["callnative"] == ["1"]
    to = unquote(query["to"][0]).split(",", 2)
    assert to == ["116.460000", "39.910000", "老川 菜馆&分店"]
    assert url.endswith("&mode=walk&src=good-life&coordinate=gaode&callnative=1")
