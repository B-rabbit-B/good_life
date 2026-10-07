"""第一阶段整体演示：不经过任何界面，用通用 MCP 客户端走一遍“经期 + 医嘱 + 饮食 + 健身”。

用法：在后端目录运行 uv run python -m app.phase1_demo（数据库需在运行）。
脚本会重建演示账号 demo_phase1（密码 demo-pass-123）并签发一个读写授权，然后以子进程方式启动 MCP 服务，
通过标准输入输出逐步调用工具。只有“确认医嘱”一步代表用户本人在应用里的操作，走 SDK 的用户登录令牌。
"""

import asyncio
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sqlalchemy import delete, select

from app.agent_grants import service as grants
from app.auth.models import User
from app.auth.service import register_user
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.mcp_server.server import CLIENT_NAME_ENV, TOKEN_ENV
from app.profile.service import update_profile
from app.sdk import GoodLife, UserAccessToken
from app.security.tokens import create_access_token

DEMO_USERNAME = "demo_phase1"
DEMO_PASSWORD = "demo-pass-123"
CLIENT_NAME = "第一阶段演示"
PROFILE = {"gender": "female", "birth_year": 1996, "height_cm": 162, "weight_kg": 54, "activity_level": "light",
           "goal": "lose_fat"}
ORDER_TEXT = "两周内忌食辛辣、生冷食物，避免剧烈运动。"
CYCLE_STARTS_DAYS_AGO = (87, 59, 31, 2)  # 最近一次经期从前天开始、尚未结束，所以今天处于月经期
PERIOD_DAYS = 5
BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass
class Step:
    title: str
    ok: bool
    lines: list[str] = field(default_factory=list)


def prepare_account(today: date) -> tuple[str, str]:
    """重建演示账号：注册、确认免责声明、填写档案、签发读写授权。返回（授权令牌，登录令牌）。"""
    with get_sessionmaker()() as db:
        db.execute(delete(User).where(User.username == DEMO_USERNAME))
        db.commit()
        user = register_user(db, DEMO_USERNAME, DEMO_PASSWORD)
        disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
        update_profile(db, user.id, PROFILE)
        _, grant_token = grants.create_grant(db, user.id, CLIENT_NAME, "read_write", 1, grants.now())
        user = db.scalar(select(User).where(User.id == user.id))
        return grant_token, create_access_token(user.id, user.token_version)


class Story:
    def __init__(self, session: ClientSession, login_token: str, today: date):
        self.session = session
        self.login_token = login_token
        self.today = today
        self.steps: list[Step] = []

    async def tool(self, name: str, args: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
        result = await self.session.call_tool(name, args or {})
        return result.is_error, result.structured_content

    async def data(self, name: str, args: dict[str, Any] | None = None) -> Any:
        is_error, body = await self.tool(name, args)
        if is_error:
            raise RuntimeError(f"{name} 失败：{body['error']['code']} {body['error']['message']}")
        return body["data"]

    async def food_id(self, query: str) -> str:
        return (await self.data("nutrition_search_foods", {"query": query}))["results"][0]["id"]

    def step(self, title: str, ok: bool, *lines: str) -> None:
        self.steps.append(Step(title, ok, list(lines)))

    def day(self, days_ago: int) -> str:
        return (self.today - timedelta(days=days_ago)).isoformat()


def _reasons(evaluation: dict[str, Any], source: str) -> list[str]:
    return [r["message"] for r in evaluation["reasons"] if r["source"] == source]


async def run_story(story: Story) -> None:
    tools = (await story.session.list_tools()).tools
    caps = await story.data("profile_get_capabilities")
    story.step("连接与能力", len(tools) == 26 and caps["cycle"],
               f"通用 MCP 客户端连上服务，看到 {len(tools)} 个工具；按档案开放的模块：{caps}")

    for days_ago in CYCLE_STARTS_DAYS_AGO:
        end = None if days_ago < PERIOD_DAYS else story.day(days_ago - PERIOD_DAYS + 1)
        await story.data("cycle_record_period", {"start_date": story.day(days_ago), "end_date": end})
    prediction = await story.data("cycle_get_prediction")
    phase = await story.data("cycle_get_phase")
    tips = await story.data("cycle_get_tips")
    story.step("经期：记录与预测", prediction["status"] == "ok" and phase["phase"] == "menstrual",
               f"记录了 {len(CYCLE_STARTS_DAYS_AGO)} 次经期；预测下次 {prediction['next_period_start']}，"
               f"排卵日 {prediction['ovulation_day']}", f"今天处于 {phase['phase']}，第 {phase['cycle_day']} 天；"
               f"阶段提示 {len(tips['tips'])} 条，例如“{tips['tips'][0]['title']}”")

    order = await story.data("medical_submit_order", {"text": ORDER_TEXT})
    pending = [(i["category"], i["subjects"], i["status"]) for i in order["items"]]
    story.step("医嘱：模型录入，只生成待确认条目", all(s == "pending_confirmation" for *_, s in pending),
               f"录入“{ORDER_TEXT}”，得到 {len(pending)} 条待确认条目：{pending}")
    is_error, denied = await story.tool("medical_confirm_item", {"item_id": order["items"][0]["id"]})
    story.step("医嘱：模型无法确认", is_error and denied["error"]["code"] == "unknown_capability",
               f"调用确认工具被拒绝：{denied['error']['code']}，{denied['error']['message']}")
    sdk = GoodLife(today=lambda: story.today)
    for item in order["items"]:
        sdk.call(UserAccessToken(story.login_token), "medical.confirm_item", {"item_id": item["id"]},
                 client_name="用户本人在应用里确认")
    constraints = await story.data("medical_get_constraints")
    story.step("医嘱：用户本人确认后生效", len(constraints["constraints"]) == len(order["items"]),
               "（这一步代表用户在应用里点确认，走用户登录令牌，不是模型）",
               f"当前生效的医嘱约束 {len(constraints['constraints'])} 条")

    spicy = await story.data("nutrition_evaluate_food", {"food_id": await story.food_id("麻婆豆腐"), "grams": 200})
    melon = await story.data("nutrition_evaluate_food", {"food_id": await story.food_id("西瓜"), "grams": 200})
    egg = await story.data("nutrition_evaluate_food", {"food_id": await story.food_id("鸡蛋"), "grams": 50})
    story.step("饮食：多约束融合判断",
               spicy["conclusion"] == "not_recommended" and melon["conclusion"] == "not_recommended"
               and egg["conclusion"] in ("suitable", "caution"),
               f"麻婆豆腐：{spicy['conclusion']}，医嘱依据：{_reasons(spicy, 'medical')[:1]}",
               f"西瓜：{melon['conclusion']}，医嘱依据 {len(_reasons(melon, 'medical'))} 条、"
               f"经期提示 {len(_reasons(melon, 'cycle'))} 条", f"鸡蛋：{egg['conclusion']}")

    for meal_type, query, grams in (("breakfast", "鸡蛋", 50), ("lunch", "米饭", 150), ("lunch", "番茄炒蛋", 200)):
        await story.data("nutrition_log_meal", {"eaten_on": story.today.isoformat(), "meal_type": meal_type,
                                                "food_id": await story.food_id(query), "grams": grams})
    before = await story.data("nutrition_get_daily_summary")
    story.step("饮食：记录与当日汇总", before["total"]["energy_kcal"] > 0,
               f"记录早餐与午餐 3 项，已摄入 {before['total']['energy_kcal']} 千卡；"
               f"当日需求 {before['needs']['energy_kcal']} 千卡")

    walk = await story.data("fitness_search_exercises", {"query": "快走"})
    run = await story.data("fitness_search_exercises", {"query": "跑步"})
    easy = await story.data("fitness_log_workout", {"performed_on": story.today.isoformat(), "rpe": 4, "cardio": [
        {"exercise_id": walk["results"][0]["id"], "duration_minutes": 40, "rpe": 4}]})
    hard = await story.data("fitness_log_workout", {"performed_on": story.today.isoformat(), "rpe": 8, "cardio": [
        {"exercise_id": run["results"][0]["id"], "duration_minutes": 20, "rpe": 8}]})
    signal = await story.data("fitness_get_training_signal")
    story.step("健身：记录训练与运动限制冲突提示",
               not easy["conflicts"] and any(c["level"] == "conflict" for c in hard["conflicts"])
               and signal["trained"] and signal["energy_low"],
               f"快走 40 分钟（轻度）：冲突 {len(easy['conflicts'])} 条",
               f"跑步 20 分钟（高强度）：{hard['conflicts'][0]['message'] if hard['conflicts'] else '无冲突'}",
               f"今日训练信号：强度 {signal['intensity']}，估算消耗 {signal['energy_low']} 至 {signal['energy_high']} 千卡"
               f"（{signal['disclaimer'][:12]}…）")

    after = await story.data("nutrition_get_daily_summary")
    rice = await story.data("nutrition_evaluate_food", {"food_id": await story.food_id("米饭"), "grams": 150})
    story.step("联动：训练改变饮食额度与判断",
               after["needs"]["energy_kcal"] == before["needs"]["energy_kcal"] + signal["energy_low"]
               and any("训练" in m for m in _reasons(rice, "training")),
               f"当日需求 {before['needs']['energy_kcal']} → {after['needs']['energy_kcal']} 千卡（只加估算下限）",
               f"米饭的训练依据：{_reasons(rice, 'training')[:2]}")

    item_id = constraints["constraints"][0]["item_id"]
    proposed = await story.data("medical_propose_resolution", {"item_id": item_id, "reason": "复诊时医生说可以恢复"})
    story.step("医嘱：模型只能提出解除建议", proposed["status"] == "active" and proposed["resolution_proposed_at"],
               f"提出建议后条目仍为 {proposed['status']}，等待用户本人确认解除")


def print_audit(user_id: Any) -> list[str]:
    from app.agent_grants.service import list_audits

    with get_sessionmaker()() as db:
        rows = list_audits(db, user_id, 200)
    errors = [r for r in rows if r.outcome == "error"]
    return [f"审计共 {len(rows)} 行，其中失败 {len(errors)} 行（{sorted({r.error_code for r in errors})}）；"
            "审计只记能力名、结果、错误码、客户端与耗时，不记参数和返回内容"]


async def run(today: date, out: Callable[[str], None] = print) -> bool:
    grant_token, login_token = prepare_account(today)
    env = {**os.environ, TOKEN_ENV: grant_token, CLIENT_NAME_ENV: CLIENT_NAME}
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND_DIR), env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        story = Story(session, login_token, today)
        await run_story(story)
    with get_sessionmaker()() as db:
        user_id = db.scalar(select(User.id).where(User.username == DEMO_USERNAME))
    out(f"第一阶段整体演示（{today.isoformat()}，账号 {DEMO_USERNAME}，密码 {DEMO_PASSWORD}）")
    for number, step in enumerate(story.steps, 1):
        out(f"\n{number}. [{'通过' if step.ok else '未通过'}] {step.title}")
        for line in step.lines:
            out(f"   {line}")
    for line in print_audit(user_id):
        out(f"\n{line}")
    passed = all(step.ok for step in story.steps)
    out(f"\n共 {len(story.steps)} 步，{'全部通过' if passed else '有未通过的步骤'}")
    return passed


def main() -> None:
    sys.exit(0 if asyncio.run(run(date.today())) else 1)


if __name__ == "__main__":
    main()
