"""把构建好的前端（单页应用）挂在根路径。

只替换路由器的默认处理（没有任何路由匹配的请求才会走到这里），所以不会遮住任何已有路由，
也不改变已有路由的 405；未知的 /api 路径仍然交给原来的 not_found，返回统一格式的 404。
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ASSETS_PREFIX = "/assets/"
IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _file_in(dist: Path, path: str) -> Path | None:
    """路径对应的 dist 内的文件；解析后跑到 dist 之外的、不是文件的一律返回 None。"""
    try:
        candidate = (dist / path.lstrip("/")).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist):
            return candidate
    except (OSError, ValueError):
        pass
    return None


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
        if path.startswith(ASSETS_PREFIX):
            asset = _file_in(dist, path)
            if asset is None:
                await not_found(scope, receive, send)
                return
            response = FileResponse(asset, headers={"Cache-Control": IMMUTABLE})
        else:
            target = _file_in(dist, path) or index
            response = FileResponse(target, headers={"Cache-Control": NO_CACHE})
        await response(scope, receive, send)

    app.router.default = serve
    return True
