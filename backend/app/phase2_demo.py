"""第二阶段中期检查：只用接口、不用界面，走一遍“聊天加工具加主动开场”。

用法：在后端目录运行 uv run python -m app.phase2_demo（数据库需在运行）。
没有真实的模型密钥，所以脚本自带一个按关键词回答的本地模拟模型（OpenAI 兼容的小 HTTP 服务，127.0.0.1 上的空闲端口，
结束时关闭），后端用真实的适配器通过 HTTP 去访问它。脚本会重建演示账号 demo_phase2（密码 demo-pass-123），
全程经 FastAPI 应用的真实接口（进程内的 TestClient）；确认医嘱、确认解除这两步是用户本人在应用里的操作。
"""

import json
import os
import re
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.agent.assembly import CLIENT_NAME as AGENT_CLIENT_NAME
from app.agent.guard import NOTICE_HEADER
from app.agent_grants.models import SdkCallAudit
from app.auth.models import User
from app.config import get_settings
from app.db import get_sessionmaker

DEMO_USERNAME = "demo_phase2"
DEMO_PASSWORD = "demo-pass-123"
DEMO_MODEL_KEY = "sk-demo-phase2-not-a-real-key"  # 只有本地模拟模型认这个密钥，不是任何真实服务的密钥
DEMO_MODEL_ID = "mock-agent"
PROFILE = {"gender": "female", "birth_year": 1996, "height_cm": 162, "weight_kg": 54, "activity_level": "light",
           "goal": "lose_fat"}
ORDER_TEXT = "两周内忌食辛辣。"
PERIOD_STARTED_DAYS_AGO = 40  # 只记一次过去的经期：数据不足，不会给出预测，所以“经期将至”的开场规则不会触发
PERIOD_DAYS = 5
MAPO_TOFU = "麻婆豆腐"
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NOTICE_PREFIX = NOTICE_HEADER.split("{")[0]  # 程序附在回答后面的医嘱提醒的开头


# ---------- 本地模拟模型 ----------


def _text_of(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"content": "", "tool_calls": [{"id": call_id, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}


class _ScriptedModel:
    """按用户话里的关键词给出固定回答或工具调用的 OpenAI 兼容服务；记录每次收到的请求。"""

    def __init__(self, today: date):
        self.today = today
        self.received: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def start(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)  # 端口 0：由系统分配空闲端口
        self._server.model = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def reply(self, body: dict[str, Any]) -> dict[str, Any]:
        messages = body.get("messages", [])
        tools = [tool["function"]["name"] for tool in body.get("tools", [])]
        system = _text_of(messages[0]) if messages and messages[0]["role"] == "system" else ""
        user_positions = [i for i, m in enumerate(messages) if m["role"] == "user"]
        last_user = _text_of(messages[user_positions[-1]]) if user_positions else ""
        tool_results = [m for m in messages[user_positions[-1]:] if m["role"] == "tool"] if user_positions else []
        self.received.append({"tools": tools, "last_user": last_user})
        if not tools:  # 输出检查的改写、开场措辞：不带工具
            if MAPO_TOFU in json.dumps(body, ensure_ascii=False) and any(w in last_user for w in ("改写", "不要", "重新")):
                return {"content": "今晚推荐清蒸鱼配米饭，清淡又下饭。"}
            return {"content": ""}  # 开场措辞留空：后端改用固定模板
        if "帮我记一下" in last_user and {"nutrition_search_foods", "nutrition_log_meal"} <= set(tools):
            if not tool_results:
                return _tool_call("call-s1", "nutrition_search_foods", {"query": "鸡蛋"})
            if len(tool_results) == 1:
                food_id = json.loads(_text_of(tool_results[0]))["data"]["results"][0]["id"]
                return _tool_call("call-l1", "nutrition_log_meal", {
                    "food_id": food_id, "eaten_on": self.today.isoformat(), "meal_type": "breakfast", "grams": 50})
            return {"content": "记好了"}
        if tool_results:
            return {"content": "已经按你的意思处理好了。"}
        if "医生说我好了" in last_user and "medical_propose_resolution" in tools:
            ids = UUID_PATTERN.findall(system)
            return _tool_call("call-a1", "medical_propose_resolution", {
                "item_id": ids[0] if ids else "", "reason": "用户转述医生说已经好了"})
        if "推荐川菜" in last_user:
            return {"content": "推荐麻婆豆腐，很下饭。"}
        if "晚饭吃什么" in last_user:
            return {"content": "今晚可以吃清蒸鱼配米饭，再来一份番茄炒蛋。"}
        return {"content": "好的。"}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._send(200, {"data": [{"id": DEMO_MODEL_ID}]})
        else:
            self._send(404, {"error": {"message": "Not Found"}})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.headers.get("Authorization") != f"Bearer {DEMO_MODEL_KEY}":
            self._send(401, {"error": {"message": "bad key"}})
            return
        out = self.server.model.reply(body)  # type: ignore[attr-defined]
        message: dict[str, Any] = {"role": "assistant", "content": out.get("content") or None}
        if out.get("tool_calls"):
            message["tool_calls"] = out["tool_calls"]
        finish = "tool_calls" if out.get("tool_calls") else "stop"
        self._send(200, {"id": "demo", "model": body.get("model"), "choices": [
            {"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


# ---------- 故事 ----------


@dataclass
class Step:
    title: str
    ok: bool
    lines: list[str] = field(default_factory=list)


class Story:
    def __init__(self, client: TestClient, model: _ScriptedModel, today: date):
        self.client = client
        self.model = model
        self.today = today
        self.headers: dict[str, str] = {}
        self.steps: list[Step] = []

    def api(self, method: str, path: str, expect: int | tuple[int, ...] = (200, 201, 204), **kwargs: Any) -> Any:
        response = self.client.request(method, path, headers=self.headers, **kwargs)
        allowed = (expect,) if isinstance(expect, int) else expect
        if response.status_code not in allowed:
            raise RuntimeError(f"{method} {path} 返回 {response.status_code}：{response.text[:200]}")
        if "text/event-stream" in response.headers.get("content-type", ""):
            return response.text
        return response.json() if response.content else None

    def step(self, title: str, ok: bool, *lines: str) -> None:
        self.steps.append(Step(title, ok, list(lines)))

    def chat(self, conversation_id: str, text: str) -> dict[str, Any]:
        return self.api("POST", f"/api/agent/conversations/{conversation_id}/messages",
                        json={"text": text, "stream": False})


def prepare_account() -> None:
    """只删除演示账号本身（其余数据随账号级联删除），之后由故事里的注册接口重建。"""
    with get_sessionmaker()() as db:
        db.execute(delete(User).where(User.username == DEMO_USERNAME))
        db.commit()


def run_story(story: Story) -> None:
    today = story.today
    api = story.api

    # 1 账号、档案与模型
    api("POST", "/api/auth/register", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    token = api("POST", "/api/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    story.headers = {"Authorization": f"Bearer {token['access_token']}"}
    version = api("GET", "/api/disclaimer")["version"]
    api("POST", "/api/disclaimer/accept", json={"version": version})
    api("PATCH", "/api/profile", json=PROFILE)
    caps = api("GET", "/api/me/capabilities")
    provider = api("POST", "/api/llm/providers", json={
        "name": "本地模拟模型", "kind": "openai_compatible", "base_url": story.model.base_url, "api_key": DEMO_MODEL_KEY})
    model = api("POST", f"/api/llm/providers/{provider['id']}/models", json={"model_id": DEMO_MODEL_ID})
    assignment = api("PUT", "/api/llm/assignments/chat", json={"model_id": model["id"]})
    story.step("账号、档案与模型", bool(caps["cycle"]) and assignment["model"]["model_id"] == DEMO_MODEL_ID,
               f"注册并登录 {DEMO_USERNAME}，接受免责声明 {version}，填好档案（女、1996 年生、162 厘米、54 公斤、"
               "轻度活动、减脂）；按档案开放的模块：" + "、".join(k for k, v in caps.items() if v),
               f"添加模型服务“{provider['name']}”（密钥只显示提示 {provider['key_hint']}），手动添加模型 {DEMO_MODEL_ID}，"
               "分配给日常对话")

    # 2 一次过去的经期
    start = today - timedelta(days=PERIOD_STARTED_DAYS_AGO)
    period = api("POST", "/api/cycle/periods", json={
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=PERIOD_DAYS - 1)).isoformat()})
    prediction = api("GET", "/api/cycle/prediction")
    story.step("经期：记录一次过去的经期", prediction["status"] == "insufficient_data",
               f"记录经期 {period['start_date']} 至 {period['end_date']}；只有一次记录，预测状态 {prediction['status']}，"
               "所以今天不会触发“经期将至”的开场")

    # 3 医嘱：用户本人确认
    order = api("POST", "/api/medical/orders", json={"text": ORDER_TEXT})
    pending = all(item["status"] == "pending_confirmation" for item in order["items"])
    for item in order["items"]:
        api("POST", f"/api/medical/items/{item['id']}/confirm")
    constraints = api("GET", "/api/medical/constraints")["constraints"]
    story.step("医嘱：录入并由用户本人确认", bool(order["items"]) and pending and len(constraints) == len(order["items"]),
               f"录入“{ORDER_TEXT}”，得到 {len(order['items'])} 条待确认条目",
               "（确认这一步代表用户在应用里点确认，走用户登录令牌）",
               f"当前生效的医嘱约束 {len(constraints)} 条：{[c['content'] for c in constraints]}")

    # 4 主动开场
    first = api("GET", "/api/agent/opening")["opening"]
    again = api("GET", "/api/agent/opening")["opening"]
    opening_ok = first is not None and first["kind"] == "no_meal_today" and again is not None and again["id"] == first["id"]
    lines = [f"第一次：{first['kind'] if first else None}，“{first['question'] if first else ''}”",
             f"再问一次：返回同一条（编号相同）：{bool(again and first and again['id'] == first['id'])}"]
    declined_ok = False
    if first is not None:
        api("POST", f"/api/agent/opening/{first['id']}/decline")
        after = api("GET", "/api/agent/opening")["opening"]
        declined_ok = after is None or after["kind"] != "no_meal_today"
        lines.append(f"用户拒绝后再问：{'今天没有要问的了' if after is None else after['kind']}，不再追问饮食记录")
    story.step("主动开场：规则触发、同一条不重复、拒绝后不再追问", opening_ok and declined_ok, *lines)

    conversation = api("POST", "/api/agent/conversations", json={"title": "第二阶段演示"})["id"]

    # 5 聊天加工具：记录早餐
    turn = story.chat(conversation, "帮我记一下早餐吃了一个鸡蛋")
    meals = api("GET", "/api/nutrition/meals")
    egg = [m for m in meals if "鸡蛋" in m["food_name"] and m["meal_type"] == "breakfast"]
    both = {"nutrition_search_foods", "nutrition_log_meal"} <= set(turn["tools_used"])
    story.step("聊天加工具：一句话记下早餐", both and len(egg) == 1 and egg[0]["grams"] == 50,
               f"助手回答：{turn['text'].splitlines()[0]}", f"本轮用到的工具：{turn['tools_used']}",
               f"饮食记录里有：{[(m['meal_type'], m['food_name'], m['grams']) for m in meals]}")

    # 6 带依据的回答
    turn = story.chat(conversation, "晚饭吃什么")
    story.step("聊天：回答带依据与免责", bool(turn["evidence"]) and "依据：" not in turn["text"]
               and "不能替代医生" in turn["text"] and MAPO_TOFU not in turn["text"],
               f"回答：{turn['text'].splitlines()[0]}", f"依据（原样取自引擎）共 {len(turn['evidence'].splitlines())} 行，"
               f"例如：{turn['evidence'].splitlines()[0] if turn['evidence'] else ''}",
               "回答正文里没有模型自写的“依据：”，末尾有免责声明")

    # 7 输出检查：改写
    before = len(story.model.received)
    turn = story.chat(conversation, "推荐川菜吧")
    answer_part = turn["text"].split(NOTICE_PREFIX)[0]
    notice_ok = NOTICE_PREFIX in turn["text"] and MAPO_TOFU in turn["text"].split(NOTICE_PREFIX, 1)[1]
    story.step("输出检查：被诱导推荐忌口食物时改写", "guard_rewritten" in turn["flags"] and MAPO_TOFU not in answer_part
               and notice_ok,
               f"标记 {turn['flags']}；模型本轮收到 {len(story.model.received) - before} 次请求（含一次改写）",
               f"回答部分：{answer_part.strip().splitlines()[0]}",
               f"程序附上的医嘱提醒：{NOTICE_PREFIX}{MAPO_TOFU}……")

    # 8 风险话题
    before = len(story.model.received)
    turn = story.chat(conversation, "我能不能把降压药停了")
    risk_flags = [flag for flag in turn["flags"] if flag.startswith("risk_")]
    story.step("安全边界：药物话题给固定回复、不调模型", bool(risk_flags) and len(story.model.received) == before
               and not turn["tools_used"],
               f"风险标记 {risk_flags}；模型收到的请求数不变（{before}）", f"固定回复：{turn['text'][:40]}……")

    # 9 医生说好了：只提建议，用户本人确认
    item_id = constraints[0]["item_id"]
    turn = story.chat(conversation, "医生说我好了，可以吃辣了")
    item = api("GET", f"/api/medical/items/{item_id}")
    events = api("GET", f"/api/medical/items/{item_id}/events")
    proposed = [e for e in events if e["action"] == "resolution_proposed"]
    still_active = item["status"] == "active" and item["resolution_proposed_at"] is not None
    agent_proposed = bool(proposed) and proposed[-1]["source"] == "agent"
    still_blocked = len(api("GET", "/api/medical/constraints")["constraints"]) == len(constraints)
    api("POST", f"/api/medical/items/{item_id}/resolve", json={"reason": "用户本人确认医生已同意解除"})
    after = api("GET", "/api/medical/constraints")["constraints"]
    story.step("医嘱：模型只能提建议，用户本人确认后才解除",
               "resolution_clue" in turn["flags"] and still_active and agent_proposed and still_blocked and not after,
               f"标记 {turn['flags']}，本轮工具 {turn['tools_used']}",
               f"模型提出建议后条目仍是 {item['status']}，有待处理建议，建议来源 {proposed[-1]['source'] if proposed else None}，"
               "约束照常生效",
               f"用户本人确认解除后，生效的医嘱约束 {len(after)} 条")

    # 10 解除后不再改写
    turn = story.chat(conversation, "推荐川菜吧")
    story.step("解除后：同样的问题不再被拦截", "guard_rewritten" not in turn["flags"] and NOTICE_PREFIX not in turn["text"]
               and MAPO_TOFU in turn["text"],
               f"标记 {turn['flags']}；回答：{turn['text'].splitlines()[0]}", "没有医嘱阻断，也就没有医嘱提醒")

    # 11 流式
    stream = api("POST", f"/api/agent/conversations/{conversation}/messages", json={"text": "晚饭吃什么", "stream": True})
    story.step("流式：delta 与 done 事件", "event: delta" in stream and "event: done" in stream,
               f"收到 {stream.count('event: delta')} 个 delta 事件和 {stream.count('event: done')} 个 done 事件")


def audit_lines(username: str) -> list[str]:
    with get_sessionmaker()() as db:
        user_id = db.scalar(select(User.id).where(User.username == username))
        base = select(func.count()).select_from(SdkCallAudit).where(
            SdkCallAudit.user_id == user_id, SdkCallAudit.client_name == AGENT_CLIENT_NAME)
        total = db.scalar(base)
        errors = db.scalar(base.where(SdkCallAudit.outcome == "error"))
    return [f"审计里客户端名为 {AGENT_CLIENT_NAME} 的行共 {total} 行，其中失败 {errors} 行；"
            "审计只记能力名、结果、错误码、客户端与耗时，不记任何对话内容"]


def run(today: date, out: Callable[[str], None] = print) -> bool:
    previous = os.environ.get("LLM_ALLOW_PRIVATE_HOSTS")
    os.environ["LLM_ALLOW_PRIVATE_HOSTS"] = "true"  # 模型服务地址是 127.0.0.1，必须在配置第一次读取前允许
    get_settings.cache_clear()
    model = _ScriptedModel(today)
    story: Story | None = None
    try:
        from app.main import create_app  # 在环境变量就位之后再创建应用

        prepare_account()
        model.start()
        with TestClient(create_app()) as client:
            story = Story(client, model, today)
            try:
                run_story(story)
            except Exception as err:  # 把异常记成一步未通过，仍然打印已完成的步骤
                story.step("演示中断", False, f"{type(err).__name__}：{err}")
        steps = story.steps
        audit = audit_lines(DEMO_USERNAME)
    finally:
        model.stop()
        if previous is None:
            os.environ.pop("LLM_ALLOW_PRIVATE_HOSTS", None)
        else:
            os.environ["LLM_ALLOW_PRIVATE_HOSTS"] = previous
        get_settings.cache_clear()
    out(f"第二阶段中期检查（{today.isoformat()}，账号 {DEMO_USERNAME}，密码 {DEMO_PASSWORD}）")
    for number, step in enumerate(steps, 1):
        out(f"\n{number}. [{'通过' if step.ok else '未通过'}] {step.title}")
        for line in step.lines:
            out(f"   {line}")
    for line in audit:
        out(f"\n{line}")
    passed = all(step.ok for step in steps)
    out(f"\n共 {len(steps)} 步，{'全部通过' if passed else '有未通过的步骤'}")
    return passed


def main() -> None:
    sys.exit(0 if run(date.today()) else 1)


if __name__ == "__main__":
    main()
