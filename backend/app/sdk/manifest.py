"""能力清单：名称、模块、级别、说明与输入输出的 JSON Schema；仓库里的 manifest.json 是它的快照。"""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.sdk.client import SDK_VERSION
from app.sdk.registry import REGISTRY, Capability

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"


def build_manifest(registry: dict[str, Capability]) -> dict[str, Any]:
    return {
        "sdk_version": SDK_VERSION,
        "capabilities": [
            {
                "name": cap.name,
                "module": cap.module,
                "level": cap.level,
                "summary": cap.summary,
                "input_schema": cap.input_model.model_json_schema(),
                "output_schema": TypeAdapter(cap.output_type).json_schema(mode="serialization"),
            }
            for cap in sorted(registry.values(), key=lambda cap: cap.name)
        ],
    }


def main() -> None:
    text = json.dumps(build_manifest(REGISTRY), ensure_ascii=False, indent=2, sort_keys=True)
    MANIFEST_PATH.write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
