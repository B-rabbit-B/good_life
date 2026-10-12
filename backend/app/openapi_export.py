"""把后端的 OpenAPI 文档写成前端提交进仓库的接口快照，前端的类型由它生成。

用法：在后端目录运行 uv run python -m app.openapi_export <输出路径>（前端的 pnpm api:gen 会调用它）。
不连数据库、不启动服务，只读应用的路由定义。
"""

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI

# 导出只读路由定义，用不到数据库与密钥；给出占位值，没有 .env 的检出也能导出（已设置的环境变量优先）
PLACEHOLDER_ENV = {
    "DATABASE_URL": "postgresql+psycopg://openapi-export@127.0.0.1:1/unused",
    "JWT_SECRET": "openapi-export-placeholder-secret-0123456789",
    "FIELD_ENCRYPTION_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}


def render_openapi(app: FastAPI) -> str:
    """固定格式：中文原样、两格缩进、键排序、末尾一个换行。"""
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("用法：python -m app.openapi_export <输出路径>", file=sys.stderr)
        return 2
    for name, value in PLACEHOLDER_ENV.items():
        os.environ.setdefault(name, value)
    from app.main import create_app

    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n"：在 Windows 上也写 LF，与前端生成的类型文件一致
    out.write_text(render_openapi(create_app(serve_frontend=False)), encoding="utf-8", newline="\n")
    print(f"已写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
