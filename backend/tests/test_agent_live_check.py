"""智能体实测脚本：用 MockTransport 驱动的模拟模型跑完整个脚本，绝不访问真实网络，也不读取真实的密钥文件。"""

import io
import json
import tempfile
from contextlib import redirect_stdout
from datetime import date, timedelta
from inspect import signature
from pathlib import Path

import httpx2
from sqlalchemy import func, select

from app.agent import live_check
from app.agent.guard import NOTICE_HEADER
from app.agent.live_check import (
    AFTER_TRAINING,
    CLUE,
    DINNER,
    INDUCEMENTS,
    RISK_QUESTIONS,
    USER_LABELS,
    ModelChoice,
    pick_models,
)
from app.agent.models import AgentConversation, AgentMessage, AgentOpening
from app.agent_grants.models import SdkCallAudit
from app.auth.models import User
from app.db import get_sessionmaker
from app.llm.adapters import make_adapter
from app.llm.models import LlmAssignment, LlmModel, LlmProvider

BACKEND = Path(__file__).resolve().parents[1]
QWEN_KEY = "sk-qwen-0123456789abcdef"
DEEPSEEK_KEY = "sk-deepseek-0123456789abcdef"
ALL_KEYS = (QWEN_KEY, DEEPSEEK_KEY)
TODAY = date.today()
PHASES = {"menstrual", "follicular", "ovulation", "luteal"}
BASE_CONFIG = f"QWEN_API_KEY={QWEN_KEY}\nQWEN_CHAT_MODEL=qwen-plus\n"
TWO_MODELS = BASE_CONFIG + f"DEEPSEEK_API_KEY={DEEPSEEK_KEY}\nDEEPSEEK_CHAT_MODEL=deepseek-chat\n"


class FakeModels:
    """按提问内容回答的模拟模型：被诱导时推荐麻婆豆腐，被要求重写时改推清蒸鱼，开场措辞原样回显问题，
    健康用户的回答里故意回显收到的密钥，检验结果文件会把它去掉。"""

    def __init__(self, bad_models: tuple[str, ...] = ()):
        self.requests: list[dict] = []
        self.bad_models = bad_models

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append({"model": body["model"], "host": request.url.host})
        messages = body["messages"]
        system = messages[0]["content"]
        last = messages[-1]["content"]
        key = request.headers["authorization"].removeprefix("Bearer ")
        if body["model"] in self.bad_models:
            return httpx2.Response(500, json={"error": {"message": f"boom {key}", "type": "server_error"}})
        if system.startswith("你是健康生活助手，现在要主动向用户开口"):
            text = "你好，" + last
        elif "重写" in last:
            text = "今晚可以吃清蒸鱼配米饭。"
        elif any(word in last for word in ("川菜", "麻婆", "能吃")):
            text = "那就吃麻婆豆腐吧，很下饭。"
        elif last == CLUE:
            text = "好的，解除医嘱需要你在应用里确认，我先帮你提出建议。"
        elif "辛辣" in system:
            text = "今晚可以吃清蒸鱼配米饭。"
        else:
            text = f"晚饭可以吃清蒸鱼配米饭，再搭配一份青菜和一碗清淡的汤，清淡又有蛋白质。（调试信息 {key}）"
        return httpx2.Response(200, json={"model": body["model"], "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                          "choices": [{"message": {"role": "assistant", "content": text},
                                                       "finish_reason": "stop"}]})


def _factory(model: FakeModels):
    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(model))

    return factory


def _run(config: str = BASE_CONFIG, model: FakeModels | None = None, factory=None) -> tuple[int, str, str, FakeModels]:
    """写临时密钥文件、运行 main，返回（退出码，结果文件正文，屏幕输出，模拟模型）；用完删除临时目录。"""
    model = model or FakeModels()
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as directory:
        keys, result = Path(directory) / "llm_keys.local.env", Path(directory) / "agent_live_result.md"
        keys.write_text(config, encoding="utf-8")
        with redirect_stdout(out):
            code = live_check.main(keys, result, factory or _factory(model), today=TODAY)
        written = result.read_text(encoding="utf-8") if result.exists() else ""
    return code, written, out.getvalue(), model


def _count(model) -> int:
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(model))


def _assert_nothing_left() -> None:
    """临时用户及其全部数据都已删除。"""
    for table in (User, AgentConversation, AgentMessage, AgentOpening, LlmProvider, LlmModel, LlmAssignment,
                  SdkCallAudit):
        assert _count(table) == 0, table.__name__


# ---------- 运行与结果结构 ----------


def test_full_run_records_every_scenario_with_the_required_fields_and_deletes_the_users():
    code, written, out, model = _run()
    assert code == 0
    _assert_nothing_left()
    assert "临时演示用户已全部删除（本次共 5 个）" in written and "临时演示用户已全部删除" in out

    assert written.startswith("# 智能体实测结果")
    assert f"运行日期：{TODAY.isoformat()}" in written and "本文件不含任何密钥" in written
    assert "使用的模型：主要：通义千问（qwen-plus）" in written
    for section in ("## 同一句“晚饭吃什么”，五类用户各问一次", "## 忌辛辣医嘱用户：三次诱导",
                    "## 健身用户：训练后吃什么", "## 医嘱待复核用户：主动开场与医生的新意见",
                    "## 风险话题：药物、严重症状、孕期异常"):
        assert section in written, section
    for label in USER_LABELS.values():
        assert f"### {label}：{DINNER}" in written, label
    for text in (*INDUCEMENTS, AFTER_TRAINING, CLUE, *RISK_QUESTIONS):
        assert f"：{text}" in written, text
    for field in ("- 模型：", "- 脚本判断：", "- 是否命中输出检查：", "- flags：", "- 调用的工具：", "- 耗时：", "回答全文：",
                  "依据段："):
        assert field in written, field
    # 五类用户晚饭 + 三次诱导 + 训练后 + 开场两次与医生的新意见 + 三个风险问题 = 15 条；没有第二家模型
    assert written.count("\n### ") == 15
    assert "第二家" not in written and {r["model"] for r in model.requests} == {"qwen-plus"}
    assert "出错 0 项" in written


def test_inducements_are_caught_by_the_output_guard_and_the_independent_recheck_passes():
    _, written, _, _ = _run()
    block = written.split("## 忌辛辣医嘱用户：三次诱导")[1].split("\n## ")[0]
    assert block.count("是，改写后通过") == 3 and "guard_rewritten" in block
    assert "引擎复核：回答里没有提到被医嘱阻断的食物" in block
    assert "按你当前生效的医嘱，以下食物不建议" in block  # 程序附上的医嘱提醒在回答全文里
    assert NOTICE_HEADER.split("{")[0] in block
    # 模型原来的推荐（麻婆豆腐）没有出现在“回答”里被当作建议：改写后是清蒸鱼
    assert "清蒸鱼" in block and "很下饭" not in block


def test_risk_questions_use_fixed_replies_without_tools_and_the_clue_is_only_a_suggestion():
    _, written, _, model = _run()
    risk = written.split("## 风险话题：药物、严重症状、孕期异常")[1]
    assert risk.count("命中风险话题") == 3 and "risk_medication" in risk and "risk_severe_symptom" in risk
    assert "risk_pregnancy" in risk and "120" in risk
    review = written.split("## 医嘱待复核用户：主动开场与医生的新意见")[1].split("\n## ")[0]
    assert "你有一条医嘱（每天少盐，复查前继续遵守）" in review  # 开场问题
    assert "拒绝之后，同一天不会再问同一类问题" in review
    assert "医嘱约束 1 条 → 1 条，没有被解除" in review and "resolution_clue" in review
    # 风险问题没有调用模型：模型一共只收到 5（晚饭）+ 3（诱导）+ 3（重写）+ 1（训练后）+ 2（两次开场措辞）+ 1（医生的新意见）次请求
    assert len(model.requests) == 5 + 3 + 3 + 1 + 2 + 1


def test_the_non_cycle_users_are_checked_for_stray_cycle_words_and_the_cycle_user_is_left_to_a_human():
    _, written, _, _ = _run()
    assert "没有经期模块的用户，回答里却出现了" not in written
    period = written.split("### 经期用户：晚饭吃什么")[1].split("\n### ")[0]
    assert "- 脚本判断：需人工判断" in period


def test_second_model_reruns_the_inducements_on_the_avoid_user():
    model = FakeModels()
    code, written, _, _ = _run(TWO_MODELS, model)
    assert code == 0
    _assert_nothing_left()
    assert "第二家：DeepSeek（deepseek-chat）" in written
    section = written.split("## 换成第二家模型：DeepSeek（deepseek-chat）（验收第 9 条）")[1]
    assert section.count("\n### ") == 4  # 晚饭加三次诱导
    assert section.count("- 模型：DeepSeek（deepseek-chat）") == 4
    assert {r["model"] for r in model.requests} == {"qwen-plus", "deepseek-chat"}
    assert {r["model"] for r in model.requests if r["host"] == "api.deepseek.com"} == {"deepseek-chat"}


def test_tools_model_is_preferred_and_providers_without_a_key_or_model_are_not_used():
    config = {"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "qwen-plus", "QWEN_TOOLS_MODEL": "qwen-max",
              "DEEPSEEK_API_KEY": DEEPSEEK_KEY, "DEEPSEEK_CHAT_MODEL": "",
              "ZHIPU_CHAT_MODEL": "glm-4-plus", "CUSTOM_API_KEY": "abcdefgh12345678", "CUSTOM_CHAT_MODEL": "x"}
    choices = pick_models(config)
    assert [(c.provider, c.model_id) for c in choices] == [("通义千问", "qwen-max")]  # 通用兼容服务没填类型，配置有误
    assert choices[0].api_key == QWEN_KEY and "sk-" not in repr(choices[0])  # repr 不显示密钥
    assert pick_models({}) == []


# ---------- 不泄露密钥、不留下用户 ----------


def test_no_key_appears_in_the_file_or_on_screen_even_when_the_model_or_an_error_echoes_it():
    model = FakeModels(bad_models=("deepseek-chat",))
    code, written, out, _ = _run(TWO_MODELS, model)
    assert code == 0
    assert "调试信息 ****" in written  # 模型回显的密钥被去掉
    assert "llm_provider_error" in written or "agent_model_error" in written  # 第二家出错，记为错误行
    for secret in ALL_KEYS:
        assert secret not in written and secret not in out
    assert "sk-" not in written.replace("sk-****", "")


def test_a_failing_model_is_recorded_per_scenario_without_stopping_the_run():
    code, written, _, _ = _run(model=FakeModels(bad_models=("qwen-plus",)))
    assert code == 0
    _assert_nothing_left()
    assert "- 脚本判断：出错" in written and "agent_model_error" in written
    assert "风险话题" in written and "命中风险话题" in written  # 风险问题不需要模型，照样通过
    assert "出错 0 项" not in written


def test_a_failing_constraint_read_is_recorded_on_the_clue_scenario_without_stopping_the_run(monkeypatch):
    def broken(self, user):
        raise RuntimeError(f"read failed with {QWEN_KEY}")

    monkeypatch.setattr(live_check._Runner, "constraint_count", broken)
    code, written, out, _ = _run()
    assert code == 0 and "运行出错" not in out
    _assert_nothing_left()
    clue = written.split(f"### {USER_LABELS['review']}：{CLUE}")[1].split("\n### ")[0]
    assert "- 脚本判断：出错" in clue and "脚本内部出错：RuntimeError" in clue
    assert "## 风险话题：药物、严重症状、孕期异常" in written  # 后面的场景照常运行
    assert QWEN_KEY not in written and QWEN_KEY not in out


def test_interrupted_run_still_deletes_the_users_and_writes_the_partial_result():
    model = FakeModels()
    ok_factory = _factory(model)
    calls = {"count": 0}

    def factory(kind, base_url, api_key):
        calls["count"] += 1
        if calls["count"] == 6:  # 跑到一半，用户按下 Ctrl+C
            raise KeyboardInterrupt
        return ok_factory(kind, base_url, api_key)

    code, written, out, _ = _run(factory=factory)
    assert code == 130
    _assert_nothing_left()
    assert "中断" in written and "中断" in out
    assert 0 < written.count("\n### ") < 15
    assert QWEN_KEY not in written and QWEN_KEY not in out


def test_setup_failure_still_deletes_the_users_that_were_created(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError(f"setup failed with {QWEN_KEY}")

    monkeypatch.setattr(live_check.workouts, "create_workout", boom)
    code, written, out, _ = _run()
    assert code == 1
    _assert_nothing_left()
    assert "运行出错：RuntimeError" in out and QWEN_KEY not in out and QWEN_KEY not in written
    assert "中断或出错" in written


def test_cleanup_failure_is_reported_with_the_prefix_and_the_exit_code_is_not_zero(monkeypatch):
    def broken(prefix):
        raise RuntimeError("db down")

    monkeypatch.setattr(live_check, "delete_users", broken)
    code, written, out, _ = _run()
    assert code == 1
    assert "警告：临时演示用户没有删除成功" in written and "live_" in out


def test_usernames_carry_a_unique_prefix_and_only_those_users_are_deleted():
    with get_sessionmaker()() as db:
        bystander = live_check.register_user(db, "live", "pass-word-123")  # 前缀相近但不是脚本建立的用户
        keep = bystander.id
    first, second = "live_aaaaaaaa_", "live_bbbbbbbb_"
    live_check.create_users(first, TODAY)
    live_check.create_users(second, TODAY)
    with get_sessionmaker()() as db:
        names = set(db.scalars(select(User.username)))
    assert {f"{first}{key}" for key in USER_LABELS} <= names and {f"{second}{key}" for key in USER_LABELS} <= names
    assert live_check.delete_users(first) == 5
    with get_sessionmaker()() as db:
        names = set(db.scalars(select(User.username)))
        assert not any(name.startswith(first) for name in names)
        assert {f"{second}{key}" for key in USER_LABELS} <= names and db.get(User, keep) is not None
    assert live_check.delete_users(second) == 5


def test_demo_users_have_the_profiles_and_data_the_scenarios_need():
    ids = live_check.create_users("live_cccccccc_", TODAY)
    try:
        from app.sdk import AgentCredential, GoodLife
        from app.sdk.tooling import agent_registry

        sdk = GoodLife(registry=agent_registry(), today=lambda: TODAY)

        def read(user, capability, params=None):
            return sdk.call(AgentCredential(ids[user]), capability, params).data

        assert [read(user, "profile.get_capabilities")["cycle"] for user in USER_LABELS] == [False, True, False, False,
                                                                                            False]
        assert read("period", "cycle.get_phase", {"day": TODAY.isoformat()})["phase"] in PHASES
        assert [c["category"] for c in read("avoid", "medical.get_constraints")["constraints"]] == ["diet_avoid"]
        assert read("healthy", "medical.get_constraints")["constraints"] == []
        week = read("fitness", "fitness.list_workouts", {"start": (TODAY - timedelta(days=7)).isoformat(),
                                                         "end": TODAY.isoformat()})
        assert len(week) == 6
        constraints = read("review", "medical.get_constraints")["constraints"]
        assert len(constraints) == 1 and constraints[0]["needs_review"] is True
        assert len(read("review", "medical.list_reviews")) == 1
    finally:
        assert live_check.delete_users("live_cccccccc_") == 5


# ---------- 入口与文件 ----------


def test_main_without_a_keys_file_or_without_any_usable_model_explains_what_to_do(capsys):
    with tempfile.TemporaryDirectory() as directory:
        missing, result = Path(directory) / "llm_keys.local.env", Path(directory) / "agent_live_result.md"
        assert live_check.main(missing, result) == 1
        assert not result.exists()
        assert "llm_keys.local.env.example" in capsys.readouterr().out
        missing.write_text("QWEN_API_KEY=\nQWEN_CHAT_MODEL=qwen-plus\n", encoding="utf-8")
        assert live_check.main(missing, result) == 1
        assert not result.exists() and "至少填好一家" in capsys.readouterr().out
    _assert_nothing_left()


def test_main_explains_a_keys_file_that_is_not_utf8(capsys):
    with tempfile.TemporaryDirectory() as directory:
        keys, result = Path(directory) / "llm_keys.local.env", Path(directory) / "agent_live_result.md"
        keys.write_bytes(f"# 注释\nQWEN_API_KEY={QWEN_KEY}\n".encode("gbk"))
        assert live_check.main(keys, result) == 1
        assert not result.exists()
    captured = capsys.readouterr()
    assert "UTF-8" in captured.out and QWEN_KEY not in captured.out + captured.err


def test_defaults_use_the_step_07_key_file_the_60_second_adapter_and_a_git_ignored_result_file():
    from app.llm import live_check as step_07

    params = signature(live_check.main).parameters
    assert params["env_path"].default == step_07.KEYS_FILE and params["factory"].default is step_07.live_adapter
    assert params["result_path"].default == BACKEND / "agent_live_result.md"
    entries = (BACKEND / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "agent_live_result.md" in entries and "llm_keys.local.env" in entries


def test_render_scrubs_keys_even_when_an_answer_carries_one():
    record = live_check.Record("场景", "用户", "模型", "问题", answer=f"密钥 {QWEN_KEY} 与 sk-abcdefghijklmnop0000\n第二行")
    text = live_check.render_markdown([record], [QWEN_KEY], [ModelChoice("通义千问", "openai_compatible", "u", QWEN_KEY, "m")],
                                      TODAY)
    assert QWEN_KEY not in text and "sk-abcdefghijklmnop0000" not in text and "****" in text
    assert "> 第二行" in text
    assert live_check.Record("a", "b", "c", "d").status == "需人工判断"
