"""端到端测试用的后端：测试库、本地模拟模型与模拟高德，加上构建好的前端。

用法：在后端目录运行 uv run python -m app.e2e_server --port 8765 --dist <前端构建目录> --fixtures <测试图片目录>
（前端的 scripts/e2e-server.mjs 会先构建前端再调用它，Playwright 通过它启动）。
启动时把测试库 goodlife_test 迁移到最新并清空全部表，所以不能与后端 pytest 同时运行。
模型与高德只用 127.0.0.1 上的模拟服务（沿用第二阶段整体验收的模拟模型与模拟高德），密钥都是演示用的假密钥；
不读取 .env 里的数据库、令牌与加密密钥（由下面的测试值覆盖）。
"""

import argparse
import io
import os
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from fastapi import FastAPI
from PIL import Image

from app.config import get_settings
from app.phase2_acceptance import DEMO_AMAP_KEY, MEAL_COLOUR, VISION_MODEL_ID, WHITE, _AcceptanceModel, _MockAmap
from app.phase2_demo import DEMO_MODEL_ID, DEMO_MODEL_KEY, _Handler

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://goodlife:goodlife@127.0.0.1:5433/goodlife_test"
# 与 tests/conftest.py 相同的测试值，只用于测试库
TEST_JWT_SECRET = "test-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
TEST_FIELD_ENCRYPTION_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
BAD_KEY = "sk-e2e-bad-key"  # 模拟模型不认的密钥，用来测“获取模型”一步报错
FIXTURE_SIZE = (640, 480)


# ---------- 模拟模型：列模型也校验密钥，并列出对话与看图两个模型 ----------


class E2EHandler(_Handler):
    def do_GET(self) -> None:
        if self.headers.get("Authorization") != f"Bearer {DEMO_MODEL_KEY}":
            self._send(401, {"error": {"message": "bad key"}})
        elif self.path == "/v1/models":
            self._send(200, {"data": [{"id": DEMO_MODEL_ID}, {"id": VISION_MODEL_ID}]})
        else:
            self._send(404, {"error": {"message": "Not Found"}})


class E2EModel(_AcceptanceModel):
    def start(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), E2EHandler)  # 端口 0：由系统分配空闲端口
        self._server.model = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()


# ---------- 测试图片与应用 ----------


def _write_jpeg(path: Path, colour: tuple[int, int, int]) -> None:
    out = io.BytesIO()
    Image.new("RGB", FIXTURE_SIZE, colour).save(out, format="JPEG")
    path.write_bytes(out.getvalue())


def write_fixtures(directory: Path) -> None:
    """meal.jpg 是模拟看图模型认作麻婆豆腐加米饭的颜色，white.jpg 是纯白（模拟看图模型答“不是食物”）。"""
    directory.mkdir(parents=True, exist_ok=True)
    _write_jpeg(directory / "meal.jpg", MEAL_COLOUR)
    _write_jpeg(directory / "white.jpg", WHITE)


def build_app(info: dict[str, str], dist: Path | None) -> FastAPI:
    """后端应用加一个 GET /__e2e/info（测试用来拿模拟模型的地址与密钥），最后挂上前端构建目录。"""
    from app.frontend_static import mount_frontend
    from app.main import create_app  # 在环境变量就位之后再创建应用

    app = create_app(serve_frontend=False)

    @app.get("/__e2e/info", include_in_schema=False)
    def e2e_info() -> dict[str, str]:
        return info

    if dist is not None and not mount_frontend(app, dist):
        raise RuntimeError(f"前端构建目录里没有 index.html：{dist}")
    return app


def _migrate_and_clear() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    import app.models  # noqa: F401  注册全部模型
    from app.db import Base, get_engine

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="端到端测试用的后端")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dist", type=Path, default=None)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args(argv)

    os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", DEFAULT_DATABASE_URL)
    os.environ["JWT_SECRET"] = TEST_JWT_SECRET
    os.environ["FIELD_ENCRYPTION_KEY"] = TEST_FIELD_ENCRYPTION_KEY
    os.environ["LLM_ALLOW_PRIVATE_HOSTS"] = "true"  # 模拟服务在 127.0.0.1
    model = E2EModel(date.today())
    amap = _MockAmap()
    try:
        model.start()
        amap.start()
        os.environ["AMAP_KEY"] = DEMO_AMAP_KEY
        os.environ["AMAP_BASE_URL"] = amap.base_url
        get_settings.cache_clear()
        _migrate_and_clear()
        write_fixtures(args.fixtures)
        info = {"model_base_url": model.base_url, "model_key": DEMO_MODEL_KEY, "bad_key": BAD_KEY,
                "chat_model_id": DEMO_MODEL_ID, "vision_model_id": VISION_MODEL_ID}
        app = build_app(info, args.dist)

        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=args.port)
    finally:
        try:
            model.stop()
        finally:
            amap.stop()


if __name__ == "__main__":
    main()
