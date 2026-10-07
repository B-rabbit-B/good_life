import ipaddress
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from app.errors import AppError


def _invalid(reason: str) -> AppError:
    return AppError(422, "llm_invalid_url", reason)


def _is_internal(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # 去掉 IPv6 的接口后缀
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


def validate_base_url(
    url: str, *, allow_private: bool, resolver: Callable[..., Any] = socket.getaddrinfo
) -> str:
    """检查用户填写的服务地址，返回去掉结尾斜杠的地址。

    IP 直接检查，不做域名解析；域名用 resolver 解析后，任何一个结果落在内网就拒绝，避免借服务地址探测内网。
    """
    text = url.strip()
    try:
        parts = urlsplit(text)
        port = parts.port
        host = parts.hostname
    except ValueError:
        raise _invalid("服务地址格式不正确，请填写形如 https://api.example.com/v1 的地址") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise _invalid("服务地址必须以 https:// 开头（本机调试可用 http://），请检查协议")
    if not host:
        raise _invalid("服务地址里没有主机名，请填写形如 https://api.example.com/v1 的完整地址")
    if not allow_private:
        if parts.scheme.lower() != "https":
            raise _invalid("非本机的服务地址必须使用 https://，请把 http:// 改成 https://")
        try:
            ipaddress.ip_address(host)
            addresses = [host]
        except ValueError:
            try:
                infos = resolver(host, port or 443, type=socket.SOCK_STREAM)
            except OSError:
                raise _invalid(f"无法解析主机 {host}，请检查地址是否拼写正确、网络是否可用") from None
            addresses = [info[4][0] for info in infos]
            if not addresses:
                raise _invalid(f"无法解析主机 {host}，请检查地址是否拼写正确")
        if any(_is_internal(address) for address in addresses):
            raise _invalid(f"主机 {host} 指向内网或本机地址，出于安全考虑不允许；请填写服务商提供的公网地址")
    return text.rstrip("/")
