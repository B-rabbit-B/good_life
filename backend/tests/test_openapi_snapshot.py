"""前端提交的接口快照必须与后端当前的 OpenAPI 文档逐字一致，前端的类型由它生成；导出不受 .env 影响。"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT = BACKEND_DIR.parent / "frontend" / "src" / "api" / "openapi.json"
HINT = "frontend/src/api/openapi.json 已过期：在 frontend 下运行 pnpm api:gen"
# 有毒的 .env：读到它时校验会失败（JWT_SECRET 太短、加密密钥无效），其余值一看便知是从这里来的
POISON = "\n".join([
    "DATABASE_URL=postgresql+psycopg://poison:poison@127.0.0.1:1/poison",
    "JWT_SECRET=poison",
    "FIELD_ENCRYPTION_KEY=poison",
    "AMAP_KEY=POISON-AMAP-KEY",
    "LLM_TIMEOUT_SECONDS=999",
]) + "\n"
# 子进程先把 Settings 指向有毒的 .env（模拟 backend/.env），再做第二个参数里的事
SCRIPT = """
import json, sys
import app.config as config
config.Settings.model_config["env_file"] = sys.argv[1]
if sys.argv[2] == "export":
    from app.openapi_export import main
    code = main([sys.argv[3]])
else:
    code = 0
settings = config.get_settings()
print(json.dumps({"code": code, "jwt": settings.jwt_secret, "db": settings.database_url,
                  "amap": settings.amap_key, "timeout": settings.llm_timeout_seconds}))
"""
CLEARED_ENV = ("DATABASE_URL", "JWT_SECRET", "FIELD_ENCRYPTION_KEY", "AMAP_KEY", "AMAP_BASE_URL",
               "LLM_TIMEOUT_SECONDS", "LLM_ALLOW_PRIVATE_HOSTS", "FRONTEND_DIST_DIR")


def test_frontend_openapi_snapshot_is_current():
    expected = json.dumps(create_app(serve_frontend=False).openapi(), ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n"
    assert SNAPSHOT.is_file(), HINT
    # read_text 按通用换行读取：Windows 检出成 CRLF 也照样比较内容
    assert SNAPSHOT.read_text(encoding="utf-8") == expected, HINT


@pytest.fixture
def scratch():
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name not in CLEARED_ENV}
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, "-c", SCRIPT, *args], cwd=BACKEND_DIR, env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


def test_export_ignores_a_poisoned_env_file(scratch):
    poisoned = scratch / ".env"
    poisoned.write_text(POISON, encoding="utf-8")
    # 对照：不经导出直接读配置，确实会读到有毒的 .env 并因校验失败而退出
    control = _run(str(poisoned), "settings-only")
    assert control.returncode != 0 and "JWT_SECRET" in control.stderr

    out = scratch / "openapi.json"
    result = _run(str(poisoned), "export", str(out))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["code"] == 0
    assert "poison" not in report["db"].lower() and "poison" not in report["jwt"].lower()
    assert report["amap"] is None and report["timeout"] == 20.0
    assert out.read_text(encoding="utf-8") == SNAPSHOT.read_text(encoding="utf-8")
