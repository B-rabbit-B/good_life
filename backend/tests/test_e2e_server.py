"""端到端测试用的后端：信息接口不被前端单页应用遮住，模拟模型校验密钥，测试图片的颜色符合模拟看图模型的约定，
库名不以 _test 结尾时拒绝启动。"""

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from PIL import Image, ImageStat

from app import e2e_server
from app.config import Settings, get_settings
from app.e2e_server import (BAD_KEY, DEFAULT_DATABASE_URL, E2EModel, build_app, e2e_database_url, main,
                            write_fixtures)
from app.phase2_acceptance import MEAL_COLOUR, VISION_MODEL_ID
from app.phase2_demo import DEMO_MODEL_ID, DEMO_MODEL_KEY

INDEX = "<!doctype html><title>good-life</title><div id=root></div><div id=shell-root></div>"
INFO = {"model_base_url": "http://127.0.0.1:1/v1", "model_key": DEMO_MODEL_KEY, "bad_key": BAD_KEY,
        "chat_model_id": DEMO_MODEL_ID, "vision_model_id": VISION_MODEL_ID}


@pytest.fixture
def scratch():
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _list_models(base_url: str, key: str) -> tuple[int, dict]:
    request = urllib.request.Request(f"{base_url}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as err:
        with err:
            return err.code, json.loads(err.read())


def test_info_route_is_not_shadowed_by_the_spa(scratch):
    (scratch / "index.html").write_text(INDEX, encoding="utf-8")
    with TestClient(build_app(INFO, scratch)) as client:
        info = client.get("/__e2e/info")
        assert info.status_code == 200 and info.json() == INFO
        page = client.get("/chat")
        assert page.status_code == 200 and page.text == INDEX
        assert client.get("/api/health").json() == {"status": "ok"}
    with TestClient(build_app(INFO, None)) as client:  # 不给前端目录时只有接口
        assert client.get("/__e2e/info").json() == INFO
        assert client.get("/chat").status_code == 404


def test_e2e_model_rejects_a_bad_key_when_listing():
    model = E2EModel(date.today())
    model.start()
    try:
        status, body = _list_models(model.base_url, DEMO_MODEL_KEY)
        assert status == 200
        assert [entry["id"] for entry in body["data"]] == [DEMO_MODEL_ID, VISION_MODEL_ID]
        status, body = _list_models(model.base_url, BAD_KEY)
        assert status == 401 and "error" in body
    finally:
        model.stop()


def _mean(path: Path) -> list[float]:
    with Image.open(path) as image:
        assert image.size == (640, 480)
        return ImageStat.Stat(image.convert("RGB")).mean


def test_fixtures_have_the_expected_colours(scratch):
    write_fixtures(scratch / "fixtures")
    meal = _mean(scratch / "fixtures" / "meal.jpg")
    assert all(abs(channel - expected) < 3 for channel, expected in zip(meal, MEAL_COLOUR, strict=True))
    assert min(_mean(scratch / "fixtures" / "white.jpg")) > 250


# 都连不上（端口 1）：万一检查失效，也碰不到任何真实的数据库
UNREACHABLE = "postgresql+psycopg://x:x@127.0.0.1:1"
SET_BY_MAIN = ("DATABASE_URL", "JWT_SECRET", "FIELD_ENCRYPTION_KEY", "LLM_ALLOW_PRIVATE_HOSTS", "FRONTEND_DIST_DIR",
               "AMAP_KEY", "AMAP_BASE_URL")


def _guard_did_not_stop(*args, **kwargs):
    raise AssertionError("guard did not stop before side effects")


@pytest.mark.parametrize("url", [f"{UNREACHABLE}/goodlife", f"{UNREACHABLE}/goodlife_test_copy", UNREACHABLE])
def test_e2e_server_refuses_a_database_not_named_test(scratch, monkeypatch, url):
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    # 检查万一失效：迁移清表、启动模拟服务与 uvicorn 都直接让测试失败；main 改过的环境变量与配置在测试后恢复
    monkeypatch.setattr(e2e_server, "_migrate_and_clear", _guard_did_not_stop)
    monkeypatch.setattr(E2EModel, "start", _guard_did_not_stop)
    monkeypatch.setattr(uvicorn, "run", _guard_did_not_stop)
    for name in SET_BY_MAIN:
        monkeypatch.setenv(name, os.environ.get(name, ""))
    monkeypatch.setitem(Settings.model_config, "env_file", Settings.model_config.get("env_file"))
    before = (os.environ["DATABASE_URL"], Settings.model_config.get("env_file"))
    fixtures = scratch / "fixtures"
    try:
        with pytest.raises(SystemExit) as refused:
            main(["--port", "0", "--fixtures", str(fixtures)])
    finally:
        get_settings.cache_clear()
    assert "_test" in str(refused.value.code)
    # 在检查之前什么都没动：环境变量、配置与测试图片目录都还是原样
    assert (os.environ["DATABASE_URL"], Settings.model_config.get("env_file")) == before
    assert not fixtures.exists()


def test_e2e_database_url_accepts_a_test_database(monkeypatch):
    # 只调用纯检查函数，不调用 main：这个地址能通过检查
    monkeypatch.setenv("TEST_DATABASE_URL", f"{UNREACHABLE}/goodlife_test")
    assert e2e_database_url() == f"{UNREACHABLE}/goodlife_test"
    monkeypatch.delenv("TEST_DATABASE_URL")
    assert e2e_database_url() == DEFAULT_DATABASE_URL
