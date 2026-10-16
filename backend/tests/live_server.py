"""在线程里起一个真实的 uvicorn 服务器，并抓取全部日志出口的格式化文本（含堆栈），供“全部日志”金丝雀测试使用。

请求一律用标准库 urllib 发出：它不写日志，所以抓到的文本只来自服务器与应用本身（测试客户端若用 httpx2，
它自己的请求行会带上路径里的日期）。
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import uvicorn
import uvicorn.config
from fastapi import FastAPI

# 调到 DEBUG 的记录器："" 是根记录器
DEBUG_LOGGERS = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "app.access", "httpx2", "httpcore2")
CAPTURE_FORMAT = "%(name)s %(levelname)s %(message)s"
START_TIMEOUT = 30.0
STOP_TIMEOUT = 30.0


class CaptureHandler(logging.Handler):
    """记下每条记录格式化后的文本；logging.Formatter 会把 exc_info 与 stack_info 的堆栈接在消息后面。"""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.setFormatter(logging.Formatter(CAPTURE_FORMAT))
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


class _Server(uvicorn.Server):
    """启动完成（套接字已经在监听）时发出信号，不靠轮询或固定等待。"""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.ready = threading.Event()

    async def startup(self, sockets: Any = None) -> None:
        await super().startup(sockets=sockets)
        self.ready.set()


class LiveServer:
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.capture = CaptureHandler()
        self.port: int | None = None
        self._levels: dict[str, int] = {}
        self._targets: list[logging.Logger] = []
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self.port is not None, "服务器还没启动"
        return f"http://127.0.0.1:{self.port}"

    def text(self) -> str:
        return "\n".join(self.capture.lines)

    def __enter__(self) -> "LiveServer":
        # 构造 Config 时 uvicorn 按 LOGGING_CONFIG 配好自己的记录器（uvicorn 与 uvicorn.access 不向上传递）
        config = uvicorn.Config(self.app, host="127.0.0.1", port=0, log_config=uvicorn.config.LOGGING_CONFIG)
        for name in DEBUG_LOGGERS:
            logger = logging.getLogger(name)
            self._levels[name] = logger.level
            logger.setLevel(logging.DEBUG)
        existing = [item for item in logging.root.manager.loggerDict.values() if isinstance(item, logging.Logger)]
        self._targets = [logging.getLogger(), *(logger for logger in existing if not logger.propagate)]
        for logger in self._targets:
            logger.addHandler(self.capture)
        self._server = _Server(config)
        self._thread = threading.Thread(target=self._server.run, name="live-server", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + START_TIMEOUT
        while not self._server.ready.wait(0.05):
            if not self._thread.is_alive() or time.monotonic() > deadline:
                self.__exit__()
                raise RuntimeError("测试服务器没能启动：\n" + self.text())
        self.port = self._server.servers[0].sockets[0].getsockname()[1]
        return self

    def __exit__(self, *exc_info: object) -> None:
        try:
            if self._server is not None:
                self._server.should_exit = True
            if self._thread is not None:
                self._thread.join(STOP_TIMEOUT)
        finally:
            self._restore()

    def _restore(self) -> None:
        for logger in self._targets:
            logger.removeHandler(self.capture)
        for name, level in self._levels.items():
            logging.getLogger(name).setLevel(level)
        self._targets = []
        self._levels = {}


def request(base_url: str, method: str, path: str, body: Any = None,
            headers: dict[str, str] | None = None) -> tuple[int, Any]:
    """发一个 JSON 请求，返回状态码与解析后的响应体（不是 JSON 时返回文本）；4xx、5xx 不抛异常。"""
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(base_url + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
        error.close()
    text = raw.decode()
    try:
        return status, json.loads(text) if text else None
    except json.JSONDecodeError:
        return status, text


def prepare_user(base_url: str, username: str, password: str) -> dict[str, str]:
    """注册、登录、确认免责声明并给出经期与医嘱两项单独同意，返回带登录令牌的请求头。"""
    status, body = request(base_url, "POST", "/api/auth/register",
                           {"username": username, "password": password, "age_confirmed": True})
    assert status == 201, body
    status, body = request(base_url, "POST", "/api/auth/login", {"username": username, "password": password})
    assert status == 200, body
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    status, body = request(base_url, "GET", "/api/disclaimer")
    assert status == 200, body
    status, body = request(base_url, "POST", "/api/disclaimer/accept", {"version": body["version"]}, headers)
    assert status == 200, body
    status, body = request(base_url, "GET", "/api/consents", None, headers)
    assert status == 200, body
    for consent in body:
        status, granted = request(base_url, "POST", f"/api/consents/{consent['kind']}",
                                  {"version": consent["current_version"]}, headers)
        assert status == 200, granted
    return headers
