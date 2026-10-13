"""把构建好的前端（单页应用）挂在根路径。

只替换路由器的默认处理（没有任何路由匹配的请求才会走到这里），所以不会遮住任何已有路由，
也不改变已有路由的 405；未知的 /api 路径仍然交给原来的 not_found，返回统一格式的 404。

取文件的规则：
- 请求路径先按文本检查，不合格（空段、..、点开头的段、反斜杠、冒号、盘符或 UNC 形式）的一律当作不存在，
  不拼路径、不碰文件系统（所以 UNC 形式的路径不会发出网络访问）；
- 解析后跑到 dist 之外的（包括指向 dist 之外的符号链接）当作不存在；
- 不存在时：/assets/ 下的返回 404；最后一段带扩展名（含点）的返回 404；其余当作前端路由，返回 index.html。
"""

from pathlib import Path, PurePosixPath, PureWindowsPath

from fastapi import FastAPI
from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ASSETS_PREFIX = "/assets/"
IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
# 只加不会影响前端运行的三项（不设完整的 CSP：字体、启动脚本等要逐项核对，留给以后）
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Referrer-Policy": "same-origin",
}


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _safe_relative(path: str) -> str | None:
    """按文本检查请求路径，合格时返回去掉开头斜杠的相对路径，否则 None（不访问文件系统）。"""
    segments = path.split("/")
    for index, segment in enumerate(segments):
        if segment == "":
            if 0 < index < len(segments) - 1:
                return None
            continue
        if segment.startswith(".") or "\\" in segment or ":" in segment:
            return None
    relative = path.lstrip("/")
    if PureWindowsPath(relative).drive or PureWindowsPath(relative).is_absolute() or PurePosixPath(relative).is_absolute():
        return None
    return relative


def _file_in(dist: Path, path: str) -> Path | None:
    """路径对应的 dist 内的文件；路径不合格、解析后跑到 dist 之外的、不是文件的一律返回 None。"""
    relative = _safe_relative(path)
    if relative is None:
        return None
    try:
        candidate = (dist / relative).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return candidate
    except (OSError, ValueError):
        pass
    return None


def _has_extension(path: str) -> bool:
    """最后一段含点（例如 /favicon.ico、/x/y.js）：这是在要一个文件，不是前端路由。"""
    return "." in path.rstrip("/").rsplit("/", 1)[-1]


def mount_frontend(app: FastAPI, dist_dir: Path) -> bool:
    """dist_dir 里有 index.html 才挂载并返回 True；否则什么都不做。"""
    dist = dist_dir.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return False
    not_found = app.router.default

    async def serve(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD") or _is_api_path(path):
            await not_found(scope, receive, send)
            return
        found = _file_in(dist, path)
        if found is None and (path.startswith(ASSETS_PREFIX) or _has_extension(path)):
            await not_found(scope, receive, send)
            return
        cache = IMMUTABLE if path.startswith(ASSETS_PREFIX) else NO_CACHE
        response = FileResponse(found or index, headers={"Cache-Control": cache, **SECURITY_HEADERS})
        await response(scope, receive, send)

    app.router.default = serve
    return True
