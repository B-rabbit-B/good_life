"""前端提交的接口快照必须与后端当前的 OpenAPI 文档逐字一致，前端的类型由它生成。"""

import json
from pathlib import Path

from app.main import create_app

SNAPSHOT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"
HINT = "frontend/src/api/openapi.json 已过期：在 frontend 下运行 pnpm api:gen"


def test_frontend_openapi_snapshot_is_current():
    expected = json.dumps(create_app(serve_frontend=False).openapi(), ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n"
    assert SNAPSHOT.is_file(), HINT
    # read_text 按通用换行读取：Windows 检出成 CRLF 也照样比较内容
    assert SNAPSHOT.read_text(encoding="utf-8") == expected, HINT
