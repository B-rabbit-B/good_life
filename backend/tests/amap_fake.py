"""模拟高德：基于 MockTransport，回答周边搜索、地址解析与逆地理，绝不访问真实网络。

固定的一组店：川菜馆、粥铺、轻食店、火锅店、麻辣烫、面馆、一家判断不出类别的“某某餐厅”。
fake 夹具换上测试密钥与地址、清空限流并替换传输层；不经 client 夹具的测试（例如真实服务器）
可以直接用 FakeAmap 加 app.restaurants.amap.use_transport。
"""

from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from app.config import Settings
from app.restaurants import amap
from app.restaurants import service as restaurant_service
from app.restaurants.amap import use_transport

KEY = "amap-flow-key-0123456789abcdef"
BASE = "https://amap.example.com"


def _poi(poi_id, name, typecode, distance, rating, lng, lat, address):
    return {"id": poi_id, "name": name, "location": f"{lng},{lat}", "typecode": typecode,
            "type": "餐饮服务", "address": address, "distance": distance,
            "business": {"rating": rating} if rating else []}


POIS = [
    _poi("B001", "老川菜馆", "050102", "120", "4.6", 116.462, 39.910, "建国路 1 号"),
    _poi("B002", "张记粥铺", "050100", "300", "4.2", 116.463, 39.911, "建国路 2 号"),
    _poi("B003", "绿叶轻食", "050000", "450", "4.8", 116.464, 39.912, "建国路 3 号"),
    _poi("B004", "老码头火锅", "050117", "200", "4.5", 116.465, 39.913, "建国路 4 号"),
    _poi("B005", "杨记麻辣烫", "050000", "150", "4.0", 116.466, 39.914, "建国路 5 号"),
    _poi("B006", "张姐面馆", "050100", "600", "", 116.467, 39.915, "建国路 6 号"),
    _poi("B007", "某某餐厅", "050000", "80", "", 116.468, 39.916, "建国路 7 号"),
]
GUOMAO = {"formatted_address": "北京市朝阳区国贸", "district": "朝阳区", "adcode": "110105", "city": [],
          "province": "北京市", "location": "116.458000,39.908000"}
# 只匹配到城市：区县与城市都是空数组（直辖市），名称只能来自省份
CITY_LEVEL = {"formatted_address": "北京市", "district": [], "city": [], "province": "北京市", "adcode": "110000",
              "location": "116.407000,39.904000"}
REGEO = {"formatted_address": "北京市朝阳区建国门外大街", "addressComponent": {
    "district": "朝阳区", "adcode": "110105", "city": [], "province": "北京市"}}


def ok(body: dict) -> httpx2.Response:
    return httpx2.Response(200, json={"status": "1", "info": "OK", "infocode": "10000", **body})


class FakeAmap:
    """模拟高德：记录每次请求的路径与参数，以及请求时测试登记的数据库会话是否开着事务。"""

    def __init__(self):
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.sessions: list = []
        self.in_transaction: list[bool] = []
        self.override: httpx2.Response | None = None
        self.regeo = REGEO
        self.geocodes = {"国贸": [GUOMAO], "北京": [CITY_LEVEL]}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.in_transaction.append(any(session.in_transaction() for session in self.sessions))
        params = {k: v[0] for k, v in parse_qs(urlsplit(str(request.url)).query).items()}
        self.requests.append((request.url.path, params))
        if self.override is not None:
            return self.override
        if request.url.path == "/v5/place/around":
            return ok({"count": str(len(POIS)), "pois": POIS})
        if request.url.path == "/v3/geocode/geo":
            found = self.geocodes.get(params["address"], [])
            return ok({"count": str(len(found)), "geocodes": found})
        if request.url.path == "/v3/geocode/regeo":
            return ok({"regeocode": self.regeo})
        return httpx2.Response(404)

    def calls(self, path: str) -> list[dict[str, str]]:
        return [params for request_path, params in self.requests if request_path == path]


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, database_url="postgresql+psycopg://u:p@localhost:5433/db", jwt_secret="x" * 32,
                    field_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=", **overrides)


@pytest.fixture
def fake(client, monkeypatch):
    monkeypatch.setattr(amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url=BASE))
    restaurant_service.reset_rate_limit()
    model = FakeAmap()
    with use_transport(httpx2.MockTransport(model)):
        yield model
    restaurant_service.reset_rate_limit()
