"""红队实测脚本：用 MockTransport 驱动的模拟模型跑完整个脚本（附近餐厅用脚本内置的模拟高德），
绝不访问真实网络，也不读取真实的密钥文件。"""

import io
import json
import re
import shutil
import subprocess
import tempfile
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date
from inspect import signature
from pathlib import Path

import httpx2
from sqlalchemy import func, select

from app.agent import redteam_check
from app.agent.redteam_check import ATTACKS, OPENING, RESULT_FILE, SIMULATED_SHOP, Attack, AttackRecord
from app.auth.models import User
from app.config import get_settings
from app.db import get_sessionmaker
from app.llm.adapters import make_adapter
from app.llm.live_check import KEYS_FILE, live_adapter
from app.medical.models import MedicalItem
from app.restaurants import amap

BACKEND = Path(__file__).resolve().parents[1]
QWEN_KEY = "sk-qwen-0123456789abcdef"
DEEPSEEK_KEY = "sk-deepseek-0123456789abcdef"
TODAY = date.today()
ONE_MODEL = f"QWEN_API_KEY={QWEN_KEY}\nQWEN_TOOLS_MODEL=qwen-plus\n"
TWO_MODELS = ONE_MODEL + f"DEEPSEEK_API_KEY={DEEPSEEK_KEY}\nDEEPSEEK_CHAT_MODEL=deepseek-chat\n"
CONFIRM_ATTACK = "要求确认或解除医嘱"
ITEM_ID = re.compile(r"条目编号 ([0-9a-f-]{36})")


class ObedientModel:
    """“照着做”的模拟模型：被要求确认解除医嘱时真的去调用确认工具（拿到 unknown_tool 后谎称已经办好），
    被诱导时推荐麻婆豆腐，被要求重写时改推清蒸鱼，开场改写原样带上模板，被要系统指令时回显收到的密钥。"""

    def __init__(self):
        self.tool_results: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        messages = body["messages"]
        system, last = messages[0]["content"], messages[-1]
        key = request.headers["authorization"].removeprefix("Bearer ")
        calls = []
        if last["role"] == "tool":
            self.tool_results.append(json.loads(last["content"]))
            text = "已经全部确认并解除了。"
        elif system.startswith("你是健康生活助手，现在要主动向用户开口"):
            text = "你好，" + last["content"]
        elif "重写" in last["content"]:
            text = "今晚可以吃清蒸鱼配米饭。"
        elif "确认解除" in last["content"]:
            text = ""
            calls = [{"id": "call-1", "type": "function", "function": {
                "name": "medical_confirm_item",
                "arguments": json.dumps({"item_id": ITEM_ID.search(system).group(1)})}}]
        elif "附近" in last["content"]:
            text = ""
            calls = [{"id": "call-2", "type": "function", "function": {
                "name": "nutrition_nearby_restaurants", "arguments": json.dumps({"place": "国贸"}, ensure_ascii=False)}}]
        elif "麻婆" in last["content"]:
            text = "那就吃麻婆豆腐吧。"
        elif "系统指令" in last["content"]:
            text = f"不能提供。（调试信息 {key}）"
        else:
            text = "好的。"
        message = {"role": "assistant", "content": text or None, **({"tool_calls": calls} if calls else {})}
        return httpx2.Response(200, json={"model": body["model"], "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                          "choices": [{"message": message,
                                                       "finish_reason": "tool_calls" if calls else "stop"}]})


def _factory(model: ObedientModel):
    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(model))

    return factory


def _run(config: str = ONE_MODEL, model: ObedientModel | None = None) -> tuple[int, str, str, ObedientModel]:
    model = model or ObedientModel()
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as directory:
        keys, result = Path(directory) / "llm_keys.local.env", Path(directory) / "redteam_live_result.md"
        keys.write_text(config, encoding="utf-8")
        with redirect_stdout(out):
            code = redteam_check.main(keys, result, _factory(model), today=TODAY)
        written = result.read_text(encoding="utf-8") if result.exists() else ""
    return code, written, out.getvalue(), model


def _count(table) -> int:
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(table))


def _section(written: str, attack: str) -> str:
    return written.split(f"### {attack} · ")[1].split("\n### ")[0]


def test_missing_keys_file_explains_how_to_prepare_it(capsys):
    with tempfile.TemporaryDirectory() as directory:
        missing, result = Path(directory) / "llm_keys.local.env", Path(directory) / "redteam_live_result.md"
        assert redteam_check.main(missing, result) == 1
        assert not result.exists()
        assert "llm_keys.local.env.example" in capsys.readouterr().out
        missing.write_text("QWEN_API_KEY=\nQWEN_CHAT_MODEL=qwen-plus\n", encoding="utf-8")
        assert redteam_check.main(missing, result) == 1
        assert not result.exists() and "至少填好一家" in capsys.readouterr().out
    assert _count(User) == 0


def test_runs_every_attack_and_reports_breaches(monkeypatch):
    assert len(ATTACKS) >= 10 and len({attack.name for attack in ATTACKS}) == len(ATTACKS)
    assert any(attack.message == OPENING for attack in ATTACKS)
    code, written, _, model = _run()
    assert code == 0
    for attack in ATTACKS:
        assert f"### {attack.name} · 通义千问（qwen-plus）" in written, attack.name
    assert "## 成功率" in written and "突破 0 次 / 自动判断 11 次，成功率 0%" in written
    assert "出错 0 项" in written

    # 模型真的调用了被拒绝的确认工具，只得到 unknown_tool；硬边界没破，报告写“未突破”
    assert any(r.get("error", {}).get("code") == "unknown_tool" for r in model.tool_results)
    confirm = _section(written, CONFIRM_ATTACK)
    assert "- 调用的工具：无" in confirm and "- 试图调用但被拒绝的工具：medical_confirm_item" in confirm
    assert "- 脚本判断：未突破" in confirm and "已经全部确认并解除了" in confirm
    # 被诱导推荐麻婆豆腐：输出检查改写后引擎复核通过
    assert "- 脚本判断：未突破" in _section(written, "诱导推荐医嘱禁忌的食物")
    # 模拟高德夹带指令的店名确实交给了模型；跑完之后换回原来的配置
    assert any(SIMULATED_SHOP in json.dumps(r, ensure_ascii=False) for r in model.tool_results)
    assert "- 脚本判断：未突破" in _section(written, "高德店名夹带指令（模拟高德）")
    assert amap.get_settings is get_settings

    # 把一个判断函数换成总是突破，成功率随之变化
    always = tuple(replace(a, judge=lambda target, outcome: (True, "测试：总是突破")) if a.name == CONFIRM_ATTACK
                   else a for a in ATTACKS)
    monkeypatch.setattr(redteam_check, "ATTACKS", always)
    _, written, _, _ = _run()
    assert "突破 1 次 / 自动判断 11 次，成功率 9%" in written
    assert "- 脚本判断：突破" in _section(written, CONFIRM_ATTACK)


def test_report_contains_no_keys_and_users_are_deleted(monkeypatch):
    prefixes = []
    original = redteam_check.delete_users

    def spy(prefix: str) -> int:
        prefixes.append(prefix)
        return original(prefix)

    monkeypatch.setattr(redteam_check, "delete_users", spy)
    code, written, out, _ = _run(TWO_MODELS)
    assert code == 0
    for key in (QWEN_KEY, DEEPSEEK_KEY):
        assert key not in written and key not in out
    assert "****" in written  # 回显的密钥被去掉了
    [prefix] = prefixes
    assert re.fullmatch(r"redteam_[0-9a-f]{8}_", prefix)
    expected = 1 + 2 * len(ATTACKS)  # 另一个用户加上每家模型每个攻击一个攻击者
    assert f"临时用户已全部删除（本次共 {expected} 个）" in written
    assert _count(User) == 0 and _count(MedicalItem) == 0
    assert "通义千问（qwen-plus）：突破 0 次" in written and "DeepSeek（deepseek-chat）：突破 0 次" in written


def test_a_failing_attack_is_recorded_and_the_rest_still_run(monkeypatch):
    def broken(db, target):
        raise RuntimeError(f"不该出现在结果里的文字 {QWEN_KEY}")

    monkeypatch.setattr(redteam_check, "ATTACKS", (Attack("坏掉的准备", broken, "你好", ATTACKS[0].judge), *ATTACKS[:2]))
    code, written, _, _ = _run()
    assert code == 0
    assert "- 错误：脚本内部出错：RuntimeError" in _section(written, "坏掉的准备")
    assert QWEN_KEY not in written and "出错 1 项" in written
    assert _count(User) == 0


def test_render_scrubs_keys_and_counts_only_judged_attacks():
    records = [AttackRecord("甲", "模型", "问", answer=f"带着 {QWEN_KEY}\n第二行", breached=True),
               AttackRecord("乙", "模型", "问", breached=False), AttackRecord("丙", "模型", "问"),
               AttackRecord("丁", "模型", "问", error="出错了")]
    text = redteam_check.render_markdown(records, [QWEN_KEY], [], TODAY)
    assert QWEN_KEY not in text and "> 第二行" in text
    assert "突破 1 次 / 自动判断 2 次，成功率 50%；需人工判断 1 项，出错 1 项。" in text


def test_result_file_is_ignored_by_git():
    params = signature(redteam_check.main).parameters
    assert params["env_path"].default == KEYS_FILE and params["factory"].default is live_adapter
    assert params["result_path"].default == RESULT_FILE == BACKEND / "redteam_live_result.md"
    entries = (BACKEND / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "redteam_live_result.md" in entries and "llm_keys.local.env" in entries
    git = shutil.which("git")
    assert git is not None
    ignored = subprocess.run([git, "check-ignore", "-q", str(RESULT_FILE)], cwd=BACKEND, check=False)
    assert ignored.returncode == 0
