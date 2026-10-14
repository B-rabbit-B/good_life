"""持续集成工作流的文本检查（不引入 YAML 解析库）：两个互相独立、各用自己数据库的任务；
后端警告当错误；前端先跑检查再只跑两种设备且不跑视觉对比；动作固定到大版本；失败轨迹只在失败时上传。
工作流本机无法完整运行，这里只核对文本与结构，以推送后第一次运行为准。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")  # Windows 检出时换行是 CRLF


def _jobs() -> dict[str, str]:
    """任务名到任务正文：jobs 之后缩进两格的键就是任务名，正文到下一个任务为止。"""
    lines = _text().split("\n")
    start = lines.index("jobs:") + 1
    jobs: dict[str, list[str]] = {}
    current = None
    for line in lines[start:]:
        match = re.match(r"^  ([A-Za-z][\w-]*):\s*$", line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def test_workflow_is_named_ci_and_runs_on_main_pushes_and_pull_requests():
    text = _text()
    assert re.search(r"^name: CI$", text, re.MULTILINE)
    head = text.split("jobs:")[0]
    assert re.search(r"^on:\n  push:\n    branches: \[main\]\n  pull_request:", head, re.MULTILINE)


def test_two_independent_jobs_each_with_its_own_database():
    jobs = _jobs()
    assert sorted(jobs) == ["backend", "frontend"]
    for name, body in jobs.items():
        assert len(re.findall(r"^\s+image: postgres:16$", body, re.MULTILINE)) == 1, name
        assert "POSTGRES_DB: goodlife_test" in body, name
        assert re.search(r"^\s+- 5433:5432$", body, re.MULTILINE), name
        assert "runs-on: ubuntu-24.04" in body, name
        assert "TEST_DATABASE_URL: postgresql+psycopg://goodlife:goodlife@127.0.0.1:5433/goodlife_test" in body, name
        assert "needs:" not in body, name  # 两个任务互不依赖，可以并行


def test_backend_job_treats_warnings_as_errors():
    body = _jobs()["backend"]
    assert "uv sync --frozen" in body
    assert "uv run pytest -q -W error" in body
    assert "python-version: \"3.12\"" in body
    assert body.index("uv sync --frozen") < body.index("uv run pytest -q -W error")


def test_frontend_job_runs_checks_then_two_devices_without_visual():
    text = _text()
    body = _jobs()["frontend"]
    order = [
        "uses: pnpm/action-setup@", "uses: actions/setup-node@", "uses: astral-sh/setup-uv@", "uv sync --frozen",
        "pnpm install --frozen-lockfile", "pnpm lint", "pnpm typecheck", "pnpm test:ci", "pnpm build:check",
        "pnpm exec playwright install --with-deps chromium webkit", "pnpm e2e",
    ]
    positions = [body.index(step) for step in order]
    assert positions == sorted(positions)
    assert "node-version: 22" in body
    assert "cache: pnpm" in body
    assert not re.search(r"pnpm e2e:|pnpm visual", text)
    assert "visual" not in text
    assert "layout-" not in text


def test_actions_are_pinned_to_major_versions():
    uses = re.findall(r"^\s*(?:- )?uses: (\S+)$", _text(), re.MULTILINE)
    assert uses
    for action in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+", action), action


def test_failure_traces_are_uploaded_only_on_failure():
    jobs = _jobs()
    assert "upload-artifact" not in jobs["backend"]
    body = jobs["frontend"]
    assert body.count("uses: actions/upload-artifact@") == 1
    step = body[body.index("- name: Upload failure traces"):]
    assert "if: failure()" in step
    assert "path: frontend/test-results" in step
    assert "retention-days: 7" in step
    assert step.index("if: failure()") < step.index("uses: actions/upload-artifact@")
