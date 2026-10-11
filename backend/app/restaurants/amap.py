"""高德 Web 服务客户端：周边搜索、地址解析、逆地理。

坐标一律是 GCJ-02；GPS 坐标要先用 coords.wgs84_to_gcj02 换算。密钥只放在请求参数里，
任何错误说明、异常信息与 repr 都不含密钥或高德返回的原文。
"""

import logging
import math
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx2

from app.config import get_settings
from app.errors import AppError

_BUSY_CODES = {"10003", "10004", "10014", "10019", "10020", "10021", "10044", "10045"}
_KEY_CODES = {"10001", "10009", "10010", "10012"}

_transport_override: httpx2.BaseTransport | None = None

_QUERY = re.compile(r"\?[^\s\"]*")


class _RedactQueryFilter(logging.Filter):
    """httpx2 会在 INFO 级别记录完整请求地址，查询串里有密钥、坐标、地点原文与检索关键词；这里把整个查询串
    改写成 ?<redacted>，只保留路径。只改写这个记录器的记录，不抬高日志级别，所以模型适配器的 INFO 日志不受影响。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            return True
        redacted = _QUERY.sub("?<redacted>", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


_httpx_logger = logging.getLogger("httpx2")
if not any(isinstance(f, _RedactQueryFilter) for f in _httpx_logger.filters):
    _httpx_logger.addFilter(_RedactQueryFilter())


@dataclass(frozen=True)
class Poi:
    id: str
    name: str
    lng: float
    lat: float
    typecode: str
    type_text: str
    address: str
    distance_m: int | None
    rating: float | None


@dataclass(frozen=True)
class Place:
    name: str
    lng: float
    lat: float
    district: str
    adcode: str
    city: str  # 直辖市的 city 在高德返回里是空数组，这里为空字符串
    province: str


def _failed(message: str = "附近餐厅服务暂时不可用（高德服务出错或无法连接），请稍后再试") -> AppError:
    return AppError(502, "restaurant_service_failed", message)


def _text(value: Any) -> str:
    """高德对空值常返回空数组，统一当作空字符串。"""
    return value.strip() if isinstance(value, str) else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _location(value: Any) -> tuple[float, float] | None:
    parts = _text(value).split(",")
    if len(parts) != 2:
        return None
    lng, lat = _number(parts[0]), _number(parts[1])
    return (lng, lat) if lng is not None and lat is not None else None


def _coord(value: float) -> str:
    return f"{value:.6f}"


class AmapClient:
    def __init__(self, key: str, base_url: str, timeout: float, transport: httpx2.BaseTransport | None = None):
        self._key = key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return f"AmapClient(base_url={self._base_url!r})"

    def _get(self, path: str, params: dict[str, str]) -> dict:
        """发出请求并返回 status 为 1 的 JSON 对象；其余情况都转成 AppError。"""
        try:
            # 注入 transport（测试）时不读取环境中的代理设置，保证请求一定走注入的 transport
            with httpx2.Client(transport=self._transport, timeout=self._timeout,
                               trust_env=self._transport is None) as client:
                response = client.get(self._base_url + path, params={"key": self._key, **params})
        except httpx2.TimeoutException:
            raise _failed("连接高德服务超时，请稍后再试") from None
        except (httpx2.HTTPError, httpx2.InvalidURL):
            # 底层异常文本可能带出带密钥的请求地址，所以不带出任何原文
            raise _failed() from None
        if response.status_code != 200:
            raise _failed()
        try:
            data = response.json()
        except ValueError:
            raise _failed() from None
        if not isinstance(data, dict):
            raise _failed()
        status = data.get("status")
        if status == "1":
            return data
        if status != "0":
            raise _failed()
        infocode = str(data.get("infocode", ""))
        if infocode in _BUSY_CODES:
            raise AppError(503, "restaurant_service_busy", "高德服务额度用完或请求太频繁，请稍后再试")
        if infocode in _KEY_CODES:
            raise _failed("服务端配置的高德密钥无效或类型不对，需要高德开放平台的 Web 服务类型密钥，请联系管理员检查")
        raise _failed()

    def around(self, lng: float, lat: float, *, keywords: str | None, radius: int) -> list[Poi]:
        params = {
            "location": f"{_coord(lng)},{_coord(lat)}", "types": "050000", "radius": str(radius),
            "sortrule": "distance", "page_size": "25", "page_num": "1", "show_fields": "business",
        }
        if keywords:
            params["keywords"] = keywords
        data = self._get("/v5/place/around", params)
        pois = data.get("pois", [])
        if not isinstance(pois, list):
            raise _failed()
        result = []
        for item in pois:
            poi = self._poi(item)
            if poi is not None:
                result.append(poi)
        return result

    @staticmethod
    def _poi(item: Any) -> Poi | None:
        if not isinstance(item, dict):
            return None
        location = _location(item.get("location"))
        poi_id, name = _text(item.get("id")), _text(item.get("name"))
        if location is None or not poi_id or not name:
            return None
        distance = _number(item.get("distance"))
        business = item.get("business")
        rating = _number(business.get("rating")) if isinstance(business, dict) else None
        return Poi(poi_id, name, location[0], location[1], _text(item.get("typecode")), _text(item.get("type")),
                   _text(item.get("address")), int(distance) if distance is not None else None, rating)

    def geocode(self, address: str, city: str | None) -> Place | None:
        params = {"address": address}
        if city:
            params["city"] = city
        data = self._get("/v3/geocode/geo", params)
        results = data.get("geocodes", [])
        if not isinstance(results, list):
            raise _failed()
        if not results:
            return None
        first = results[0]
        location = _location(first.get("location")) if isinstance(first, dict) else None
        if location is None:
            raise _failed()
        return Place(_text(first.get("formatted_address")) or address, location[0], location[1],
                     _text(first.get("district")), _text(first.get("adcode")), _text(first.get("city")),
                     _text(first.get("province")))

    def regeo(self, lng: float, lat: float) -> Place:
        data = self._get("/v3/geocode/regeo", {"location": f"{_coord(lng)},{_coord(lat)}"})
        regeocode = data.get("regeocode")
        component = regeocode.get("addressComponent") if isinstance(regeocode, dict) else None
        if not isinstance(component, dict):
            raise _failed()
        return Place(_text(regeocode.get("formatted_address")), lng, lat,
                     _text(component.get("district")), _text(component.get("adcode")), _text(component.get("city")),
                     _text(component.get("province")))


@contextmanager
def use_transport(transport: httpx2.BaseTransport | None) -> Iterator[None]:
    """测试期间替换传输层，退出时恢复原值。"""
    global _transport_override
    previous = _transport_override
    _transport_override = transport
    try:
        yield
    finally:
        _transport_override = previous


def get_amap_client() -> AmapClient:
    settings = get_settings()
    if not settings.amap_key:
        raise AppError(503, "restaurant_not_configured",
                       "附近餐厅功能未开启：服务端还没有配置高德密钥，请联系管理员在服务端配置后再试")
    return AmapClient(settings.amap_key, settings.amap_base_url, settings.amap_timeout_seconds,
                      transport=_transport_override)


def navigation_url(poi: Poi) -> str:
    to = f"{_coord(poi.lng)},{_coord(poi.lat)},{quote(poi.name, safe='')}"
    return f"https://uri.amap.com/navigation?to={to}&mode=walk&src=good-life&coordinate=gaode&callnative=1"
