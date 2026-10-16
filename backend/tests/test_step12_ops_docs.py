"""步骤 12 任务 11 的文档检查：备份与恢复预案、依赖故障预案、新人复现记录（交付文档，不含代码与命令），
以及 README 的新章节与状态徽章。任务 9 的隐私文档由 test_step12_docs.py 检查，这里不碰。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "12-交付物"
README = ROOT / "README.md"
BACKUP = "备份与恢复预案.md"
DEPENDENCY = "依赖故障预案.md"
REPRODUCTION = "新人复现记录.md"
FORBIDDEN = ("```", "`", "pnpm ", "uv run", "uv sync", "python -m", "docker ", "pg_dump", "psql ", "git clone")


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _readme() -> str:
    return README.read_text(encoding="utf-8").replace("\r\n", "\n")  # Windows 检出时换行是 CRLF


def _readme_section(number: int) -> str:
    text = _readme()
    match = re.search(rf"^## {number}\. .*?(?=^## \d+\. |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, number
    return match.group(0)


def test_runbooks_contain_no_commands_and_point_to_readme():
    for name in (BACKUP, DEPENDENCY, REPRODUCTION):
        content = _read(name)
        for word in FORBIDDEN:
            assert word not in content, (name, word)
    backup = _read(BACKUP)
    assert "README" in backup and "第 26 节" in backup
    for topic in ("数据库", "加密密钥", "FIELD_ENCRYPTION_KEY", "不备份", "恢复", "核对", "丢失", "删除账号", "残留", "过期"):
        assert topic in backup, topic
    assert "README" in _read(DEPENDENCY)


def test_dependency_runbook_covers_three_dependencies_with_codes():
    content = _read(DEPENDENCY)
    for dependency in ("数据库", "模型服务", "高德"):
        assert dependency in content, dependency
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "backend" / "app").rglob("*.py"))
    for code in ("internal_error", "agent_model_error", "restaurant_service_failed"):
        assert code in content, code
        assert f'"{code}"' in source, code  # 预案里写的错误码在源码里确实存在
    for heading in ("用户所见", "恢复方法", "恢复后核对"):
        assert content.count(heading) >= 3, heading


def test_reproduction_record_lists_every_readme_step():
    content = _read(REPRODUCTION)
    for number in (1, 2, 3, 4, 5, 6, 7, 22):
        assert f"第 {number} 节" in content, number
    assert "大小写" in content
    assert "卡点" in content and "修正" in content
    assert "第一次运行" in content  # 推送后 CI 第一次运行的补记位置


def test_readme_has_the_new_sections_and_the_badge():
    text = _readme()
    head = text.split("\n## ")[0]
    assert "actions/workflows/ci.yml/badge.svg" in head
    headings = re.findall(r"^## (\d+)\. (.+)$", text, re.MULTILINE)
    assert [(int(n), t) for n, t in headings[-4:]] == [
        (23, "隐私与数据"), (24, "提示词注入红队实测"), (25, "持续集成"), (26, "备份与恢复")]
    privacy = _readme_section(23)
    for word in ("单独同意", "导出", "清空", "删除账号", "撤回"):
        assert word in privacy, word
    redteam = _readme_section(24)
    assert "uv run python -m app.agent.redteam_check" in redteam
    assert "llm_keys.local.env" in redteam and "不提交" in redteam
    ci = _readme_section(25)
    for word in ("backend", "frontend", "iPhone 13", "Pixel 7", "视觉对比", "私有仓库"):
        assert word in ci, word
    backup = _readme_section(26)
    for word in ("docker compose exec", "pg_dump", "FIELD_ENCRYPTION_KEY", "残留"):
        assert word in backup, word
    # 第 4 节的加密字段清单覆盖步骤 07 至 10 新增的加密内容
    configuration = _readme_section(4)
    for word in ("对话", "模型服务的密钥", "照片", "大致区域"):
        assert word in configuration, word
