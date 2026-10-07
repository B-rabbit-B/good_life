# 步骤 05 健身模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 记录力量与有氧训练，给出训练量、动作进步趋势与能量消耗估算（区间、标为估算），输出"今日训练信号"并接入步骤 04 的约束引擎，让训练日与休息日的饮食判断明显不同；医嘱中有运动限制时，记录与联动建议都提示冲突。满足 `docs/05-健身模块.md` 的 7 条验收标准。

**Architecture:** 新增 `app/fitness` 包。内置动作库是只读数据文件（与营养库同样的做法），用户自定义动作入库且只对本人可见；`calc.py` 是纯函数（训练量、强度分档、能量估算、趋势）；`conflicts.py` 是纯函数（医嘱运动限制与训练的匹配）；`signals.py` 组装今日训练信号；`app/nutrition` 的上下文读取训练信号：训练日把估算消耗下限计入能量额度，引擎新增"训练"来源的软约束与冲突提示。饮食结论仍只由步骤 04 的引擎给出。

**Tech Stack:** 沿用前面步骤：Python 3.12、FastAPI、SQLAlchemy 2、PostgreSQL 16、Alembic、pytest、httpx2。

**Spec:** `docs/05-健身模块.md`（总览见 `docs/00-总览与串联.md`）

## Global Constraints

- 运行平台是 Windows 11，终端是 PowerShell 5.1（不支持 `&&`）；也可以用 Bash 工具。
- 所有后端命令都在 `E:\workspace\good-life\backend` 目录下执行，统一用 `uv run ...`；完整测试用 `uv run pytest -q -W error`，必须零失败、零警告。
- 数据库地址用 `127.0.0.1:5433`，测试库 `goodlife_test`。
- 统一错误格式：`{"error": {"code": "<机器可读码>", "message": "<中文提示>"}}`，业务错误一律抛 `app.errors.AppError`。
- 每张业务表都必须有 `user_id` 列；查询统一从 `owned_by` 开始；按编号取单条记录用 `get_owned_or_404`。内置动作库不入库。
- 任何接口都不接受客户端传入的 user_id；请求模型一律 `extra="forbid"`。
- 所有 `/api/fitness/*` 接口依赖 `require_fitness_user`（内部依赖 `require_disclaimer_user`）；是否开放只由 `compute_capabilities` 判断。
- "今天"一律通过依赖 `get_today` 取得；服务层需要日期的函数显式接收 `today`；训练日期不能晚于今天。
- 读取医嘱只能通过 `app.medical.items.get_current_constraints`；读取档案用 `get_or_create_profile`。
- 健身模块只输出"信号"，不得自己给饮食结论；饮食结论只由 `app.nutrition.engine` 给出。
- 所有能量消耗估算都给出区间并标注"仅为估算"。
- 训练备注加密存储；动作、组数、重量、次数、时长等数值明文存储（汇总与趋势需要计算）。
- 计算必须确定性：同样输入同样输出，输出列表按固定规则排序。
- 模型与迁移必须一致；新迁移接在 `0009_meal_entries_day_index` 之后，revision 编号不超过 32 个字符。
- 提交信息以如下一行结尾：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（不要替换成你自己的模型名）；不得提交 `backend/.env` 与 `.superpowers/`。
- 交付文档（`docs/05-交付物/` 下）不得出现代码、命令、反引号或代码块。

## 关键决策

| 决策 | 内容 | 理由 |
|---|---|---|
| 训练消耗计入额度 | 用户选定：训练日把"估算消耗区间的下限"加进当天能量额度（目标、范围下限、范围上限都加），汇总与判断里写明加了多少 | 用户选定，偏保守 |
| 内置动作库 | 只读数据文件，约 40 个常见力量动作、15 个常见有氧动作，自己整理；能量代谢当量（MET）参照公开的身体活动代谢当量表（Compendium of Physical Activities）的常见取值并标为近似 | 规格要求自己整理、不拷贝 wger 数据 |
| 自定义动作 | 入库，只对本人可见，编号形如 custom:<编号> | 规格 |
| 训练量口径 | 每组"重量（千克）× 次数"累加；自重动作重量记 0、不计入训练量，另计"总次数"；肌群训练量把该动作的训练量完整计入它的每个主要肌群 | 固定、可手算 |
| 主观强度分档 | 1 至 4 轻度、5 至 7 中等、8 至 10 高强度；未填按中等 | 简单、可解释 |
| 能量估算 | 千卡 = MET × 体重（千克）× 小时；力量训练的 MET 按强度取 3.5、5.0、6.0；有氧按动作在三个强度下的 MET；区间为估算值的 80% 至 120%；没有体重时不估算并说明 | 常用口径，误差大所以给区间 |
| 力量训练时长 | 填了整次训练时长时：力量部分 = 总时长 − 有氧时长（不小于 0）；没填时按每组 40 秒加组间休息（未填按 90 秒）估算 | 规格只要求粗略估算 |
| 联动信号 | 今天是否训练、训练类型、最高强度档、估算消耗区间、涉及肌群、与医嘱的冲突；引擎新增"训练"来源：力量训练日对高蛋白给正面依据，中等及以上强度对快碳给正面依据，休息日不产生训练依据 | 规格：训练日与休息日明显不同 |
| 医嘱运动限制 | 运动限制医嘱的涉及对象按词汇表对应到训练特征（任何训练、高强度、负重、跑步、游泳、弯腰、跳跃）；对不上的说法给"无法判断，请自行核对"；冲突只提示，不阻止记录 | 规格：提示冲突 |

## 文件结构

```
backend/app/fitness/
├── __init__.py
├── data/exercises.json         # 内置动作库（任务 1）
├── data/limit_terms.json       # 运动限制说法词汇表（任务 4）
├── library.py                  # 动作库加载、检索（任务 1），合并自定义动作（任务 2）
├── calc.py                     # 纯计算：训练量、强度、能量估算、趋势（任务 3）
├── models.py                   # custom_exercises、workouts、strength_sets、cardio_entries（任务 2）
├── workouts.py                 # 训练与自定义动作的读写（任务 2）
├── summaries.py                # 周汇总与动作趋势（任务 3）
├── conflicts.py                # 医嘱运动限制匹配（任务 4）
├── signals.py                  # 今日训练信号（任务 4）
├── schemas.py、deps.py、router.py   # 任务 2 建，任务 3、4 追加
└── demo.py                     # 任务 6
backend/app/nutrition/          # 任务 5 修改：needs、engine、context、schemas、data/soft_rules.json
backend/migrations/versions/0010_fitness.py
backend/tests/test_fitness_*.py
docs/05-交付物/                  # 任务 6
```

---

### Task 1: 内置动作库与检索

**Files:**
- Create: `backend/app/fitness/__init__.py`, `backend/app/fitness/library.py`, `backend/app/fitness/data/exercises.json`
- Test: `backend/tests/test_fitness_library.py`

**Interfaces:**
- Produces（`app.fitness.library`）:
  - 常量 `MUSCLES`（chest、back、shoulders、biceps、triceps、quads、hamstrings、glutes、calves、core、full_body）、`EQUIPMENT`（barbell、dumbbell、machine、cable、bodyweight、kettlebell、band、none、other）、`KINDS`（strength、cardio）、`EXERCISE_TRAITS`（high_impact、running、swimming、bending、jumping、cycling）、`STRENGTH_MET = {"light": 3.5, "moderate": 5.0, "vigorous": 6.0}`、`MET_SOURCE_NOTE`
  - 数据类 `Exercise(id, name, aliases, kind, primary_muscles, equipment, traits, met: tuple[float, float, float] | None, custom: bool)`（frozen；met 为有氧动作在轻度、中等、高强度下的 MET，力量动作为 None）、`ExerciseHit(exercise, match)`
  - `ExerciseLibrary(exercises)`：`get(exercise_id)`、`search(query, extra=(), limit=20) -> list[ExerciseHit]`（extra 为本人的自定义动作，一并参与检索）
  - `load_library() -> ExerciseLibrary`（带缓存）
- 检索规则与营养库相同的思路：`exact_name`、`exact_alias`、`prefix`、`contains`、`query_contains`（查询包含长度不少于 2 的名称或别名）；同一档内内置动作在前、名称短在前、按编号；查询为空或匹配不上返回空列表。

`exercises.json` 格式：列表，每项 `{"id": "<小写英文与下划线>", "name", "aliases": [], "kind": "strength|cardio", "primary_muscles": [...], "equipment", "traits": [...], "met": [轻, 中, 高] 或 null}`，内置编号对外为 `ex:<id>`。至少包含：
- 力量：卧推、上斜卧推、哑铃卧推、哑铃飞鸟、俯卧撑、双杠臂屈伸、深蹲、前蹲、腿举、箭步蹲、保加利亚分腿蹲、硬拉、罗马尼亚硬拉、臀推、腿弯举、腿屈伸、提踵、引体向上、高位下拉、杠铃划船、哑铃划船、坐姿划船、推举（站姿杠铃推举）、哑铃推举、侧平举、面拉、杠铃弯举、哑铃弯举、锤式弯举、绳索下压、仰卧臂屈伸、平板支撑、卷腹、悬垂举腿、俄罗斯转体、壶铃摇摆、山羊挺身、农夫行走（不少于 38 个）。硬拉、罗马尼亚硬拉、杠铃划船、壶铃摇摆、山羊挺身带 bending；跳跃类带 jumping。
- 有氧：跑步、慢跑、快走、散步、跑步机、椭圆机、动感单车（室内骑行）、骑自行车、游泳、跳绳、划船机、爬楼梯、登山、开合跳、波比跳、HIIT（不少于 15 个）；跑步、慢跑、跑步机带 running，游泳带 swimming，跳绳、开合跳、波比跳带 jumping 与 high_impact，骑行类带 cycling。
- 有氧 MET 取值参照身体活动代谢当量表的常见值（例如跑步约 6.0、8.0、10.0，快走约 3.5、4.3、5.0，游泳约 5.8、7.0、9.8），在 `MET_SOURCE_NOTE` 中说明来源与"近似值，仅用于粗略估算"。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_fitness_library.py`
```python
from app.fitness.library import EQUIPMENT, KINDS, MUSCLES, Exercise, load_library


def test_library_loads_and_is_well_formed():
    library = load_library()
    exercises = list(library.exercises.values())
    assert sum(e.kind == "strength" for e in exercises) >= 38
    assert sum(e.kind == "cardio" for e in exercises) >= 15
    ids = [e.id for e in exercises]
    assert len(ids) == len(set(ids))
    for exercise in exercises:
        assert exercise.id.startswith("ex:")
        assert exercise.kind in KINDS
        assert exercise.equipment in EQUIPMENT
        assert exercise.primary_muscles and set(exercise.primary_muscles) <= set(MUSCLES)
        if exercise.kind == "cardio":
            light, moderate, vigorous = exercise.met
            assert 0 < light <= moderate <= vigorous
        else:
            assert exercise.met is None


def test_search_exact_alias_and_not_found():
    library = load_library()
    first = library.search("卧推")[0]
    assert (first.exercise.name, first.match) == ("卧推", "exact_name")
    assert library.search("杠铃卧推")[0].exercise.id == first.exercise.id
    assert library.search("今天练了深蹲")[0].exercise.name == "深蹲"
    assert library.search("完全不存在的动作") == []
    assert library.search("  ") == []
    assert [h.exercise.id for h in library.search("推")] == [h.exercise.id for h in library.search("推")]


def test_traits():
    library = load_library()
    by_name = {e.name: e for e in library.exercises.values()}
    assert "bending" in by_name["硬拉"].traits
    assert "running" in by_name["跑步"].traits
    assert "swimming" in by_name["游泳"].traits
    assert {"jumping", "high_impact"} <= set(by_name["跳绳"].traits)


def test_custom_exercises_join_the_search():
    library = load_library()
    custom = Exercise(
        id="custom:abc", name="我的特色推", aliases=(), kind="strength", primary_muscles=("chest",),
        equipment="other", traits=(), met=None, custom=True,
    )
    hits = library.search("我的特色推", extra=(custom,))
    assert hits[0].exercise.id == "custom:abc"
    assert library.search("我的特色推") == []
```

- [ ] **Step 2: 运行确认失败**：`uv run pytest tests/test_fitness_library.py -q`，FAIL（模块不存在）。

- [ ] **Step 3: 实现**：编写 `exercises.json` 与 `library.py`（pydantic 校验数据文件，`extra="forbid"`；编号唯一、肌群与器械与特征取值合法、有氧必须有 met、力量必须没有 met；违反时抛 `ValueError` 并指出哪一项）。别名至少覆盖：杠铃卧推（卧推）、平板卧推、哑铃卧推、杠铃深蹲（深蹲）、传统硬拉（硬拉）、站姿推举、引体、下拉、二头弯举、三头下压、慢跑、快步走、跑步机跑步、单车、骑车、蛙泳、自由泳。

- [ ] **Step 4: 运行确认通过**：`uv run pytest tests/test_fitness_library.py -v`，然后 `uv run pytest -q -W error`。

- [ ] **Step 5: 提交**：`git add backend/app/fitness backend/tests/test_fitness_library.py`，`git commit -m "feat(fitness): add built-in exercise library with search"`

---

### Task 2: 数据表、自定义动作、训练记录与接口

**Files:**
- Create: `backend/app/fitness/models.py`, `workouts.py`, `schemas.py`, `deps.py`, `router.py`
- Create: `backend/migrations/versions/0010_fitness.py`
- Modify: `backend/app/fitness/library.py`（`exercise_from_custom(row) -> Exercise`）、`backend/app/models.py`、`backend/app/main.py`、`backend/tests/test_route_guards.py`
- Test: `backend/tests/test_fitness_workouts.py`

**Interfaces:**
- Produces:
  - ORM：`CustomExercise`（表 custom_exercises：id、user_id、name、aliases（JSONB）、kind、primary_muscles（JSONB）、equipment、traits（JSONB）、met_light、met_moderate、met_vigorous（可空，有氧必填）、created_at，`(user_id, name)` 唯一）、`Workout`（表 workouts：id、user_id、performed_on、duration_minutes（可空）、rpe（可空，1 至 10）、note（加密，可空）、created_at、updated_at）、`StrengthSet`（表 strength_sets：id、user_id、workout_id（外键级联、索引）、exercise_id、exercise_name、position、set_index、weight_kg、reps、rest_seconds（可空）、rpe（可空））、`CardioEntry`（表 cardio_entries：id、user_id、workout_id（外键级联、索引）、exercise_id、exercise_name、position、duration_minutes、distance_km（可空）、rpe（可空））
  - `app.fitness.workouts`：`resolve_exercise(db, user_id, exercise_id) -> Exercise`（内置或本人的自定义，否则 404 `exercise_not_found`）、`user_custom_exercises(db, user_id) -> tuple[Exercise, ...]`、`create_custom_exercise(db, user_id, fields)`、`delete_custom_exercise(db, user_id, exercise_id)`、`create_workout(db, user_id, payload, today) -> Workout`、`replace_workout(db, user_id, workout_id, payload, today)`、`delete_workout(db, user_id, workout_id)`、`get_workout(db, user_id, workout_id)`、`list_workouts(db, user_id, start, end)`、`workout_detail(db, user_id, workout) -> WorkoutDetail`（含按动作分组的力量组与有氧条目，按 position、set_index 排序）
  - `require_fitness_user`；接口（前缀 `/api/fitness`）：GET `/exercises/search?q=`、GET `/exercises/{exercise_id}`、POST `/exercises`（201，自定义）、GET `/exercises/custom`、DELETE `/exercises/custom/{exercise_id}`（204）、POST `/workouts`（201）、GET `/workouts?start=&end=`（默认最近 7 天）、GET `/workouts/{workout_id}`、PUT `/workouts/{workout_id}`（整条替换）、DELETE `/workouts/{workout_id}`（204）
  - 错误码：`exercise_not_found`(404)、`workout_in_future`(422)、`custom_exercise_exists`(409)、`fitness_not_available`(403)、`empty_workout`(422)

训练请求体：`{"performed_on", "duration_minutes"?（1 至 600）, "rpe"?（1 至 10）, "note"?（不超过 500 字）, "strength": [{"exercise_id", "sets": [{"weight_kg"（0 至 500）, "reps"（1 至 100）, "rest_seconds"?（0 至 900）, "rpe"?}]（1 至 30 组）}], "cardio": [{"exercise_id", "duration_minutes"（1 至 600）, "distance_km"?（0 至 300）, "rpe"?}]}`；strength 与 cardio 至少有一项非空，否则 `empty_workout`；力量条目只能引用 kind 为 strength 的动作，有氧条目只能引用 cardio 动作（否则 422 `exercise_kind_mismatch`）。动作名称在记录时存快照。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_fitness_workouts.py`
```python
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 10, 7)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _ex(client, headers, name):
    return client.get("/api/fitness/exercises/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _bench_workout(client, headers, day="2026-10-07", sets=((60, 10), (60, 8), (65, 6))):
    body = {
        "performed_on": day, "rpe": 7, "note": "胸部日",
        "strength": [{"exercise_id": _ex(client, headers, "卧推"),
                      "sets": [{"weight_kg": w, "reps": r} for w, r in sets]}],
        "cardio": [],
    }
    response = client.post("/api/fitness/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_record_bench_press_workout(client):
    headers = ready_user(client, "alice")
    workout = _bench_workout(client, headers)
    [block] = workout["strength"]
    assert block["exercise_name"] == "卧推"
    assert [(s["set_index"], s["weight_kg"], s["reps"]) for s in block["sets"]] == [(1, 60, 10), (2, 60, 8), (3, 65, 6)]
    assert workout["note"] == "胸部日"
    fetched = client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).json()
    assert fetched == workout


def test_workout_validation(client):
    headers = ready_user(client, "alice")
    bench = _ex(client, headers, "卧推")
    run = _ex(client, headers, "跑步")
    cases = [
        ({"performed_on": "2026-10-08", "strength": [{"exercise_id": bench, "sets": [{"weight_kg": 60, "reps": 5}]}]},
         422, "workout_in_future"),
        ({"performed_on": "2026-10-07", "strength": [], "cardio": []}, 422, "empty_workout"),
        ({"performed_on": "2026-10-07", "strength": [{"exercise_id": "ex:nope", "sets": [{"weight_kg": 1, "reps": 1}]}]},
         404, "exercise_not_found"),
        ({"performed_on": "2026-10-07", "strength": [{"exercise_id": run, "sets": [{"weight_kg": 1, "reps": 1}]}]},
         422, "exercise_kind_mismatch"),
    ]
    for body, status, code in cases:
        response = client.post("/api/fitness/workouts", json=body, headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), body
    for bad_set in ({"weight_kg": -1, "reps": 5}, {"weight_kg": 60, "reps": 0}, {"weight_kg": 60, "reps": 5, "x": 1}):
        body = {"performed_on": "2026-10-07", "strength": [{"exercise_id": bench, "sets": [bad_set]}]}
        assert client.post("/api/fitness/workouts", json=body, headers=headers).status_code == 422


def test_replace_and_delete_workout(client):
    headers = ready_user(client, "alice")
    workout = _bench_workout(client, headers)
    body = {"performed_on": "2026-10-06", "rpe": 5, "strength": [],
            "cardio": [{"exercise_id": _ex(client, headers, "跑步"), "duration_minutes": 30, "distance_km": 5}]}
    replaced = client.put(f"/api/fitness/workouts/{workout['id']}", json=body, headers=headers).json()
    assert (replaced["performed_on"], replaced["strength"], replaced["cardio"][0]["duration_minutes"]) == (
        "2026-10-06", [], 30)
    listed = client.get("/api/fitness/workouts", params={"start": "2026-10-01", "end": "2026-10-07"},
                        headers=headers).json()
    assert [w["id"] for w in listed] == [workout["id"]]
    assert client.delete(f"/api/fitness/workouts/{workout['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).status_code == 404


def test_custom_exercise_is_private(client):
    alice = ready_user(client, "alice")
    created = client.post("/api/fitness/exercises", json={
        "name": "地雷管推举", "aliases": ["单臂地雷推"], "kind": "strength", "primary_muscles": ["shoulders"],
        "equipment": "barbell",
    }, headers=alice)
    assert created.status_code == 201
    custom_id = created.json()["id"]
    assert custom_id.startswith("custom:")
    assert client.get("/api/fitness/exercises/search", params={"q": "地雷管推举"}, headers=alice).json()["results"][0][
        "id"] == custom_id
    dup = client.post("/api/fitness/exercises", json={
        "name": "地雷管推举", "kind": "strength", "primary_muscles": ["shoulders"], "equipment": "barbell"}, headers=alice)
    assert dup.json()["error"]["code"] == "custom_exercise_exists"
    bella = ready_user(client, "bella")
    found = client.get("/api/fitness/exercises/search", params={"q": "地雷管推举"}, headers=bella).json()
    assert found["results"] == []
    assert client.get(f"/api/fitness/exercises/{custom_id}", headers=bella).status_code == 404
    body = {"performed_on": "2026-10-07", "strength": [{"exercise_id": custom_id, "sets": [{"weight_kg": 20, "reps": 10}]}]}
    assert client.post("/api/fitness/workouts", json=body, headers=bella).json()["error"]["code"] == "exercise_not_found"
    assert client.post("/api/fitness/workouts", json=body, headers=alice).status_code == 201
    assert client.get("/api/fitness/exercises/custom", headers=bella).json() == []
    assert client.delete(f"/api/fitness/exercises/custom/{custom_id}", headers=bella).status_code == 404


def test_workouts_are_private_and_note_is_encrypted(client):
    alice = ready_user(client, "alice")
    workout = _bench_workout(client, alice)
    bella = ready_user(client, "bella")
    assert client.get("/api/fitness/workouts", headers=bella).json() == []
    for method, kwargs in [("get", {}), ("delete", {}),
                           ("put", {"json": {"performed_on": "2026-10-07", "strength": [], "cardio": [
                               {"exercise_id": "ex:running", "duration_minutes": 10}]}})]:
        response = getattr(client, method)(f"/api/fitness/workouts/{workout['id']}", headers=bella, **kwargs)
        assert response.status_code == 404, method
    with get_engine().connect() as conn:
        raw = conn.execute(text("SELECT note FROM workouts")).scalar_one()
    assert "胸部日" not in raw


def test_fitness_requires_login_and_disclaimer(client):
    assert client.get("/api/fitness/workouts").status_code == 401
    headers = register_and_login(client, "carl")
    assert client.get("/api/fitness/workouts", headers=headers).json()["error"]["code"] == "disclaimer_not_accepted"
```

（"ex:running" 是跑步的内置编号；如果实现时跑步的编号不同，请改用 `_ex(client, alice, "跑步")` 取得。）

在 `test_route_guards.py` 追加 `test_every_fitness_route_requires_fitness_user`：所有 `/api/fitness/` 开头的路由（至少 10 个）依赖树中都有 `require_fitness_user`（写法同营养模块的对应测试）。

- [ ] **Step 2: 运行确认失败**，然后实现：模型与迁移（`0010_fitness`，down_revision `0009_meal_entries_day_index`；四张表，索引名与 mixin 默认一致，`custom_exercises` 唯一约束名 `uq_custom_exercises_user_name`）；`library.exercise_from_custom`（自定义动作编号 `custom:<uuid>`，`custom=True`）；`workouts.py`（整条替换：先删旧的组与有氧条目再写新的；position 按请求顺序从 1 开始，set_index 每个动作内从 1 开始）；`schemas.py`；`deps.py`（`require_fitness_user`，结构同营养模块，403 `fitness_not_available`）；`router.py`；`main.py` 挂路由；`app/models.py` 导入。
  - 检索接口返回 `{"query", "found", "exact", "results": [{"id", "name", "kind", "primary_muscles", "equipment", "custom", "match"}], "message"}`，未找到时 message 为"未找到与“<查询>”匹配的动作，可以新增自定义动作"，只有相近候选时 exact 为 false 并提示确认。
  - 动作详情返回全部字段（MET 与来源说明一并返回）。

- [ ] **Step 3: 运行确认通过**：目标测试与全量测试；对开发库执行 `uv run alembic upgrade head`。

- [ ] **Step 4: 提交**：`git commit -m "feat(fitness): add custom exercises, workout logging and fitness API"`

---

### Task 3: 训练量、能量估算、周汇总与动作趋势

**Files:**
- Create: `backend/app/fitness/calc.py`, `backend/app/fitness/summaries.py`
- Modify: `backend/app/fitness/schemas.py`, `router.py`
- Test: `backend/tests/test_fitness_calc.py`, `backend/tests/test_fitness_summaries.py`

**Interfaces:**
- Produces（`app.fitness.calc`，纯函数）:
  - 常量 `WORK_SECONDS_PER_SET = 40`、`DEFAULT_REST_SECONDS = 90`、`ESTIMATE_RANGE = (0.8, 1.2)`、`ESTIMATE_NOTE = "能量消耗仅为估算：按代谢当量粗略计算，个体差异很大，给出的是大致区间。"`、`INTENSITY_LEVELS = ("light", "moderate", "vigorous")`
  - `intensity_from_rpe(rpe: int | None) -> str`（1 至 4 light，5 至 7 moderate，8 至 10 vigorous，None 为 moderate）
  - 数据类 `SetInput(weight_kg, reps, rest_seconds, rpe)`、`StrengthInput(exercise, sets)`、`CardioInput(exercise, duration_minutes, distance_km, rpe)`、`WorkoutInput(performed_on, duration_minutes, rpe, strength: tuple[StrengthInput, ...], cardio: tuple[CardioInput, ...])`
  - `strength_volume(sets) -> float`（Σ 重量 × 次数）、`total_reps(sets) -> int`
  - `EnergyEstimate(kcal: float | None, low: int | None, high: int | None, status: str, note: str)`；`estimate_workout_energy(workout: WorkoutInput, body_weight_kg: float | None) -> EnergyEstimate`
  - `muscle_volumes(workouts: Iterable[WorkoutInput]) -> dict[str, float]`（按肌群名排序的字典；动作训练量完整计入它的每个主要肌群）
  - `TrendPoint(day, max_weight_kg, total_volume, total_reps, sets)`、`exercise_trend(points) -> tuple[TrendPoint, ...]`（按日期升序；同一天多次训练合并）
- `summaries.py`：`week_summary(db, user_id, week_start, body_weight_kg) -> WeekSummary`（week_start 必须是周一，否则 422 `invalid_week_start`；含训练次数、训练天数、总训练量、各肌群训练量、有氧总分钟、估算消耗区间合计、note）、`exercise_trend_for(db, user_id, exercise_id) -> (Exercise, tuple[TrendPoint, ...])`
- 接口：GET `/api/fitness/summary/week?start=`（默认本周一）、GET `/api/fitness/exercises/{exercise_id}/trend`

能量估算规则：
- 有氧条目：MET = 动作的 met[强度档]，强度取条目 rpe，否则整次训练 rpe，否则中等；千卡 = MET × 体重 × 分钟 ÷ 60。
- 力量部分：MET = `STRENGTH_MET[整次训练强度档]`；时长：若填了整次训练时长，力量分钟 = max(总时长 − 有氧总分钟, 0)；否则每组 (40 + 组间休息秒数，未填 90) 秒累加后 ÷ 60。只有有氧没有力量时力量部分为 0。
- 整次估算 kcal 为两部分之和（不四舍五入）；low = 四舍五入(kcal × 0.8)，high = 四舍五入(kcal × 1.2)；status 为 `ok`。体重缺失时 status `missing_body_weight`、kcal/low/high 为空、note 说明需要先在档案里填写体重。

手算样例（体重 70 千克）：
- 跑步 30 分钟，主观强度 6（中等，MET 8.0）→ 8 × 70 × 0.5 = 280 千卡，区间 224 至 336。
- 力量训练，整次时长 60 分钟、主观强度 7（中等，MET 5.0）、没有有氧 → 350 千卡，区间 280 至 420。
- 卧推 60×10、60×8、65×6 的训练量 = 600 + 480 + 390 = 1470，总次数 24。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_fitness_calc.py`
```python
from datetime import date

from app.fitness.calc import (
    CardioInput,
    SetInput,
    StrengthInput,
    WorkoutInput,
    estimate_workout_energy,
    exercise_trend,
    intensity_from_rpe,
    muscle_volumes,
    strength_volume,
    total_reps,
    TrendPoint,
)
from app.fitness.library import load_library

LIB = load_library()


def _by_name(name):
    return next(e for e in LIB.exercises.values() if e.name == name)


def _sets(*pairs, rest=None):
    return tuple(SetInput(weight_kg=w, reps=r, rest_seconds=rest, rpe=None) for w, r in pairs)


def test_intensity_buckets():
    assert [intensity_from_rpe(x) for x in (1, 4, 5, 7, 8, 10, None)] == [
        "light", "light", "moderate", "moderate", "vigorous", "vigorous", "moderate"]


def test_bench_volume_matches_hand_calculation():
    sets = _sets((60, 10), (60, 8), (65, 6))
    assert strength_volume(sets) == 1470
    assert total_reps(sets) == 24


def test_running_energy_example():
    run = _by_name("跑步")
    assert run.met[1] == 8.0
    workout = WorkoutInput(date(2026, 10, 7), None, 6, (), (CardioInput(run, 30, 5.0, None),))
    estimate = estimate_workout_energy(workout, 70)
    assert (estimate.kcal, estimate.low, estimate.high, estimate.status) == (280.0, 224, 336, "ok")
    assert "仅为估算" in estimate.note


def test_strength_energy_with_duration():
    workout = WorkoutInput(date(2026, 10, 7), 60, 7, (StrengthInput(_by_name("卧推"), _sets((60, 10))),), ())
    estimate = estimate_workout_energy(workout, 70)
    assert (estimate.kcal, estimate.low, estimate.high) == (350.0, 280, 420)


def test_strength_energy_without_duration_uses_sets_and_rest():
    workout = WorkoutInput(date(2026, 10, 7), None, 9, (StrengthInput(_by_name("深蹲"), _sets((100, 5), (100, 5), rest=140)),), ())
    estimate = estimate_workout_energy(workout, 80)
    minutes = 2 * (40 + 140) / 60
    assert estimate.kcal == 6.0 * 80 * minutes / 60


def test_missing_body_weight():
    workout = WorkoutInput(date(2026, 10, 7), 60, 7, (StrengthInput(_by_name("卧推"), _sets((60, 10))),), ())
    estimate = estimate_workout_energy(workout, None)
    assert (estimate.kcal, estimate.low, estimate.status) == (None, None, "missing_body_weight")


def test_muscle_volumes_count_each_primary_muscle():
    bench = _by_name("卧推")
    workout = WorkoutInput(date(2026, 10, 7), None, None, (StrengthInput(bench, _sets((60, 10))),), ())
    volumes = muscle_volumes([workout])
    assert all(volumes[m] == 600 for m in bench.primary_muscles)
    assert list(volumes) == sorted(volumes)


def test_trend_merges_same_day_and_sorts():
    points = [
        TrendPoint(date(2026, 10, 7), 65, 1470, 24, 3),
        TrendPoint(date(2026, 9, 30), 60, 1200, 20, 2),
        TrendPoint(date(2026, 10, 7), 70, 350, 5, 1),
    ]
    trend = exercise_trend(points)
    assert [(p.day, p.max_weight_kg, p.total_volume, p.total_reps, p.sets) for p in trend] == [
        (date(2026, 9, 30), 60, 1200, 20, 2), (date(2026, 10, 7), 70, 1820, 29, 4)]
```

`backend/tests/test_fitness_summaries.py`：通过接口（固定今天为 2026-10-07，星期三）记录：
- 9 月 30 日、10 月 3 日、10 月 7 日三次卧推，最高重量依次 60、62.5、65，训练量依次手算；
- 10 月 5 日一次跑步 30 分钟主观强度 6；档案体重 70 千克。
断言：
- 趋势接口按日期升序返回三个点，最高重量 60 → 62.5 → 65，训练量与手算一致（验收第 2 条）；
- `summary/week?start=2026-10-05` 的训练次数 2、训练天数 2、总训练量等于 10 月 7 日卧推训练量、各肌群训练量正确、有氧 30 分钟、估算消耗区间是两次训练区间之和并带"仅为估算"（验收第 6 条）；
- start 不是周一时返回 422 `invalid_week_start`；
- 另一个用户的周汇总为空、趋势为空列表。

- [ ] **Step 2: 运行确认失败**，然后实现 `calc.py`（全部纯函数，frozen 数据类）、`summaries.py`（从数据库读出训练并转换为 `WorkoutInput`；动作用 `resolve_exercise` 取得，已删除的自定义动作用快照名称构造一个临时 Exercise，肌群为 ("full_body",)，并在说明里提示）、接口与 schema。

- [ ] **Step 3: 运行确认通过并提交**：`git commit -m "feat(fitness): add volume, energy estimation, weekly summary and exercise trend"`

---

### Task 4: 运动限制冲突与今日训练信号

**Files:**
- Create: `backend/app/fitness/data/limit_terms.json`, `backend/app/fitness/conflicts.py`, `backend/app/fitness/signals.py`
- Modify: `backend/app/fitness/schemas.py`, `router.py`, `workouts.py`（记录与修改训练的响应附带冲突提示）
- Test: `backend/tests/test_fitness_conflicts.py`, `backend/tests/test_fitness_signal.py`

**Interfaces:**
- Produces:
  - `limit_terms.json`：`{"terms": {"<说法>": {"match": "any"} | {"match": "intensity", "min": "vigorous"} | {"match": "loaded"} | {"match": "traits", "traits": [...]} | {"not_applicable": true}}}`；查找时先原样，再去掉结尾的"运动""活动""动作"后再查；不少于：运动、锻炼、健身、体育锻炼 → any；剧烈运动、剧烈活动、高强度运动、高强度训练、剧烈 → intensity vigorous（另外带 high_impact 特征的动作也算）；提重物、重物、负重、举重、搬重物 → loaded（含重量大于 0 的力量组）；跑步、跑、长跑 → traits running；游泳 → traits swimming；弯腰 → traits bending；跳跃、跳 → traits jumping；骑车、骑行 → traits cycling；久坐、久站、卧床 → not_applicable。
  - `app.fitness.conflicts`：`Conflict(item_id, content, subject, level, message, workout_ids)`（level 为 `conflict` 或 `unverifiable`）、`find_conflicts(constraints, workouts) -> tuple[Conflict, ...]`（只看类别为 exercise_limit 的医嘱；workouts 为 (workout_id, WorkoutInput) 列表；结果按 item_id、subject、level 排序）
  - `app.fitness.signals`：`TrainingSignal(day, trained, kinds, intensity, energy_low, energy_high, energy_status, muscles, workout_count, conflicts, notes, disclaimer)`、`training_signal(db, user_id, today) -> TrainingSignal`
  - 接口：GET `/api/fitness/signal`（今天）；POST/PUT 训练的响应增加 `conflicts` 字段（按今天生效的医嘱判断这一条训练）。

冲突规则：
- 医嘱的每个涉及对象：查词汇表；any → 只要有训练就冲突；intensity → 整次训练强度为高强度、或任一条目强度为高强度、或含 high_impact 动作时冲突；loaded → 任一力量组重量大于 0 时冲突；traits → 含有该特征的动作时冲突；not_applicable → 跳过；词汇表里没有 → 有训练时给 `unverifiable`（"无法自动判断今天的训练是否符合医嘱「…」中的「…」，请自行核对"）。
- 冲突消息："今天的训练可能与医嘱「<医嘱内容>」冲突：涉及「<说法>」，请确认是否适合继续，或咨询医生。"；待复核的医嘱同样提示并加"这条医嘱正在待复核"。
- 冲突只提示，不阻止记录训练。

今日训练信号：
- trained 为今天是否有训练；kinds 为今天出现的类型（strength、cardio，排序）；intensity 为今天所有训练与条目中最高的强度档，没有训练时为 `none`；energy 为今天各次训练估算区间之和（体重缺失时为空并说明）；muscles 为今天力量训练涉及的主要肌群（排序）；conflicts 为今天的训练与今天生效医嘱的冲突；disclaimer 为 ESTIMATE_NOTE。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_fitness_conflicts.py`（纯函数，用 `app.medical.items.Constraint` 构造医嘱、用 calc 的输入数据类构造训练）：
- 医嘱"术后两周内避免提重物及剧烈运动"（exercise_limit，subjects ["提重物","剧烈运动"]）：卧推 60 千克一次（主观强度 6）→ 有"提重物"冲突、没有"剧烈运动"冲突；快走 30 分钟主观强度 4 → 没有冲突；跑步主观强度 9 → "剧烈运动"冲突；跳绳主观强度 5 → "剧烈运动"冲突（high_impact）。
- 医嘱"避免弯腰" → 硬拉冲突、卧推不冲突。
- 医嘱"卧床休息"（subjects ["卧床"]）→ 不产生冲突。
- 医嘱"避免对抗性运动"（未收录说法）→ 有训练时 `unverifiable`，没有训练时什么都没有。
- 非运动限制类医嘱（diet_avoid）不参与。
- 结果排序确定：打乱医嘱与训练顺序结果相同。

`backend/tests/test_fitness_signal.py`（接口，固定今天 2026-10-07）：
- 没有训练：`trained` 为假、`intensity` 为 none、`energy_low` 为空、`kinds` 为空。
- 今天记录卧推（体重 70 千克，整次 60 分钟、主观强度 7）后：`trained` 为真、kinds ["strength"]、intensity moderate、energy 280 至 420、muscles 含 chest。
- 通过医嘱接口录入并确认"两周内避免提重物及剧烈运动。"后：记录训练的响应含 `conflicts`（提重物）；`/signal` 的 conflicts 同样含这一条，ref 为医嘱条目编号（验收第 5 条）。

- [ ] **Step 2: 运行确认失败**，然后实现（词汇表用 pydantic 校验，重复键拒绝，引用的特征必须在 `EXERCISE_TRAITS` 中；训练信号只通过 `get_current_constraints(db, user_id, today)` 读医嘱，通过档案读体重）。

- [ ] **Step 3: 运行确认通过并提交**：`git commit -m "feat(fitness): add exercise-limit conflict detection and daily training signal"`

---

### Task 5: 接入步骤 04 的饮食判断

**Files:**
- Modify: `backend/app/nutrition/needs.py`（`with_training_bonus(needs, kcal) -> Needs`）、`engine.py`、`rules.py`、`context.py`、`schemas.py`、`router.py`（每日汇总用调整后的需求）、`data/soft_rules.json`
- Test: `backend/tests/test_nutrition_training.py`

**Interfaces:**
- Consumes: `app.fitness.signals.training_signal`、`TrainingSignal`
- Produces:
  - `EvaluationContext.training: TrainingContext | None`，`TrainingContext(trained, kinds, intensity, energy_low, conflicts: tuple[TrainingConflict, ...])`，`TrainingConflict(item_id, content, subject, level, message)`（engine 内定义，不导入 fitness，保持引擎纯净与依赖方向）
  - `SOURCE_ORDER` 变为 medical、cycle、goal、training、intake、preference；schemas 的 source Literal 增加 training；`SOURCE_NAMES["training"] = "训练"`
  - soft_rules.json 增加 `"training": {"strength": [...], "intensity_moderate_or_above": [...]}`：
    - strength：`{"tags": ["high_protein"], "effect": "prefer", "message": "力量训练日保证优质蛋白，有助于肌肉恢复"}`
    - intensity_moderate_or_above：`{"tags": ["fast_carb"], "effect": "prefer", "message": "训练日可以在训练前后适当安排快碳，帮助补充糖原"}`
  - `with_training_bonus`：status 为 ok 且 kcal 大于 0 时，energy_kcal、energy_kcal_low、energy_kcal_high 各加 kcal（四舍五入为整数），notes 末尾加"已计入今天训练估算消耗的下限 <kcal> 千卡。"；否则原样返回。
- 规则：
  - 上下文：开放 fitness 时读取今天的训练信号；今天有训练且估算可用时，需求加上 `energy_low`；`TrainingContext` 由信号转换而来。
  - 引擎：今天有训练时，按规则对带相应标签的食物给 `training` 来源的 prefer 依据，消息开头写"训练提示（今天有<力量训练/有氧训练>，强度<轻度/中等/高强度>）："；对每个训练冲突给一条 `training` 来源的 `info` 依据（ref 为医嘱条目编号），消息为冲突消息加"饮食判断不受影响，请留意运动安排"。休息日不产生 training 依据。info 不改变结论。
  - 营养每日汇总的 needs 与 remaining 使用加上训练消耗下限后的需求，并在 notes 中可见。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_training.py`（接口，固定今天 2026-10-07，用户档案完整：男、1990 年、175 厘米、70 千克、moderate、gain_muscle）：
- 休息日：判断米饭 200 克与鸡胸肉 150 克，依据中没有 training 来源；每日汇总的需求能量为 2760。
- 记录今天卧推训练（60 分钟、主观强度 7，估算 280 至 420）后：米饭得到 training 来源的 prefer（快碳），鸡胸肉得到 training 来源的 prefer（高蛋白）且消息含"力量训练"；每日汇总的需求能量变为 2760 + 280 = 3040，notes 含"已计入今天训练估算消耗的下限 280 千卡"（验收第 4 条：建议随之变化并说明原因）。
- 当天能量接近上限时：先记录饮食让休息日判断某高能量食物为谨慎（超出估算上限），训练后同一判断不再因能量超出而谨慎（额度增加）。具体克数按休息日上限 3036 与训练日上限 3316 设计，测试中写明计算。
- 有"两周内避免提重物及剧烈运动"医嘱并记录卧推后：任一食物的判断含 training 来源的 info 冲突依据，ref 为医嘱条目编号；结论不因 info 改变（验收第 5 条）。
- 引擎纯函数层面：同一食物在 training 为空与有训练两种上下文中的依据不同；多次运行结果一致。

- [ ] **Step 2: 运行确认失败**，然后实现（引擎仍不得导入数据库、时间或 fitness 包；context 负责把信号转换为 `TrainingContext`；soft_rules 加载校验 training 段的标签存在）。

- [ ] **Step 3: 运行确认通过并提交**：`git commit -m "feat(nutrition): use the daily training signal in needs and the constraint engine"`

---

### Task 6: 演示数据、交付文档与验收记录

**Files:**
- Create: `backend/app/fitness/demo.py`
- Test: `backend/tests/test_fitness_demo.py`, `backend/tests/test_fitness_docs.py`
- Create: `docs/05-交付物/动作库与训练记录数据表说明.md`、`训练量与能量估算口径说明.md`、`训练信号与饮食联动说明.md`、`接口清单.md`、`演示样例说明.md`、`验收记录.md`（均不得出现代码、命令、反引号与代码块）
- Modify: `README.md`（新增"健身模块演示"小节；同步开头完成情况与表数量），`docs/00-总览与串联.md`（步骤 05 改为"待验收"），`docs/04-交付物/约束融合规则说明.md`（补充训练来源）

**Interfaces:**
- Produces: `app.fitness.demo.DEMO_USERNAME = "demo_fitness"`、`seed(db, today) -> bool`、`main()`（`uv run python -m app.fitness.demo`）：一个男性增肌用户，档案完整（体重 70 千克），以今天为准倒推一周的训练：周一胸与三头、周二跑步、周三背与二头、周五腿、周六游泳、今天卧推（重量比一周前增加），另外加一个自定义动作。

- [ ] **Step 1**：测试 `seed` 两次（第一次 True、第二次 False），训练条数与卧推趋势递增；文档测试检查 `docs/05-交付物/` 无反引号、`演示样例说明.md` 提到一周的每一天。
- [ ] **Step 2**：实现 demo；写六份文档（先读代码，按实际行为写）：数据表说明（四张表与内置动作库字段、加密与明文的理由）、口径说明（训练量、强度分档、MET 来源与取值、时长估算、区间、手算样例）、联动说明（信号字段、训练消耗计入额度的规则与理由、引擎的训练来源规则、冲突规则与词汇表、休息日与训练日的对比示例）、接口清单（全部接口与错误码）、演示样例说明、验收记录（7 条验收标准逐条：自动化测试与手动核对方法，"用户验收"列留空）。
- [ ] **Step 3**：README 与总览；全量测试；开发库迁移后运行 demo 两次。
- [ ] **Step 4**：提交 `git commit -m "docs(fitness): add demo data, step 05 delivery docs and acceptance record"`
