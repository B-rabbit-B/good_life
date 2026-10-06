# 步骤 04 营养与饮食约束引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立食物营养库（成分表整理数据、自建菜品配方、手动补充）与检索，饮食记录与每日汇总，按档案估算每日需求，以及确定性的"多约束融合"引擎：医嘱为硬约束（命中即"不建议"），经期阶段、健身目标、当日剩余额度与个人偏好为软约束，输出"适合、谨慎、不建议"与逐条可追溯的依据。满足 `docs/04-营养与饮食约束引擎.md` 的 8 条验收标准。

**Architecture:** 新增 `app/nutrition` 包。营养库是只读参考数据，放在 `app/nutrition/data/` 的数据文件里，启动时加载到内存（`catalog.py`），不建数据库表；用户的饮食记录才入库（`meal_entries` 表）。`needs.py` 用 Mifflin-St Jeor 公式估算需求；`rules.py` 读取并校验医嘱词汇表与软约束规则；`engine.py` 是纯函数引擎，同样输入得到同样输出；`context.py` 只通过步骤 02、03 的查询函数（`medical.items.get_current_constraints`、`cycle.insights.get_phase_info`）组装判断所需的上下文；`router.py` 提供检索、记录、汇总、需求与判断接口。

**Tech Stack:** 沿用前面步骤：Python 3.12、FastAPI、SQLAlchemy 2、PostgreSQL 16、Alembic、pytest、httpx2。

**Spec:** `docs/04-营养与饮食约束引擎.md`（总览见 `docs/00-总览与串联.md`）

## Global Constraints

- 运行平台是 Windows 11，终端是 PowerShell 5.1（不支持 `&&`）；也可以用 Bash 工具。
- 所有后端命令都在 `E:\workspace\good-life\backend` 目录下执行，统一用 `uv run ...`；完整测试用 `uv run pytest -q -W error`，必须零失败、零警告。
- 数据库地址用 `127.0.0.1:5433`，测试库 `goodlife_test`。
- 统一错误格式：`{"error": {"code": "<机器可读码>", "message": "<中文提示>"}}`，业务错误一律抛 `app.errors.AppError(status_code, code, message)`。
- 每张业务表都必须有 `user_id` 列；查询统一从 `owned_by` 开始；按编号取单条记录用 `get_owned_or_404`。营养库不入库。
- 任何接口都不接受客户端传入的 user_id；请求模型一律 `extra="forbid"`。
- 所有 `/api/nutrition/*` 接口依赖 `require_nutrition_user`（内部依赖 `require_disclaimer_user`）；是否开放只由 `compute_capabilities` 判断。
- "今天"一律通过依赖 `get_today` 取得；服务层需要日期的函数显式接收 `today`。判断（evaluate）只针对今天，不接受其他日期——医嘱查询会按传入日期刷新到期状态，传入未来日期会提前改变用户数据。
- 引擎读取医嘱与经期信息只能通过 `app.medical.items.get_current_constraints` 与 `app.cycle.insights.get_phase_info`，不得直接查询它们的表。
- 引擎必须是确定性的：不读时间、不读随机数、不依赖字典或集合的遍历顺序；所有输出列表按固定规则排序。
- 每条结论都必须能追溯到依据（医嘱条目编号、经期提示规则编号、目标、当日摄入或个人偏好）；所有判断结果都带免责说明。
- 寒凉、温热等标签属于"传统经验"，必须单独归类并在依据中写明"传统经验"，不得作为营养学或医学结论。
- 营养库每个食物都带出处与授权状态；成分表整理数据与由它计算的菜品标为 `personal_study_only`，手动补充的估算数据标为 `self_estimate_unverified`。
- 模型与迁移必须一致；新迁移接在 `0007_medical` 之后，revision 编号不超过 32 个字符。
- 提交信息以如下一行结尾：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（不要替换成你自己的模型名）；不得提交 `backend/.env` 与 `.superpowers/`。
- 交付文档（`docs/04-交付物/` 下）不得出现代码、命令、反引号或代码块。

## 关键决策

| 决策 | 内容 | 理由 |
|---|---|---|
| 数据来源 | 用户选定：下载 Sanotsu/china-food-composition-data 固定版本 d15675c 的全量 CSV（1677 种食材），原样存入仓库并校验哈希；自建常见菜配方按食材计算营养；成分表没有的酒类、饮料、甜点等手动补充估算值 | 用户选定；固定版本保证可复现 |
| 营养库存放 | 只读数据文件，启动时加载到内存，不建数据库表 | 参考数据不属于任何用户，避免与"每张业务表都有 user_id"的约定冲突；加载快、确定性好 |
| 未识别的医嘱说法 | 用户选定：判断结论最多为"谨慎"，并列出这条医嘱请用户核对 | 用户选定；宁可多提醒也不说"适合" |
| 医嘱与食物的对应 | 医嘱的涉及对象先查词汇表（对应到食物标签），查不到再按食物名称与别名匹配；两者都对不上且营养库里没有任何食物名包含它，视为"无法判断" | 可追溯、可审核；避免猜测 |
| 饮食要求类医嘱 | 低盐、低脂、低糖、低嘌呤、糖尿病饮食、清淡按"违反的标签"判为不建议；高蛋白等按"符合"给正面依据；流质、半流质、软食无法从营养数据判断，视为"无法判断" | 规格：命中医嘱即不建议 |
| 需求估算 | Mifflin-St Jeor 公式乘活动系数，减脂乘 0.85、增肌乘 1.10；蛋白质按体重每千克 1.0、1.2（减脂）、1.6（增肌）克；脂肪占能量 20% 至 30%，碳水 50% 至 65%，膳食纤维 25 至 30 克，钠不超过 2000 毫克 | 常用公式与中国居民膳食指南的常见范围，明确标注为估算 |
| 饮食记录存储 | 食物编号、名称、克数与营养快照明文存储，备注加密 | 汇总需要按日期与数值计算；饮食本身不是诊断信息 |
| 份量 | 记录与判断都按"可食部分的克数"；也可以用份量单位（碗、个、份）换算 | 简单、可手算 |

## 文件结构

```
.gitattributes                      # CSV 原样保存，不做换行转换（任务 1）
backend/
├── app/nutrition/
│   ├── __init__.py
│   ├── data/
│   │   ├── cfcd_food_composition.csv   # 原样下载，校验哈希（任务 1）
│   │   ├── tags.json                   # 标签定义与成员（任务 1 建营养学标签，任务 2 补全）
│   │   ├── aliases.json                # 常用名到食物编号（任务 1 建，任务 2 补全）
│   │   ├── supplements.json            # 手动补充的食物（任务 2）
│   │   ├── dishes.json                 # 菜品配方（任务 2）
│   │   ├── portions.json               # 份量单位（任务 2）
│   │   ├── vocabulary.json             # 医嘱与偏好说法到标签的对应（任务 4）
│   │   └── soft_rules.json             # 经期阶段与健身目标的软约束规则（任务 4）
│   ├── catalog.py                  # 营养库加载与检索（任务 1 建，任务 2 扩展）
│   ├── needs.py                    # 需求估算（任务 3）
│   ├── models.py                   # meal_entries（任务 3）
│   ├── meals.py                    # 饮食记录与每日汇总（任务 3）
│   ├── rules.py                    # 词汇表与软规则加载（任务 4）
│   ├── engine.py                   # 约束融合引擎（任务 4）
│   ├── context.py                  # 组装判断上下文（任务 5）
│   ├── schemas.py、deps.py、router.py   # 任务 3 建，任务 5 追加
│   └── demo.py                     # 任务 6
├── migrations/versions/0008_nutrition.py   # 任务 3
└── tests/test_nutrition_*.py
docs/04-交付物/                     # 任务 6
```

---

### Task 1: 营养库核心：成分表数据、加载与检索

**Files:**
- Create: `.gitattributes`（仓库根目录）
- Create: `backend/app/nutrition/__init__.py`, `backend/app/nutrition/catalog.py`
- Create: `backend/app/nutrition/data/cfcd_food_composition.csv`（下载）, `backend/app/nutrition/data/tags.json`, `backend/app/nutrition/data/aliases.json`
- Test: `backend/tests/test_nutrition_catalog.py`

**Interfaces:**
- Produces（`app.nutrition.catalog`）:
  - 常量 `DATA_DIR`、`CFCD_FILE`、`CFCD_SHA256`、`LICENSE_PERSONAL_STUDY = "personal_study_only"`、`LICENSE_SELF_ESTIMATE = "self_estimate_unverified"`、`NUTRIENT_FIELDS`、`MATCH_TYPES`
  - `parse_value(raw) -> float | None`、`split_name(raw) -> tuple[str, tuple[str, ...]]`、`normalize_query(text) -> str`、`round_half_up(value) -> int`、`round_one(value) -> float | None`
  - 数据类 `Nutrients`（8 个营养字段，方法 `scaled(grams)`、`plus(other)`）、`TagDefinition(id, name, kind, basis, review_status)`、`Source(dataset, reference, license_status, note)`、`Food(id, name, aliases, category, kind, nutrients, tags, source, portions, default_grams)`、`SearchHit(food, match)`
  - `Catalog(foods, tag_definitions, common_aliases)`：`foods`、`tags`、`get(food_id)`、`tag_name(tag_id)`、`search(query, limit=20) -> list[SearchHit]`、`name_matches(term) -> bool`
  - `load_catalog() -> Catalog`（带缓存）

食物编号格式：成分表食材为 `cfcd:<foodCode>`，菜品为 `dish:<配方编号>`，手动补充为 `supp:<编号>`。

检索规则（排序先按匹配类型，再按偏好，再按编号）：
1. `exact_name`：查询与名称完全相同，或是 aliases.json 中的常用名；
2. `exact_alias`：查询与成分表方括号里的别名或菜品别名完全相同；
3. `prefix`：名称或别名以查询开头；
4. `contains`：名称或别名包含查询；
5. `query_contains`：查询包含某个长度不少于 2 的名称、别名或常用名（例如"一碗米饭"）。
同一匹配类型内：名称含"代表值"的优先，其次菜品、手动补充、食材，其次名称较短者，最后按编号。查询为空或匹配不上返回空列表，不猜测。

- [ ] **Step 1: 下载并锁定数据文件**

在仓库根目录创建 `.gitattributes`：
```
backend/app/nutrition/data/*.csv -text
```

下载固定版本的 CSV（用户已同意下载这份公开数据）：
```
curl -sL -o backend/app/nutrition/data/cfcd_food_composition.csv https://raw.githubusercontent.com/Sanotsu/china-food-composition-data/d15675c27582748307023b7ee7aca2a63fc52756/json_data_v3_20260825_qwen38max_kimi_k3_fixed_en/food_composition_full.csv
```
校验 SHA-256 必须为 `7f89bfde478b1ae8a9109eab7d9842e7e87d378a947e3a50b0eaa819c554dcf4`，不一致则停止并报告。不要用任何编辑器打开保存这个文件。

- [ ] **Step 2: 写失败测试**

`backend/tests/test_nutrition_catalog.py`
```python
import hashlib

from app.nutrition.catalog import (
    CFCD_FILE,
    CFCD_SHA256,
    LICENSE_PERSONAL_STUDY,
    Nutrients,
    load_catalog,
    normalize_query,
    parse_value,
    round_half_up,
    round_one,
    split_name,
)


def test_data_file_is_the_pinned_version():
    assert hashlib.sha256(CFCD_FILE.read_bytes()).hexdigest() == CFCD_SHA256


def test_parse_value():
    assert parse_value("116") == 116.0
    assert parse_value("2.50") == 2.5
    assert parse_value("899*") == 899.0
    assert parse_value("Tr") == 0.0
    for missing in ("—", "", "un", None):
        assert parse_value(missing) is None


def test_split_name():
    assert split_name("马铃薯［土豆、洋芋］") == ("马铃薯", ("土豆", "洋芋"))
    assert split_name("番茄［西红柿］") == ("番茄", ("西红柿",))
    assert split_name("米饭（蒸，代表值）") == ("米饭（蒸，代表值）", ())


def test_rounding_helpers():
    assert round_half_up(2.5) == 3
    assert round_half_up(2.49) == 2
    assert round_one(5.25) == 5.3
    assert round_one(None) is None
    assert normalize_query(" 一碗　米饭 ") == "一碗米饭"


def test_nutrients_scale_and_add():
    rice = Nutrients(energy_kcal=116, protein_g=2.6, fat_g=0.3, carbohydrate_g=25.9, sodium_mg=None)
    serving = rice.scaled(150)
    assert serving.energy_kcal == 174.0
    assert serving.sodium_mg is None
    total = serving.plus(Nutrients(energy_kcal=10, sodium_mg=5))
    assert total.energy_kcal == 184.0
    assert total.sodium_mg == 5


def test_catalog_loads_every_cfcd_row_with_source():
    catalog = load_catalog()
    cfcd = [food for food in catalog.foods.values() if food.id.startswith("cfcd:")]
    assert len(cfcd) == 1677
    rice = catalog.get("cfcd:012401x")
    assert rice.name == "米饭（蒸，代表值）"
    assert (rice.nutrients.energy_kcal, rice.nutrients.protein_g, rice.nutrients.carbohydrate_g) == (116, 2.6, 25.9)
    assert rice.source.reference == "012401x"
    assert rice.source.license_status == LICENSE_PERSONAL_STUDY
    assert "仅供个人学习" in rice.source.note
    assert all(food.source.dataset and food.source.license_status for food in catalog.foods.values())


def test_bracket_aliases_are_searchable():
    catalog = load_catalog()
    hits = catalog.search("土豆")
    assert hits[0].food.id == "cfcd:021101"
    assert hits[0].match in ("exact_name", "exact_alias")
    assert catalog.search("西红柿")[0].food.name == "番茄"


def test_common_aliases_rank_first():
    catalog = load_catalog()
    first = catalog.search("米饭")[0]
    assert (first.food.id, first.match) == ("cfcd:012401x", "exact_name")
    assert catalog.search("一碗米饭")[0].food.id == "cfcd:012401x"
    assert catalog.search("一碗米饭")[0].match == "query_contains"


def test_not_found_returns_empty_and_search_is_deterministic():
    catalog = load_catalog()
    assert catalog.search("完全不存在的食物名称") == []
    assert catalog.search("   ") == []
    assert [h.food.id for h in catalog.search("鸡")] == [h.food.id for h in catalog.search("鸡")]
    assert len(catalog.search("鸡")) == 20


def test_nutrition_tags_are_computed_from_values():
    catalog = load_catalog()
    breast = catalog.search("鸡胸脯肉")[0].food
    assert "high_protein" in breast.tags
    assert "high_protein" not in catalog.get("cfcd:012401x").tags
    assert catalog.tag_name("high_protein") == "高蛋白"
    assert catalog.tags["high_protein"].kind == "nutrition"


def test_name_matches():
    catalog = load_catalog()
    assert catalog.name_matches("菠菜")
    assert catalog.name_matches("新鲜菠菜")
    assert not catalog.name_matches("发物")
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_nutrition_catalog.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.nutrition'`

- [ ] **Step 4: 数据文件（任务 1 部分）**

`backend/app/nutrition/data/tags.json`（本任务只放营养学标签，任务 2 追加其余）：
```json
[
  {"id": "high_protein", "name": "高蛋白", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克蛋白质不少于 12 克（参照 GB 28050 高蛋白声称的数值）", "rule": {"nutrient": "protein_g", "min": 12}},
  {"id": "high_fat", "name": "高脂肪", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克脂肪不少于 20 克", "rule": {"nutrient": "fat_g", "min": 20}},
  {"id": "low_fat", "name": "低脂肪", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克脂肪不超过 3 克（参照 GB 28050 低脂肪声称的数值）", "rule": {"nutrient": "fat_g", "max": 3}},
  {"id": "high_sodium", "name": "高钠", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克钠不少于 800 毫克", "rule": {"nutrient": "sodium_mg", "min": 800}},
  {"id": "high_fiber", "name": "高膳食纤维", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克膳食纤维不少于 6 克（参照 GB 28050 高膳食纤维声称的数值）", "rule": {"nutrient": "fiber_g", "min": 6}},
  {"id": "iron_rich", "name": "富含铁", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克铁不少于 3 毫克", "rule": {"nutrient": "iron_mg", "min": 3}},
  {"id": "calcium_rich", "name": "富含钙", "kind": "nutrition", "review_status": "reviewed",
   "basis": "每 100 克钙不少于 150 毫克", "rule": {"nutrient": "calcium_mg", "min": 150}}
]
```

`backend/app/nutrition/data/aliases.json`（本任务至少包含下面这些，任务 2 补全）：
```json
{
  "米饭": "cfcd:012401x",
  "鸡蛋": "cfcd:111101x",
  "馒头": "cfcd:011404x",
  "苹果": "cfcd:061101x",
  "牛肉": "cfcd:082101x",
  "猪肉": "cfcd:081101x"
}
```

- [ ] **Step 5: 实现 catalog**

`backend/app/nutrition/__init__.py`：空文件。

`backend/app/nutrition/catalog.py`
```python
"""营养库：从数据文件加载食物（只读参考数据，不入数据库），提供按名称与别名的检索。

数据来源，每个食物都带出处与授权状态：
- 中国食物成分表（第 6 版）整理数据：Sanotsu/china-food-composition-data 固定版本 d15675c，原样保存并校验哈希；
- 自建菜品配方：按配方中各食材的成分表数值计算（任务 2）；
- 手动补充：成分表没有的酒类、饮料、甜点等的估算值（任务 2）。
"""

import csv
import json
import math
import re
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict

DATA_DIR = Path(__file__).with_name("data")
CFCD_FILE = DATA_DIR / "cfcd_food_composition.csv"
CFCD_SHA256 = "7f89bfde478b1ae8a9109eab7d9842e7e87d378a947e3a50b0eaa819c554dcf4"
CFCD_DATASET = "中国食物成分表（第 6 版）整理数据"
CFCD_NOTE = (
    "来自 Sanotsu/china-food-composition-data 固定版本 d15675c；由视觉大模型从原书识别并经交叉校验，"
    "作者声明不保证与原书完全一致；版权归原作者，仅供个人学习，商用前须核实授权或替换。"
)
LICENSE_PERSONAL_STUDY = "personal_study_only"
LICENSE_SELF_ESTIMATE = "self_estimate_unverified"
NUTRIENT_FIELDS = (
    "energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "fiber_g", "sodium_mg", "iron_mg", "calcium_mg",
)
CFCD_COLUMNS = {
    "energy_kcal": "energyKCal", "protein_g": "protein", "fat_g": "fat", "carbohydrate_g": "CHO",
    "fiber_g": "dietaryFiber", "sodium_mg": "Na", "iron_mg": "Fe", "calcium_mg": "Ca",
}
MATCH_TYPES = ("exact_name", "exact_alias", "prefix", "contains", "query_contains")
KIND_ORDER = {"dish": 0, "supplement": 1, "ingredient": 2}
SEARCH_LIMIT = 20
MIN_CONTAINED_LENGTH = 2
BRACKET_RE = re.compile(r"［([^］]*)］")
ALIAS_SPLIT_RE = re.compile(r"[、，,]")
WHITESPACE_RE = re.compile(r"[\s\u3000]+")


def parse_value(raw: str | None) -> float | None:
    """成分表数值：Tr（微量）记为 0；—、空、un 等表示未测定，记为 None；去掉数值后的星号。"""
    if raw is None:
        return None
    text = raw.strip().rstrip("*")
    if text in ("Tr", "tr"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return None


def split_name(raw: str) -> tuple[str, tuple[str, ...]]:
    aliases = tuple(
        alias.strip() for group in BRACKET_RE.findall(raw) for alias in ALIAS_SPLIT_RE.split(group) if alias.strip()
    )
    return BRACKET_RE.sub("", raw).strip(), aliases


def normalize_query(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def round_one(value: float | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Nutrients:
    """每 100 克可食部分（或按份量换算后）的营养素。None 表示数据缺失。"""

    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None
    iron_mg: float | None = None
    calcium_mg: float | None = None

    def scaled(self, grams: float) -> "Nutrients":
        return Nutrients(**{
            name: None if getattr(self, name) is None else getattr(self, name) * grams / 100
            for name in NUTRIENT_FIELDS
        })

    def plus(self, other: "Nutrients") -> "Nutrients":
        """相加；两边都缺失才是缺失，一边缺失按 0 计。"""
        values = {}
        for name in NUTRIENT_FIELDS:
            a, b = getattr(self, name), getattr(other, name)
            values[name] = None if a is None and b is None else (a or 0) + (b or 0)
        return Nutrients(**values)


@dataclass(frozen=True)
class TagDefinition:
    id: str
    name: str
    kind: str  # nutrition / composition / culinary / dietary / tradition
    basis: str
    review_status: str  # reviewed / draft


@dataclass(frozen=True)
class Source:
    dataset: str
    reference: str
    license_status: str
    note: str


@dataclass(frozen=True)
class Food:
    id: str
    name: str
    aliases: tuple[str, ...]
    category: str
    kind: str  # ingredient / dish / supplement
    nutrients: Nutrients
    tags: frozenset[str]
    source: Source
    portions: tuple[tuple[str, float], ...] = ()  # （单位, 克），按单位名排序
    default_grams: float = 100.0


@dataclass(frozen=True)
class SearchHit:
    food: Food
    match: str


class _TagRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nutrient: str
    min: float | None = None
    max: float | None = None


class _TagMembers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = []
    name_contains: list[str] = []
    categories: list[str] = []
    exclude_ids: list[str] = []


class _TagEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: Literal["nutrition", "composition", "culinary", "dietary", "tradition"]
    basis: str
    review_status: Literal["reviewed", "draft"]
    rule: _TagRule | None = None
    members: _TagMembers | None = None


class Catalog:
    def __init__(self, foods: list[Food], tag_definitions: list[TagDefinition], common_aliases: dict[str, str]):
        self.foods = MappingProxyType({food.id: food for food in sorted(foods, key=lambda f: f.id)})
        self.tags = MappingProxyType({tag.id: tag for tag in sorted(tag_definitions, key=lambda t: t.id)})
        self.common_aliases = MappingProxyType(dict(sorted(common_aliases.items())))
        self._names = {food.id: (food.name, *food.aliases) for food in self.foods.values()}

    def get(self, food_id: str) -> Food | None:
        return self.foods.get(food_id)

    def tag_name(self, tag_id: str) -> str:
        tag = self.tags.get(tag_id)
        return tag.name if tag else tag_id

    def _preference(self, food: Food) -> tuple:
        return (0 if "代表值" in food.name else 1, KIND_ORDER.get(food.kind, 9), len(food.name), food.id)

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[SearchHit]:
        q = normalize_query(query)
        if not q:
            return []
        best: dict[str, int] = {}

        def offer(food_id: str, rank: int) -> None:
            if food_id not in best or rank < best[food_id]:
                best[food_id] = rank

        for alias, food_id in self.common_aliases.items():
            if alias == q:
                offer(food_id, 0)
            elif len(alias) >= MIN_CONTAINED_LENGTH and alias in q:
                offer(food_id, 4)
        for food_id, names in self._names.items():
            name, aliases = names[0], names[1:]
            if name == q:
                offer(food_id, 0)
            elif q in aliases:
                offer(food_id, 1)
            elif any(n.startswith(q) for n in names):
                offer(food_id, 2)
            elif any(q in n for n in names):
                offer(food_id, 3)
            elif any(len(n) >= MIN_CONTAINED_LENGTH and n in q for n in names):
                offer(food_id, 4)
        ordered = sorted(best.items(), key=lambda item: (item[1], self._preference(self.foods[item[0]])))
        return [SearchHit(self.foods[food_id], MATCH_TYPES[rank]) for food_id, rank in ordered[:limit]]

    def name_matches(self, term: str) -> bool:
        """营养库里是否有食物的名称或别名与这个说法对得上（互相包含）。"""
        t = normalize_query(term)
        if not t:
            return False
        for names in (*self._names.values(), tuple(self.common_aliases)):
            for name in names:
                if t in name or (len(name) >= MIN_CONTAINED_LENGTH and name in t):
                    return True
        return False


def _load_tag_entries() -> list[_TagEntry]:
    entries = [_TagEntry.model_validate(raw) for raw in json.loads((DATA_DIR / "tags.json").read_text("utf-8"))]
    ids = [entry.id for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("tags.json 中有重复的标签编号")
    for entry in entries:
        if entry.rule and entry.rule.nutrient not in NUTRIENT_FIELDS:
            raise ValueError(f"标签 {entry.id} 引用了未知营养素 {entry.rule.nutrient}")
        if entry.kind == "tradition" and "传统" not in entry.basis:
            raise ValueError(f"传统经验类标签 {entry.id} 的依据必须写明传统经验")
    return entries


def _rule_matches(rule: _TagRule, nutrients: Nutrients) -> bool:
    value = getattr(nutrients, rule.nutrient)
    if value is None:
        return False
    if rule.min is not None and value < rule.min:
        return False
    if rule.max is not None and value > rule.max:
        return False
    return True


def _member_matches(members: _TagMembers, food: Food) -> bool:
    if food.id in members.exclude_ids:
        return False
    if food.id in members.ids:
        return True
    if any(food.category.startswith(prefix) for prefix in members.categories):
        return True
    names = (food.name, *food.aliases)
    return any(word in name for word in members.name_contains for name in names)


def assign_tags(food: Food, entries: list[_TagEntry]) -> frozenset[str]:
    tags = set(food.tags)
    for entry in entries:
        if entry.rule and _rule_matches(entry.rule, food.nutrients):
            tags.add(entry.id)
        if entry.members and _member_matches(entry.members, food):
            tags.add(entry.id)
    return frozenset(tags)


def _load_cfcd() -> list[Food]:
    foods = []
    with CFCD_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = row["foodCode"].strip()
            name, aliases = split_name(row["foodName"])
            foods.append(
                Food(
                    id=f"cfcd:{code}",
                    name=name,
                    aliases=aliases,
                    category=row["category"].strip(),
                    kind="ingredient",
                    nutrients=Nutrients(**{f: parse_value(row[c]) for f, c in CFCD_COLUMNS.items()}),
                    tags=frozenset(),
                    source=Source(CFCD_DATASET, code, LICENSE_PERSONAL_STUDY, CFCD_NOTE),
                )
            )
    return foods


def _load_common_aliases(food_ids: set[str]) -> dict[str, str]:
    aliases = json.loads((DATA_DIR / "aliases.json").read_text("utf-8"))
    unknown = sorted(target for target in aliases.values() if target not in food_ids)
    if unknown:
        raise ValueError(f"aliases.json 指向不存在的食物：{unknown}")
    return aliases


def build_catalog(foods: list[Food]) -> Catalog:
    entries = _load_tag_entries()
    tagged = [replace(food, tags=assign_tags(food, entries)) for food in foods]
    definitions = [TagDefinition(e.id, e.name, e.kind, e.basis, e.review_status) for e in entries]
    return Catalog(tagged, definitions, _load_common_aliases({food.id for food in tagged}))


@lru_cache
def load_catalog() -> Catalog:
    return build_catalog(_load_cfcd())
```


- [ ] **Step 6: 运行确认通过**

Run: `uv run pytest tests/test_nutrition_catalog.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。若 `鸡胸脯肉` 或某个编号与真实数据不符，以数据文件为准修正测试并在报告中说明。

- [ ] **Step 7: 提交**

```
git add .gitattributes backend/app/nutrition backend/tests/test_nutrition_catalog.py
git commit -m "feat(nutrition): add pinned food composition data, catalog loader and search"
```

---

### Task 2: 菜品配方、手动补充、份量与标签成员

**Files:**
- Create: `backend/app/nutrition/data/dishes.json`, `supplements.json`, `portions.json`
- Modify: `backend/app/nutrition/data/tags.json`（追加非营养学标签）, `aliases.json`（补全）, `backend/app/nutrition/catalog.py`（加载菜品、补充与份量）
- Test: `backend/tests/test_nutrition_data.py`

**Interfaces:**
- Consumes: 任务 1 的 catalog
- Produces:
  - catalog 增加 `_load_supplements()`、`_load_dishes(ingredients)`、`_load_portions()`，`load_catalog()` 返回包含三类食物的营养库
  - 常量 `DISH_DATASET = "自建菜品配方"`、`SUPPLEMENT_DATASET = "手动补充估算"`、`INHERITED_TAG_KINDS = ("composition",)`

数据文件格式（用 pydantic 校验，`extra="forbid"`）：
- `supplements.json`：列表，每项 `{"id", "name", "aliases": [], "category", "nutrients": {8 个字段，可缺省为 null}, "serving_grams", "serving_unit", "tags": [], "note"}`。出处为"手动补充估算"，授权状态 `self_estimate_unverified`，note 必须说明估算依据（例如"按常见市售产品营养成分表估算，未逐条核对"）。
- `dishes.json`：列表，每项 `{"id", "name", "aliases": [], "category", "ingredients": [{"food": "<食物编号>", "grams": 数值}], "serving_grams", "tags": [], "note"}`。营养按"各食材每 100 克数值乘以用量后相加，再除以总用量换算回每 100 克"计算；食材某项营养缺失按 0 计，并在 note 中说明；烹调失水不计。出处为"自建菜品配方"，reference 为配方编号，授权状态 `personal_study_only`（因为数值来自成分表），note 写明配方为家常做法的估计。食材可以引用成分表食材或手动补充的食物（如食盐、白糖、酱油若成分表中没有）。
- 菜品继承其食材中 kind 为 `composition` 的标签（如含肉、含海鲜、含蛋、含奶、动物内脏、含酒精），其余标签（辛辣、油炸、生冷等）在菜品的 tags 中显式声明；营养学标签按菜品自身的营养数值计算。
- `portions.json`：`{"<食物编号>": {"<单位>": 克数}}`，至少覆盖下方常用食物中的米饭（碗）、馒头（个）、鸡蛋（个）、苹果（个）、香蕉（根）、牛奶（杯或盒）、包子（个）、饺子（个）；菜品与手动补充自动带有 serving_unit（菜品默认"份"）。`Food.default_grams` 取：菜品与补充用 serving_grams；食材取 portions 中按单位名排序的第一个，没有则 100。

标签（追加到 tags.json，`review_status` 一律为 `draft`，由验收时审核）：
- composition（按分类或名称）：`meat`（畜肉类与禽肉类）、`seafood`（鱼虾蟹贝类）、`egg`（蛋类）、`dairy`（乳类）、`organ_meat`（名称含肝、肾、腰子、心、肚、肠、肺、脑的畜禽产品）、`fatty_meat`（肥肉、五花肉、猪肉代表值等脂肪含量高的畜肉）、`alcohol`（酒类）
- culinary：`spicy`（辣椒、花椒及辛辣菜品）、`fried`（油炸、油条等）、`raw_cold`（冷饮、冰淇淋、生食、凉拌菜等）
- dietary：`fast_carb`（精米白面及其制品、糖与甜食等升糖较快的碳水）、`slow_carb`（全谷物、杂豆、薯类等）、`high_sugar`、`sweets`、`sugary_drink`、`caffeine`（咖啡、浓茶）、`high_purine`（动物内脏、部分海鲜、浓肉汤、啤酒等）
- tradition（依据必须写"传统饮食经验，缺少充分的现代医学证据"）：`cold_nature`（寒凉，如西瓜、梨、苦瓜、螃蟹、绿豆等）、`warm_nature`（温热，如羊肉、生姜、桂圆、红枣、红糖等）

`aliases.json` 必须让下面 100 个常用名都能以 `exact_name` 或 `exact_alias` 检索到第一位（可以通过常用名、成分表别名、菜品或补充食物的名称与别名实现），且每个都指向合理的食物（例如"鱼"指向一种常见淡水鱼，"虾"指向一种常见虾）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_data.py`
```python
import json

import pytest

from app.nutrition.catalog import DATA_DIR, LICENSE_PERSONAL_STUDY, LICENSE_SELF_ESTIMATE, load_catalog

COMMON_FOODS = [
    # 主食 20
    "米饭", "白粥", "小米粥", "馒头", "花卷", "包子", "饺子", "馄饨", "面条", "炒饭",
    "炒面", "油条", "烧饼", "面包", "玉米", "红薯", "土豆", "燕麦", "糙米饭", "年糕",
    # 早餐与饮品 10
    "豆浆", "牛奶", "酸奶", "鸡蛋", "咸鸭蛋", "茶叶蛋", "咖啡", "奶茶", "可乐", "橙汁",
    # 蔬菜 15
    "西红柿", "黄瓜", "大白菜", "菠菜", "生菜", "西兰花", "胡萝卜", "茄子", "青椒", "冬瓜",
    "南瓜", "豆芽", "芹菜", "苦瓜", "蘑菇",
    # 水果 10
    "苹果", "香蕉", "橙子", "梨", "西瓜", "葡萄", "草莓", "桃", "猕猴桃", "柚子",
    # 肉蛋豆 15
    "猪肉", "五花肉", "牛肉", "羊肉", "鸡胸肉", "鸡腿", "鸭肉", "猪肝", "鱼", "带鱼",
    "虾", "螃蟹", "豆腐", "豆腐干", "花生",
    # 菜品 25
    "番茄炒蛋", "宫保鸡丁", "鱼香肉丝", "红烧肉", "麻婆豆腐", "青椒肉丝", "糖醋排骨", "回锅肉", "地三鲜", "清炒西兰花",
    "蒜蓉菠菜", "醋溜白菜", "红烧鱼", "清蒸鱼", "水煮鱼", "酸辣土豆丝", "可乐鸡翅", "炸鸡", "凉拌黄瓜", "紫菜蛋花汤",
    "西红柿鸡蛋汤", "火锅", "麻辣烫", "炸酱面", "牛肉面",
    # 其他 5
    "白酒", "啤酒", "红酒", "蛋糕", "冰淇淋",
]


def _food(name):
    return load_catalog().search(name)[0].food


def test_common_food_list_has_one_hundred_distinct_names():
    assert len(COMMON_FOODS) == 100
    assert len(set(COMMON_FOODS)) == 100


@pytest.mark.parametrize("name", COMMON_FOODS)
def test_common_food_is_found_exactly(name):
    hits = load_catalog().search(name)
    assert hits, f"{name} 未找到"
    assert hits[0].match in ("exact_name", "exact_alias"), (name, hits[0].food.name, hits[0].match)


def test_dishes_are_well_formed_and_computed_from_recipe():
    catalog = load_catalog()
    raw = json.loads((DATA_DIR / "dishes.json").read_text("utf-8"))
    assert len(raw) >= 40
    for dish in raw:
        assert dish["serving_grams"] > 0
        total = 0.0
        energy = 0.0
        for ingredient in dish["ingredients"]:
            food = catalog.get(ingredient["food"])
            assert food is not None, (dish["id"], ingredient["food"])
            assert ingredient["grams"] > 0
            total += ingredient["grams"]
            energy += (food.nutrients.energy_kcal or 0) * ingredient["grams"] / 100
        computed = catalog.get(f"dish:{dish['id']}")
        assert computed.kind == "dish"
        assert computed.nutrients.energy_kcal == pytest.approx(energy / total * 100)
        assert computed.source.license_status == LICENSE_PERSONAL_STUDY
        assert computed.source.reference == dish["id"]
        assert computed.default_grams == dish["serving_grams"]


def test_dishes_inherit_composition_tags():
    assert "meat" in _food("宫保鸡丁").tags
    assert "egg" in _food("番茄炒蛋").tags
    assert "seafood" in _food("清蒸鱼").tags


def test_supplements_are_marked_as_unverified_estimates():
    for food in load_catalog().foods.values():
        if food.kind == "supplement":
            assert food.source.license_status == LICENSE_SELF_ESTIMATE
            assert "估算" in food.source.note


def test_every_tag_used_is_defined_and_tradition_is_labelled():
    catalog = load_catalog()
    for food in catalog.foods.values():
        assert food.tags <= set(catalog.tags), food.id
    for tag in catalog.tags.values():
        if tag.kind == "tradition":
            assert "传统" in tag.basis
    expected_kinds = {
        "meat": "composition", "seafood": "composition", "egg": "composition", "dairy": "composition",
        "organ_meat": "composition", "fatty_meat": "composition", "alcohol": "composition",
        "spicy": "culinary", "fried": "culinary", "raw_cold": "culinary",
        "fast_carb": "dietary", "slow_carb": "dietary", "high_sugar": "dietary", "sweets": "dietary",
        "sugary_drink": "dietary", "caffeine": "dietary", "high_purine": "dietary",
        "cold_nature": "tradition", "warm_nature": "tradition",
    }
    assert {tag: catalog.tags[tag].kind for tag in expected_kinds} == expected_kinds


@pytest.mark.parametrize(
    ("name", "tag"),
    [
        ("啤酒", "alcohol"), ("白酒", "alcohol"), ("红酒", "alcohol"),
        ("麻婆豆腐", "spicy"), ("水煮鱼", "spicy"), ("酸辣土豆丝", "spicy"), ("麻辣烫", "spicy"), ("宫保鸡丁", "spicy"),
        ("油条", "fried"), ("炸鸡", "fried"), ("冰淇淋", "raw_cold"), ("凉拌黄瓜", "raw_cold"),
        ("猪肝", "organ_meat"), ("五花肉", "fatty_meat"), ("红烧肉", "fatty_meat"),
        ("蛋糕", "sweets"), ("可乐", "sugary_drink"), ("奶茶", "sugary_drink"), ("咖啡", "caffeine"),
        ("猪肝", "high_purine"), ("西瓜", "cold_nature"), ("梨", "cold_nature"), ("苦瓜", "cold_nature"),
        ("羊肉", "warm_nature"), ("米饭", "fast_carb"), ("燕麦", "slow_carb"), ("鸡胸肉", "meat"),
        ("带鱼", "seafood"), ("牛奶", "dairy"),
    ],
)
def test_expected_tags(name, tag):
    assert tag in _food(name).tags, (name, _food(name).name, sorted(_food(name).tags))


def test_plain_foods_do_not_get_wrong_tags():
    assert "spicy" not in _food("番茄炒蛋").tags
    assert "alcohol" not in _food("米饭").tags
    assert "cold_nature" not in _food("羊肉").tags


def test_portions():
    rice = _food("米饭")
    assert dict(rice.portions)["碗"] > 0
    assert dict(_food("鸡蛋").portions)["个"] > 0
    assert _food("番茄炒蛋").default_grams > 0
    assert dict(_food("番茄炒蛋").portions)["份"] == _food("番茄炒蛋").default_grams


def test_aliases_are_unique_across_foods():
    catalog = load_catalog()
    seen = {}
    for food in catalog.foods.values():
        if food.kind == "ingredient":
            continue
        for name in (food.name, *food.aliases):
            assert name not in seen, (name, seen.get(name), food.id)
            seen[name] = food.id
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_nutrition_data.py -q`
Expected: FAIL（菜品、补充与大部分常用名尚不存在）

- [ ] **Step 3: 扩展 catalog 加载**

在 `catalog.py` 中：
- 增加 pydantic 模型 `_SupplementEntry`、`_DishIngredient`、`_DishEntry`（`extra="forbid"`），以及 `_load_supplements()`、`_load_dishes(base_foods: dict[str, Food])`、`_load_portions(food_ids)`；
- 菜品营养：`total = sum(grams)`；每项营养 `sum(per100 × grams / 100) / total × 100`，缺失按 0；
- 菜品的初始 tags = 显式声明的 tags ∪ 各食材（已经过 `assign_tags` 的结果）中 kind 为 `composition` 的标签；之后再对菜品执行一次 `assign_tags`（得到营养学标签与按名称匹配的成员）；
- 份量：菜品与补充自动带 `(serving_unit 或 "份", serving_grams)`；portions.json 中的单位合并进去；`portions` 按单位名排序成元组；
- `load_catalog()` 的顺序：加载成分表食材与补充 → 先给它们打标签 → 计算菜品（用已打标签的食材） → 给菜品打标签 → 合并份量 → 构建 Catalog；
- 校验：编号唯一；菜品食材必须存在；份量引用的食物必须存在；声明的标签必须在 tags.json 中定义；违反时抛 `ValueError` 并说明是哪一项。

- [ ] **Step 4: 编写数据**

按上面的格式与要求编写 `supplements.json`、`dishes.json`（不少于 40 道，必须包含 COMMON_FOODS 中的全部菜品，以及包子、饺子、馄饨、炒饭、炒面、花卷、茶叶蛋、糙米饭等成品主食，其余选常见家常菜）、`portions.json`，补全 `aliases.json` 与 `tags.json`。配方用量按普通家常一份估计，食用油、盐等调料要计入。从 CSV 中查找食材编号时优先用"代表值"条目。

- [ ] **Step 5: 运行确认通过**

Run: `uv run pytest tests/test_nutrition_data.py tests/test_nutrition_catalog.py -q`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。

- [ ] **Step 6: 提交**

```
git add backend/app/nutrition backend/tests/test_nutrition_data.py
git commit -m "feat(nutrition): add dish recipes, supplements, portions and reviewed tag membership"
```

---

### Task 3: 需求估算、饮食记录、每日汇总与基础接口

**Files:**
- Create: `backend/app/nutrition/needs.py`, `models.py`, `meals.py`, `schemas.py`, `deps.py`, `router.py`
- Create: `backend/migrations/versions/0008_nutrition.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`, `backend/tests/test_route_guards.py`
- Test: `backend/tests/test_nutrition_needs.py`, `backend/tests/test_nutrition_meals.py`

**Interfaces:**
- Consumes: catalog；`owned_by`、`get_owned_or_404`、`EncryptedJSON`、`AppError`、`get_today`、`require_disclaimer_user`、`get_or_create_profile`、`compute_capabilities`、`tests.helpers.ready_user`
- Produces:
  - `app.nutrition.needs`：`Needs`（status、missing_fields、energy_kcal、energy_kcal_low、energy_kcal_high、protein_g、fat_g_low、fat_g_high、carbohydrate_g_low、carbohydrate_g_high、fiber_g_low、fiber_g_high、sodium_mg_max、notes）、`estimate_needs(*, gender, birth_year, height_cm, weight_kg, activity_level, goal, today) -> Needs`、`needs_for_profile(profile, today) -> Needs`、常量
  - ORM `MealEntry`（表 `meal_entries`）
  - `app.nutrition.meals`：`MEAL_TYPES`、`resolve_grams(food, grams, portion) -> float`、`log_meal(...)`、`update_meal(...)`、`delete_meal(...)`、`list_meals(db, user_id, day)`、`day_totals(db, user_id, day) -> Nutrients`、`daily_summary(db, user_id, day, needs) -> DailySummary`
  - `app.nutrition.deps.require_nutrition_user`
  - 接口（前缀 `/api/nutrition`）：GET `/foods/search?q=`、GET `/foods/{food_id}`、GET `/tags`、POST/GET `/meals`、PATCH/DELETE `/meals/{entry_id}`、GET `/summary?date=`、GET `/needs`
  - 错误码：`food_not_found`(404)、`invalid_portion`(422)、`meal_in_future`(422)、`nutrition_not_available`(403)

需求估算（`needs.py`）：
- 缺少出生年份、身高、体重、活动水平中的任何一项 → status `insufficient_profile`，列出缺失字段，其余为空。
- 年龄 = 今天的年份 − 出生年份；基础代谢 = 10 × 体重 + 6.25 × 身高 − 5 × 年龄 + 性别常数（男 +5、女 −161、未填或其他 −78）。
- 活动系数：sedentary 1.2、light 1.375、moderate 1.55、active 1.725、very_active 1.9；目标系数：lose_fat 0.85、gain_muscle 1.10、其余 1.0。
- 能量 = 四舍五入（基础代谢 × 活动系数 × 目标系数）；范围为能量的 90% 至 110%（各自四舍五入）。
- 蛋白质 = 四舍五入（体重 × 每千克克数：减脂 1.2、增肌 1.6、其余 1.0）。
- 脂肪 = 能量 × 20% ÷ 9 至 能量 × 30% ÷ 9；碳水 = 能量 × 50% ÷ 4 至 能量 × 65% ÷ 4（四舍五入）；膳食纤维 25 至 30 克；钠上限 2000 毫克。
- notes 总是包含"以上是根据档案估算的大致需求，不是医疗指标；有医嘱或慢性病时以医嘱为准。"；未填性别加一句按中间值估算；未满 18 岁加一句请咨询医生或营养师。

手算样例：女，1998 年生，162.5 厘米，52 千克，light，lose_fat，今天 2026-10-06 → 年龄 28，基础代谢 1234.625，能量 1443（范围 1299 至 1587），蛋白质 62，脂肪 32 至 48，碳水 180 至 234。男，1990 年生，175 厘米，70 千克，moderate，gain_muscle → 能量 2760（2484 至 3036），蛋白质 112。

饮食记录：
- `meal_entries`：id、user_id、eaten_on（日期）、meal_type（breakfast、lunch、dinner、snack）、food_id、food_name、grams、8 个营养快照列（可空）、note（加密，可空）、created_at、updated_at。
- 记录时按"食物每 100 克营养 × 克数 ÷ 100"计算快照；修改食物或克数时重算快照。
- 克数来源：直接给 grams（大于 0，不超过 5000），或给 portion `{unit, count}`（单位必须是该食物的份量单位之一，count 大于 0 不超过 20），二者必须且只能给一个，否则 `invalid_portion`。
- 日期不能晚于今天（`meal_in_future`）。食物编号不存在 → `food_not_found`。
- 每日汇总：按餐次与全天汇总 8 项营养（缺失按 0 并在 `incomplete_fields` 中列出），四舍五入到 1 位小数；附上需求估算与剩余量（能量剩余 = 目标能量 − 已摄入，蛋白质剩余同理，钠剩余 = 上限 − 已摄入）；需求不足时剩余量为空。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_needs.py`
```python
from datetime import date

from app.nutrition.needs import estimate_needs

TODAY = date(2026, 10, 6)


def test_female_lose_fat_example():
    needs = estimate_needs(
        gender="female", birth_year=1998, height_cm=162.5, weight_kg=52, activity_level="light", goal="lose_fat",
        today=TODAY,
    )
    assert needs.status == "ok"
    assert (needs.energy_kcal, needs.energy_kcal_low, needs.energy_kcal_high) == (1443, 1299, 1587)
    assert needs.protein_g == 62
    assert (needs.fat_g_low, needs.fat_g_high) == (32, 48)
    assert (needs.carbohydrate_g_low, needs.carbohydrate_g_high) == (180, 234)
    assert (needs.fiber_g_low, needs.fiber_g_high, needs.sodium_mg_max) == (25, 30, 2000)
    assert any("不是医疗指标" in note for note in needs.notes)


def test_male_gain_muscle_example():
    needs = estimate_needs(
        gender="male", birth_year=1990, height_cm=175, weight_kg=70, activity_level="moderate", goal="gain_muscle",
        today=TODAY,
    )
    assert (needs.energy_kcal, needs.energy_kcal_low, needs.energy_kcal_high) == (2760, 2484, 3036)
    assert needs.protein_g == 112


def test_missing_profile_fields():
    needs = estimate_needs(
        gender="female", birth_year=None, height_cm=160, weight_kg=None, activity_level="light", goal=None,
        today=TODAY,
    )
    assert needs.status == "insufficient_profile"
    assert needs.missing_fields == ("birth_year", "weight_kg")
    assert needs.energy_kcal is None


def test_unspecified_gender_and_minor_notes():
    needs = estimate_needs(
        gender=None, birth_year=2012, height_cm=150, weight_kg=40, activity_level="light", goal=None, today=TODAY,
    )
    assert needs.status == "ok"
    assert any("中间值" in note for note in needs.notes)
    assert any("医生或营养师" in note for note in needs.notes)
```

`backend/tests/test_nutrition_meals.py`
```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from app.nutrition.catalog import load_catalog, round_one
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 10, 6)
RICE = "cfcd:012401x"
EGG = "cfcd:111101x"
PROFILE = {
    "gender": "female", "birth_year": 1998, "height_cm": 162.5, "weight_kg": 52,
    "activity_level": "light", "goal": "lose_fat",
}


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _log(client, headers, food_id, meal_type="lunch", **amount):
    body = {"eaten_on": "2026-10-06", "meal_type": meal_type, "food_id": food_id, **amount}
    response = client.post("/api/nutrition/meals", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_search_and_food_detail(client):
    headers = ready_user(client, "alice")
    body = client.get("/api/nutrition/foods/search", params={"q": "米饭"}, headers=headers).json()
    assert body["found"] is True
    assert body["results"][0]["id"] == RICE
    assert body["results"][0]["match"] == "exact_name"
    missing = client.get("/api/nutrition/foods/search", params={"q": "完全不存在的食物名称"}, headers=headers).json()
    assert (missing["found"], missing["results"]) == (False, [])
    assert "未找到" in missing["message"]
    detail = client.get(f"/api/nutrition/foods/{RICE}", headers=headers).json()
    assert detail["nutrients_per_100g"]["energy_kcal"] == 116
    assert detail["source"]["license_status"] == "personal_study_only"
    assert isinstance(detail["tags"], list)
    assert all({"id", "name", "kind", "basis"} <= set(tag) for tag in detail["tags"])
    assert client.get("/api/nutrition/foods/cfcd:nope", headers=headers).json()["error"]["code"] == "food_not_found"
    tags = client.get("/api/nutrition/tags", headers=headers).json()
    assert any(tag["kind"] == "tradition" and "传统" in tag["basis"] for tag in tags)


def test_daily_summary_matches_hand_calculation(client):
    headers = ready_user(client, "alice", PROFILE)
    catalog = load_catalog()
    plan = [("breakfast", EGG, 50), ("breakfast", RICE, 100), ("lunch", RICE, 150), ("dinner", RICE, 200)]
    for meal_type, food_id, grams in plan:
        _log(client, headers, food_id, meal_type, grams=grams)
    summary = client.get("/api/nutrition/summary", params={"date": "2026-10-06"}, headers=headers).json()
    expected_energy = sum(catalog.get(f).nutrients.energy_kcal * g / 100 for _, f, g in plan)
    assert summary["total"]["energy_kcal"] == round_one(expected_energy)
    assert summary["meals"]["lunch"]["energy_kcal"] == 174.0
    assert summary["meals"]["snack"]["energy_kcal"] == 0
    expected_protein = sum(catalog.get(f).nutrients.protein_g * g / 100 for _, f, g in plan)
    assert summary["total"]["protein_g"] == round_one(expected_protein)
    assert summary["needs"]["energy_kcal"] == 1443
    assert summary["remaining"]["energy_kcal"] == round_one(1443 - expected_energy)


def test_portion_units_and_validation(client):
    headers = ready_user(client, "alice")
    food = load_catalog().get(RICE)
    bowl = dict(food.portions)["碗"]
    entry = _log(client, headers, RICE, portion={"unit": "碗", "count": 2})
    assert entry["grams"] == bowl * 2
    bad = [
        {"food_id": RICE},
        {"food_id": RICE, "grams": 100, "portion": {"unit": "碗", "count": 1}},
        {"food_id": RICE, "portion": {"unit": "桶", "count": 1}},
        {"food_id": RICE, "grams": 0},
    ]
    for extra in bad:
        body = {"eaten_on": "2026-10-06", "meal_type": "lunch", **extra}
        assert client.post("/api/nutrition/meals", json=body, headers=headers).status_code == 422, extra
    future = {"eaten_on": "2026-10-07", "meal_type": "lunch", "food_id": RICE, "grams": 100}
    assert client.post("/api/nutrition/meals", json=future, headers=headers).json()["error"]["code"] == "meal_in_future"
    unknown = {"eaten_on": "2026-10-06", "meal_type": "lunch", "food_id": "cfcd:nope", "grams": 100}
    assert client.post("/api/nutrition/meals", json=unknown, headers=headers).json()["error"]["code"] == "food_not_found"


def test_update_and_delete_meal(client):
    headers = ready_user(client, "alice")
    entry = _log(client, headers, RICE, grams=100)
    updated = client.patch(f"/api/nutrition/meals/{entry['id']}", json={"grams": 200}, headers=headers).json()
    assert updated["nutrients"]["energy_kcal"] == 232.0
    switched = client.patch(f"/api/nutrition/meals/{entry['id']}", json={"food_id": EGG}, headers=headers).json()
    assert switched["food_id"] == EGG
    assert client.delete(f"/api/nutrition/meals/{entry['id']}", headers=headers).status_code == 204
    assert client.get("/api/nutrition/meals", params={"date": "2026-10-06"}, headers=headers).json() == []


def test_meals_are_private(client):
    alice = ready_user(client, "alice")
    entry = _log(client, alice, RICE, grams=100, note="私密备注")
    bella = ready_user(client, "bella")
    assert client.get("/api/nutrition/meals", params={"date": "2026-10-06"}, headers=bella).json() == []
    assert client.patch(f"/api/nutrition/meals/{entry['id']}", json={"grams": 1}, headers=bella).status_code == 404
    assert client.delete(f"/api/nutrition/meals/{entry['id']}", headers=bella).status_code == 404
    summary = client.get("/api/nutrition/summary", params={"date": "2026-10-06"}, headers=bella).json()
    assert summary["total"]["energy_kcal"] == 0


def test_needs_endpoint(client):
    complete = ready_user(client, "alice", PROFILE)
    assert client.get("/api/nutrition/needs", headers=complete).json()["energy_kcal"] == 1443
    incomplete = ready_user(client, "bella")
    body = client.get("/api/nutrition/needs", headers=incomplete).json()
    assert body["status"] == "insufficient_profile"


def test_nutrition_requires_login_and_disclaimer(client):
    assert client.get("/api/nutrition/tags").status_code == 401
    headers = register_and_login(client, "carl")
    assert client.get("/api/nutrition/tags", headers=headers).json()["error"]["code"] == "disclaimer_not_accepted"
```

在 `test_route_guards.py` 末尾追加：
```python
def test_every_nutrition_route_requires_nutrition_user():
    from app.nutrition.deps import require_nutrition_user

    routes = [ctx for ctx in _api_routes(create_app()) if ctx.path.startswith("/api/nutrition/")]
    assert len(routes) >= 9
    missing = [ctx.path for ctx in routes if require_nutrition_user not in _dependency_calls(ctx.dependant)]
    assert missing == []
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_nutrition_needs.py tests/test_nutrition_meals.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 needs**

`backend/app/nutrition/needs.py`
```python
"""每日能量与营养素需求估算（Mifflin-St Jeor 公式乘活动系数）。只是估算，不是医疗指标。"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.nutrition.catalog import round_half_up

ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
GOAL_ENERGY_FACTORS = {"lose_fat": 0.85, "gain_muscle": 1.10}
PROTEIN_G_PER_KG = {"lose_fat": 1.2, "gain_muscle": 1.6}
DEFAULT_PROTEIN_G_PER_KG = 1.0
SEX_CONSTANTS = {"male": 5, "female": -161}
UNSPECIFIED_SEX_CONSTANT = -78  # 男女常数的中间值
ENERGY_RANGE = 0.10
FAT_ENERGY_SHARE = (0.20, 0.30)
CARB_ENERGY_SHARE = (0.50, 0.65)
FIBER_G = (25, 30)
SODIUM_MG_MAX = 2000
ESTIMATE_NOTE = "以上是根据档案估算的大致需求，不是医疗指标；有医嘱或慢性病时以医嘱为准。"
UNSPECIFIED_SEX_NOTE = "档案没有填写男女，按男女公式的中间值估算。"
MINOR_NOTE = "未成年人的营养需求与成人不同，请咨询医生或营养师。"
INSUFFICIENT_NOTE = "档案缺少估算所需的信息，补充后才能估算每日需求。"


@dataclass(frozen=True)
class Needs:
    status: str  # ok / insufficient_profile
    missing_fields: tuple[str, ...] = ()
    energy_kcal: int | None = None
    energy_kcal_low: int | None = None
    energy_kcal_high: int | None = None
    protein_g: int | None = None
    fat_g_low: int | None = None
    fat_g_high: int | None = None
    carbohydrate_g_low: int | None = None
    carbohydrate_g_high: int | None = None
    fiber_g_low: int | None = None
    fiber_g_high: int | None = None
    sodium_mg_max: int | None = None
    notes: tuple[str, ...] = ()


def estimate_needs(
    *,
    gender: str | None,
    birth_year: int | None,
    height_cm: float | None,
    weight_kg: float | None,
    activity_level: str | None,
    goal: str | None,
    today: date,
) -> Needs:
    required = (
        ("birth_year", birth_year), ("height_cm", height_cm), ("weight_kg", weight_kg),
        ("activity_level", activity_level),
    )
    missing = tuple(name for name, value in required if value is None)
    if missing:
        return Needs(status="insufficient_profile", missing_fields=missing, notes=(INSUFFICIENT_NOTE,))
    age = today.year - birth_year
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + SEX_CONSTANTS.get(gender, UNSPECIFIED_SEX_CONSTANT)
    energy = round_half_up(bmr * ACTIVITY_FACTORS[activity_level] * GOAL_ENERGY_FACTORS.get(goal, 1.0))
    notes = [ESTIMATE_NOTE]
    if gender not in SEX_CONSTANTS:
        notes.append(UNSPECIFIED_SEX_NOTE)
    if age < 18:
        notes.append(MINOR_NOTE)
    return Needs(
        status="ok",
        energy_kcal=energy,
        energy_kcal_low=round_half_up(energy * (1 - ENERGY_RANGE)),
        energy_kcal_high=round_half_up(energy * (1 + ENERGY_RANGE)),
        protein_g=round_half_up(weight_kg * PROTEIN_G_PER_KG.get(goal, DEFAULT_PROTEIN_G_PER_KG)),
        fat_g_low=round_half_up(energy * FAT_ENERGY_SHARE[0] / 9),
        fat_g_high=round_half_up(energy * FAT_ENERGY_SHARE[1] / 9),
        carbohydrate_g_low=round_half_up(energy * CARB_ENERGY_SHARE[0] / 4),
        carbohydrate_g_high=round_half_up(energy * CARB_ENERGY_SHARE[1] / 4),
        fiber_g_low=FIBER_G[0],
        fiber_g_high=FIBER_G[1],
        sodium_mg_max=SODIUM_MG_MAX,
        notes=tuple(notes),
    )


def needs_for_profile(profile: Any, today: date) -> Needs:
    return estimate_needs(
        gender=profile.gender,
        birth_year=profile.birth_year,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        goal=profile.goal,
        today=today,
    )
```

- [ ] **Step 4: 模型、迁移与饮食记录服务**

`backend/app/nutrition/models.py`
```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class MealEntry(UserOwnedMixin, Base):
    """一次饮食记录。营养为记录时按克数计算的快照；备注加密。"""

    __tablename__ = "meal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    eaten_on: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String(16))
    food_id: Mapped[str] = mapped_column(String(64))
    food_name: Mapped[str] = mapped_column(String(128))
    grams: Mapped[float] = mapped_column(Float)
    energy_kcal: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    carbohydrate_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    iron_mg: Mapped[float | None] = mapped_column(Float)
    calcium_mg: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`backend/app/models.py` 追加 `from app.nutrition import models as nutrition_models  # noqa: F401`。

`backend/migrations/versions/0008_nutrition.py`：revision `"0008_nutrition"`，down_revision `"0007_medical"`；创建 `meal_entries` 与上面模型逐列一致（营养列 `sa.Float()` 可空，note `sa.Text()` 可空，created_at、updated_at 带 `server_default=sa.func.now()`），并创建索引 `ix_meal_entries_user_id`；downgrade 删除索引与表。

`backend/app/nutrition/meals.py`
```python
"""饮食记录与每日汇总。"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.nutrition.catalog import NUTRIENT_FIELDS, Food, Nutrients, load_catalog
from app.nutrition.models import MealEntry
from app.nutrition.needs import Needs

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
MAX_GRAMS = 5000
MAX_PORTION_COUNT = 20


@dataclass(frozen=True)
class DailySummary:
    day: date
    meals: dict[str, Nutrients]
    total: Nutrients
    incomplete_fields: tuple[str, ...]
    needs: Needs
    remaining: dict[str, float] | None


def get_food(food_id: str) -> Food:
    food = load_catalog().get(food_id)
    if food is None:
        raise AppError(404, "food_not_found", "营养库里没有这个食物")
    return food


def resolve_grams(food: Food, grams: float | None, portion: dict[str, Any] | None) -> float:
    if (grams is None) == (portion is None):
        raise AppError(422, "invalid_portion", "请填写克数或份量其中一项")
    if grams is not None:
        if not 0 < grams <= MAX_GRAMS:
            raise AppError(422, "invalid_portion", f"克数需要大于 0 且不超过 {MAX_GRAMS}")
        return float(grams)
    units = dict(food.portions)
    unit, count = portion["unit"], portion["count"]
    if unit not in units:
        raise AppError(422, "invalid_portion", f"这个食物没有“{unit}”这个份量单位，可选：{'、'.join(units) or '无'}")
    if not 0 < count <= MAX_PORTION_COUNT:
        raise AppError(422, "invalid_portion", f"份数需要大于 0 且不超过 {MAX_PORTION_COUNT}")
    return units[unit] * count


def _apply_snapshot(entry: MealEntry, food: Food, grams: float) -> None:
    entry.food_id, entry.food_name, entry.grams = food.id, food.name, grams
    serving = food.nutrients.scaled(grams)
    for name in NUTRIENT_FIELDS:
        setattr(entry, name, getattr(serving, name))


def entry_nutrients(entry: MealEntry) -> Nutrients:
    return Nutrients(**{name: getattr(entry, name) for name in NUTRIENT_FIELDS})


def log_meal(
    db: Session,
    user_id: uuid.UUID,
    *,
    eaten_on: date,
    meal_type: str,
    food_id: str,
    grams: float | None,
    portion: dict[str, Any] | None,
    note: str | None,
    today: date,
) -> MealEntry:
    if eaten_on > today:
        raise AppError(422, "meal_in_future", "不能记录未来日期的饮食")
    food = get_food(food_id)
    entry = MealEntry(user_id=user_id, eaten_on=eaten_on, meal_type=meal_type, note=note)
    _apply_snapshot(entry, food, resolve_grams(food, grams, portion))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_meal(
    db: Session, user_id: uuid.UUID, entry_id: uuid.UUID, changes: dict[str, Any], today: date
) -> MealEntry:
    entry = get_owned_or_404(db, MealEntry, user_id, entry_id)
    eaten_on = changes.get("eaten_on", entry.eaten_on)
    if eaten_on > today:
        raise AppError(422, "meal_in_future", "不能记录未来日期的饮食")
    food = get_food(changes.get("food_id", entry.food_id))
    if "grams" in changes or "portion" in changes:
        grams = resolve_grams(food, changes.get("grams"), changes.get("portion"))
    else:
        grams = entry.grams
    entry.eaten_on = eaten_on
    entry.meal_type = changes.get("meal_type", entry.meal_type)
    if "note" in changes:
        entry.note = changes["note"]
    _apply_snapshot(entry, food, grams)
    db.commit()
    db.refresh(entry)
    return entry


def delete_meal(db: Session, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, MealEntry, user_id, entry_id))
    db.commit()


def list_meals(db: Session, user_id: uuid.UUID, day: date) -> list[MealEntry]:
    entries = db.scalars(owned_by(MealEntry, user_id).where(MealEntry.eaten_on == day)).all()
    return sorted(entries, key=lambda e: (MEAL_TYPES.index(e.meal_type), e.created_at, str(e.id)))


def day_totals(db: Session, user_id: uuid.UUID, day: date) -> Nutrients:
    total = Nutrients(**{name: 0.0 for name in NUTRIENT_FIELDS})
    for entry in list_meals(db, user_id, day):
        total = total.plus(entry_nutrients(entry))
    return total


def daily_summary(db: Session, user_id: uuid.UUID, day: date, needs: Needs) -> DailySummary:
    zero = Nutrients(**{name: 0.0 for name in NUTRIENT_FIELDS})
    meals = {meal_type: zero for meal_type in MEAL_TYPES}
    incomplete: set[str] = set()
    total = zero
    for entry in list_meals(db, user_id, day):
        nutrients = entry_nutrients(entry)
        incomplete.update(name for name in NUTRIENT_FIELDS if getattr(nutrients, name) is None)
        meals[entry.meal_type] = meals[entry.meal_type].plus(nutrients)
        total = total.plus(nutrients)
    remaining = None
    if needs.status == "ok":
        remaining = {
            "energy_kcal": needs.energy_kcal - total.energy_kcal,
            "protein_g": needs.protein_g - total.protein_g,
            "sodium_mg": needs.sodium_mg_max - total.sodium_mg,
        }
    return DailySummary(day, meals, total, tuple(sorted(incomplete)), needs, remaining)
```

- [ ] **Step 5: schemas、deps、router**

`backend/app/nutrition/schemas.py`：定义
- `NutrientsOut`（8 个字段，`float | None`，序列化前用 `round_one` 四舍五入到 1 位小数——在路由里用 `nutrients_out(n)` 辅助函数构建）；
- `TagOut(id, name, kind, basis, review_status)`；`SourceOut(dataset, reference, license_status, note)`；`PortionOut(unit, grams)`；
- `FoodSummaryOut(id, name, aliases, category, kind, match)`、`SearchOut(query, found, results, message)`（`message` 在找不到时为"未找到与“<查询>”匹配的食物，请换个说法或检查错别字"，找到时为空）；
- `FoodDetailOut(id, name, aliases, category, kind, nutrients_per_100g, tags: list[TagOut]（按 kind 再按 id 排序）, portions: list[PortionOut], default_grams, source)`；
- `PortionIn(unit: 1 至 8 字, count: float)`（extra forbid）；`MealCreate(eaten_on, meal_type: Literal[四种], food_id: str 1 至 64 字, grams: float | None, portion: PortionIn | None, note: str | None 最多 200 字)`；`MealUpdate`（同字段全部可选，extra forbid；eaten_on、meal_type、food_id 显式传 null 时 422）；
- `MealOut(id, eaten_on, meal_type, food_id, food_name, grams, nutrients: NutrientsOut, note, created_at, updated_at)`；
- `NeedsOut`（Needs 的全部字段，missing_fields 与 notes 为列表）；
- `SummaryOut(date, meals: dict[str, NutrientsOut], total: NutrientsOut, incomplete_fields, needs: NeedsOut, remaining: dict[str, float] | None（四舍五入 1 位）, disclaimer)`，disclaimer 为"以上汇总与需求都是估算，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。"。

`backend/app/nutrition/deps.py`：`require_nutrition_user`，结构与 `app/medical/deps.py` 相同：依赖 `require_disclaimer_user`，按 `compute_capabilities(...)["nutrition"]` 判断，不开放时 403 `nutrition_not_available`（"饮食功能当前不可用"）；不需要刷新任何状态。

`backend/app/nutrition/router.py`（前缀 `/api/nutrition`，全部依赖 `NutritionUser = Annotated[User, Depends(require_nutrition_user)]`）：
- GET `/foods/search`（q 必填，1 至 50 字）→ SearchOut；
- GET `/foods/{food_id}` → FoodDetailOut（`food_id` 用 `{food_id}` 普通路径参数，编号里的冒号在路径中合法）；
- GET `/tags` → list[TagOut]（按 kind、id 排序）；
- POST `/meals`（201）→ MealOut；GET `/meals?date=`（默认今天）→ list[MealOut]；PATCH `/meals/{entry_id}` → MealOut；DELETE `/meals/{entry_id}`（204）；
- GET `/summary?date=`（默认今天）→ SummaryOut，需求用 `needs_for_profile(get_or_create_profile(...), today)`；
- GET `/needs` → NeedsOut。

`backend/app/main.py`：include `nutrition_router`（放在 medical_router 之后）。

- [ ] **Step 6: 运行确认通过**

Run: `uv run pytest tests/test_nutrition_needs.py tests/test_nutrition_meals.py tests/test_route_guards.py -q`，然后 `uv run pytest -q -W error`，再对开发库执行 `uv run alembic upgrade head`
Expected: 全部通过、无警告；开发库迁移到 0008。

- [ ] **Step 7: 提交**

```
git add backend/app backend/migrations backend/tests
git commit -m "feat(nutrition): add needs estimation, meal logging, daily summary and food APIs"
```

---

### Task 4: 约束融合引擎、词汇表与软规则

**Files:**
- Create: `backend/app/nutrition/rules.py`, `backend/app/nutrition/engine.py`
- Create: `backend/app/nutrition/data/vocabulary.json`, `backend/app/nutrition/data/soft_rules.json`
- Test: `backend/tests/test_nutrition_engine.py`

**Interfaces:**
- Consumes: catalog（`Catalog`、`Food`、`Nutrients`、`TagDefinition`、`Source`、`round_one`）、needs（`Needs`）
- Produces:
  - `app.nutrition.rules`：`VocabularyEntry(tags, non_food, violates, prefers, unverifiable, not_applicable)`、`Vocabulary.lookup(term) -> VocabularyEntry | None`、`CycleRule(tags, effect, tradition, tip_id, message)`、`GoalRule(tags, effect, message)`、`SoftRules(cycle: dict[str, tuple[CycleRule,...]], goals: dict[str, tuple[GoalRule,...]])`、`load_vocabulary()`、`load_soft_rules()`（均带缓存，pydantic 校验，引用的标签必须在 tags.json 中定义）
  - `app.nutrition.engine`：常量 `SUITABLE`、`CAUTION`、`NOT_RECOMMENDED`、`SOURCE_ORDER`、`EFFECT_ORDER`、`SOURCE_NAMES`、`DISCLAIMER`；数据类 `HardConstraint(item_id, category, content, subjects, needs_review)`、`EvaluationContext(constraints, cycle_phase, goal, needs, day_totals, food_avoidances, diet_preferences)`、`Reason(source, effect, code, message, ref)`、`Evaluation(food_id, food_name, grams, nutrients, conclusion, reasons, tradeoff, data_source, disclaimer)`、`MealEvaluation(items, conclusion, total, disclaimer)`；函数 `evaluate_food(food, grams, context, catalog) -> Evaluation`、`evaluate_meal(items, context, catalog) -> MealEvaluation`

词汇表 `vocabulary.json`：`{"terms": {"<说法>": {...}}}`，每个说法恰好是下列一种：
- `{"tags": [...]}`：避免类说法对应的食物标签（用于医嘱的饮食禁忌、用药相关饮食注意，以及档案里的个人忌口）；
- `{"non_food": true}`：不是食物（如烟、吸烟），判断食物时跳过；
- `{"violates": [...], "prefers": [...]}`：要求类说法（用于医嘱的饮食要求与档案里的饮食偏好），食物带 violates 中的标签即不符合，带 prefers 中的标签即符合（两者至少有一项非空）；
- `{"unverifiable": true}`：无法从营养数据判断（如流质、半流质、软食）；
- `{"not_applicable": true}`：与具体食物无关（如少量多餐、多喝水、多饮水）。
查找时先按原样查，查不到再去掉结尾的"食物""食品""类""饮食"后查。至少包含：辛辣、辣、辣椒、麻辣、刺激性食物 → spicy；油腻、油炸、油炸食物、煎炸 → fried 与 high_fat（油腻）或 fried（油炸类）；生冷、生冷食物、冷饮、冰 → raw_cold；寒凉、寒性 → cold_nature；酒、饮酒、酒精、白酒、啤酒、红酒 → alcohol；烟、吸烟 → non_food；肥肉 → fatty_meat；动物内脏、内脏 → organ_meat；含糖饮料、甜饮料 → sugary_drink；甜食、甜点、甜品、糖 → sweets 与 high_sugar；海鲜 → seafood；咖啡、浓茶 → caffeine；嘌呤、高嘌呤 → high_purine；腌制、咸菜、咸 → high_sodium；低盐 → violates high_sodium；低脂 → violates high_fat、fried、fatty_meat；低糖 → violates high_sugar、sweets、sugary_drink；低嘌呤 → violates high_purine、alcohol；糖尿病饮食 → violates high_sugar、sweets、sugary_drink、fast_carb；清淡 → violates spicy、fried、high_fat；高蛋白、优质蛋白 → prefers high_protein；高纤维 → prefers high_fiber；流质、半流质、软食 → unverifiable；少量多餐、多饮水、多喝水 → not_applicable；素食、吃素 → violates meat、seafood。

软规则 `soft_rules.json`：
```json
{
  "cycle": {
    "menstrual": [
      {"tags": ["raw_cold", "cold_nature"], "effect": "caution", "tradition": true, "tip_id": "menstrual-warm",
       "message": "经期可以优先选择温热的饮食，少吃生冷寒凉的食物"},
      {"tags": ["alcohol", "caffeine"], "effect": "caution", "tradition": false, "tip_id": "menstrual-caffeine-alcohol",
       "message": "痛经明显时可以暂时减少咖啡、浓茶和酒精"},
      {"tags": ["high_sodium"], "effect": "caution", "tradition": false, "tip_id": "menstrual-salt-water",
       "message": "经期少吃过咸的食物，可能有助于减轻水肿"},
      {"tags": ["iron_rich"], "effect": "prefer", "tradition": false, "tip_id": "menstrual-iron",
       "message": "经期可以适当多吃富含铁的食物"}
    ],
    "luteal": [
      {"tags": ["high_sodium", "sweets", "sugary_drink"], "effect": "caution", "tradition": false,
       "tip_id": "luteal-slow-carbs", "message": "经前可以少吃高盐和高糖的零食"},
      {"tags": ["slow_carb"], "effect": "prefer", "tradition": false, "tip_id": "luteal-slow-carbs",
       "message": "经前主食多选全谷物等慢碳"},
      {"tags": ["calcium_rich"], "effect": "prefer", "tradition": false, "tip_id": "luteal-calcium",
       "message": "经前保证富含钙的食物"}
    ]
  },
  "goals": {
    "lose_fat": [
      {"tags": ["fried", "high_fat", "fatty_meat"], "effect": "caution", "message": "减脂期间少吃油炸和高脂肪的食物"},
      {"tags": ["sweets", "sugary_drink", "high_sugar"], "effect": "caution", "message": "减脂期间少吃甜食和含糖饮料"},
      {"tags": ["high_protein", "high_fiber"], "effect": "prefer", "message": "高蛋白、高纤维的食物饱腹感更强，适合减脂"}
    ],
    "gain_muscle": [
      {"tags": ["high_protein"], "effect": "prefer", "message": "增肌期间保证蛋白质摄入"}
    ]
  }
}
```
加载时校验：tip_id 必须存在于 `app.cycle.tips.load_tip_rules()` 中；阶段名必须是经期引擎的四个阶段之一；目标名必须是档案的目标取值之一；标签必须已定义。

判断规则（engine.py 一处实现）：
1. **医嘱（硬约束）**，逐条医嘱、逐个涉及对象：
   - 饮食禁忌与用药相关饮食注意：词汇表为 non_food → 跳过；食物带有词汇表对应的标签，或食物名称与别名和这个说法互相包含 → `block`（不建议），依据写明医嘱原文与命中方式，待复核时加"这条医嘱正在待复核，确认解除之前仍按原要求执行。"；都不命中时，如果词汇表里有这个说法或营养库里有食物名对得上 → 不影响；否则 → `unverifiable`（无法判断）。
   - 饮食要求：词汇表 violates 命中 → `block`；prefers 命中 → `prefer`；unverifiable 或词汇表里没有 → `unverifiable`；not_applicable → 跳过。
   - 运动限制与其他类医嘱不参与食物判断。
2. **经期阶段**（软约束）：按当前阶段的规则，食物带任一规则标签 → 对应 `caution` 或 `prefer`，消息开头写"经期提示（<阶段中文名>，传统经验或营养学建议，不是医嘱）："，ref 为提示规则编号。阶段未知或没有经期信息时不产生依据。
3. **健身目标**（软约束）：按档案目标的规则同理，消息开头写"健身目标（<目标中文名>）："。
4. **当日摄入**（软约束）：需求可估算时，"今日已摄入 + 本份"能量超过需求上限 → `caution`；钠超过上限 → `caution`；需求不可估算时给一条 `info`："档案信息不完整，无法估算今天的剩余额度"。
5. **个人偏好**（软约束）：档案"忌口"中的说法按避免类匹配，命中 → `caution`（"你在档案里填写了不吃「x」"），无法判断时忽略；档案"饮食偏好"按要求类匹配，violates 命中 → `caution`，prefers 命中 → `prefer`。
6. **结论**：有 `block` → 不建议；否则有 `unverifiable` 或 `caution` → 谨慎；否则适合。
7. **排序与去重**：依据去重后按（来源顺序 medical、cycle、goal、intake、preference，效果顺序 block、unverifiable、caution、prefer、info，code，ref，message）排序。
8. **权衡说明**：有 `block` 且有 `prefer` → "虽然有<来源>方面的好处，但医嘱优先，结论为不建议。"；否则同时有软约束的 `caution` 与 `prefer` → "这个食物同时有有利和需要注意的提示：有利的来自<来源>，需要注意的来自<来源>，请结合自己的情况权衡。"；否则为空。来源名按 SOURCE_ORDER 去重排序后用顿号连接。
9. 每个结果都带 `data_source`（食物出处与授权状态的简短说明）与 `DISCLAIMER`："以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。"
10. **一餐**：按顺序逐个判断，后面的食物在当日摄入里计入前面食物的份量；整餐结论取最严重的那个；返回整餐营养合计。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_engine.py`
```python
import random

import pytest

from app.nutrition.catalog import Catalog, Food, Nutrients, Source, TagDefinition
from app.nutrition.engine import (
    CAUTION,
    DISCLAIMER,
    NOT_RECOMMENDED,
    SUITABLE,
    EvaluationContext,
    HardConstraint,
    evaluate_food,
    evaluate_meal,
)
from app.nutrition.needs import Needs

SOURCE = Source("测试数据", "t", "personal_study_only", "测试")
TAGS = [
    TagDefinition(tag, name, kind, "传统饮食经验" if kind == "tradition" else "测试", "reviewed")
    for tag, name, kind in [
        ("spicy", "辛辣", "culinary"), ("high_fat", "高脂肪", "nutrition"), ("meat", "含肉", "composition"),
        ("cold_nature", "寒凉", "tradition"), ("raw_cold", "生冷", "culinary"), ("alcohol", "含酒精", "composition"),
        ("high_protein", "高蛋白", "nutrition"), ("organ_meat", "动物内脏", "composition"),
        ("iron_rich", "富含铁", "nutrition"), ("high_sodium", "高钠", "nutrition"), ("sweets", "甜食", "dietary"),
        ("high_sugar", "高糖", "dietary"), ("fast_carb", "快碳", "dietary"), ("fried", "油炸", "culinary"),
        ("slow_carb", "慢碳", "dietary"), ("high_fiber", "高膳食纤维", "nutrition"),
    ]
]


def _food(food_id, name, tags, energy=100.0, sodium=10.0, aliases=()):
    return Food(
        id=food_id, name=name, aliases=aliases, category="测试", kind="ingredient",
        nutrients=Nutrients(energy_kcal=energy, protein_g=5, fat_g=5, carbohydrate_g=10, sodium_mg=sodium),
        tags=frozenset(tags), source=SOURCE,
    )


HOTPOT = _food("t:hotpot", "火锅", {"spicy", "high_fat", "meat"}, energy=150)
WATERMELON = _food("t:melon", "西瓜", {"cold_nature"}, energy=30)
BEER = _food("t:beer", "啤酒", {"alcohol"}, energy=40)
BREAST = _food("t:breast", "鸡胸肉", {"high_protein", "meat"}, energy=130)
LIVER = _food("t:liver", "猪肝", {"organ_meat", "iron_rich", "high_protein", "meat"}, energy=130)
SPINACH = _food("t:spinach", "菠菜", set(), energy=25)
CAKE = _food("t:cake", "蛋糕", {"sweets", "high_sugar"}, energy=350)
BEEF_JERKY = _food("t:jerky", "卤牛肉", {"high_protein", "high_sodium", "meat"}, energy=200, sodium=900)
RICE = _food("t:rice", "米饭", {"fast_carb"}, energy=116)
CATALOG = Catalog([HOTPOT, WATERMELON, BEER, BREAST, LIVER, SPINACH, CAKE, BEEF_JERKY, RICE], TAGS, {})
NEEDS = Needs(status="ok", energy_kcal=1500, energy_kcal_low=1350, energy_kcal_high=1650, protein_g=60,
              sodium_mg_max=2000)
ZERO = Nutrients(energy_kcal=0, sodium_mg=0)


def _avoid(item_id, content, subjects, needs_review=False, category="diet_avoid"):
    return HardConstraint(item_id, category, content, tuple(subjects), needs_review)


def _ctx(**kwargs):
    base = {"needs": NEEDS, "day_totals": ZERO}
    base.update(kwargs)
    return EvaluationContext(**base)


def _evaluate(food, grams=100, **kwargs):
    return evaluate_food(food, grams, _ctx(**kwargs), CATALOG)


def _sources(result):
    return [(r.source, r.effect) for r in result.reasons]


def test_healthy_user_gets_suitable_with_disclaimer():
    result = _evaluate(SPINACH)
    assert result.conclusion == SUITABLE
    assert result.reasons == ()
    assert result.disclaimer == DISCLAIMER
    assert "测试数据" in result.data_source


def test_medical_avoid_blocks_and_names_the_order():
    result = _evaluate(HOTPOT, constraints=(_avoid("m1", "一周内忌食辛辣、油腻", ["辛辣", "油腻"]),))
    assert result.conclusion == NOT_RECOMMENDED
    blocks = [r for r in result.reasons if r.effect == "block"]
    assert {r.ref for r in blocks} == {"m1"}
    assert any("一周内忌食辛辣、油腻" in r.message and "辛辣" in r.message for r in blocks)


def test_name_match_blocks_too():
    result = _evaluate(WATERMELON, constraints=(_avoid("m1", "忌西瓜", ["西瓜"]),))
    assert result.conclusion == NOT_RECOMMENDED


def test_pending_review_order_still_blocks():
    result = _evaluate(BEER, constraints=(_avoid("m2", "禁酒", ["酒"], needs_review=True),))
    assert result.conclusion == NOT_RECOMMENDED
    assert any("待复核" in r.message for r in result.reasons)


def test_non_food_subject_is_ignored_and_known_food_subject_is_verifiable():
    result = _evaluate(RICE, constraints=(_avoid("m3", "戒烟，忌菠菜", ["烟", "菠菜"]),))
    assert result.conclusion == SUITABLE
    assert result.reasons == ()


def test_unrecognised_subject_caps_at_caution():
    result = _evaluate(RICE, constraints=(_avoid("m4", "忌发物", ["发物"]),))
    assert result.conclusion == CAUTION
    assert _sources(result) == [("medical", "unverifiable")]
    assert "发物" in result.reasons[0].message and "核对" in result.reasons[0].message


def test_requirement_styles():
    low_salt = _avoid("m5", "低盐饮食", ["低盐"], category="diet_require")
    assert _evaluate(BEEF_JERKY, constraints=(low_salt,)).conclusion == NOT_RECOMMENDED
    assert _evaluate(SPINACH, constraints=(low_salt,)).conclusion == SUITABLE
    protein = _avoid("m6", "优质蛋白饮食", ["优质蛋白"], category="diet_require")
    result = _evaluate(BREAST, constraints=(protein,))
    assert (result.conclusion, _sources(result)) == (SUITABLE, [("medical", "prefer")])
    liquid = _avoid("m7", "流质饮食", ["流质"], category="diet_require")
    assert _evaluate(SPINACH, constraints=(liquid,)).conclusion == CAUTION
    meals = _avoid("m8", "少量多餐", ["少量多餐"], category="diet_require")
    assert _evaluate(SPINACH, constraints=(meals,)).conclusion == SUITABLE


def test_exercise_and_other_orders_do_not_affect_food():
    orders = (_avoid("m9", "避免剧烈运动", ["剧烈运动"], category="exercise_limit"),
              _avoid("m10", "每天测血压", [], category="other"))
    assert _evaluate(HOTPOT, constraints=orders).conclusion == SUITABLE


def test_menstrual_cold_food_is_caution_from_cycle_not_medical():
    result = _evaluate(WATERMELON, cycle_phase="menstrual")
    assert result.conclusion == CAUTION
    [reason] = result.reasons
    assert (reason.source, reason.effect, reason.ref) == ("cycle", "caution", "menstrual-warm")
    assert "不是医嘱" in reason.message and "传统经验" in reason.message


def test_menstrual_iron_is_preferred():
    result = _evaluate(LIVER, cycle_phase="menstrual")
    assert result.conclusion == SUITABLE
    assert ("cycle", "prefer") in _sources(result)


def test_hard_constraint_beats_soft_preference():
    result = _evaluate(LIVER, cycle_phase="menstrual", goal="gain_muscle",
                       constraints=(_avoid("m11", "忌动物内脏", ["动物内脏"]),))
    assert result.conclusion == NOT_RECOMMENDED
    assert "医嘱优先" in result.tradeoff


def test_soft_conflict_gets_a_tradeoff_note():
    result = _evaluate(BEEF_JERKY, cycle_phase="luteal", goal="lose_fat")
    assert result.conclusion == CAUTION
    assert ("cycle", "caution") in _sources(result) and ("goal", "prefer") in _sources(result)
    assert "权衡" in result.tradeoff


def test_intake_over_energy_upper_bound():
    result = _evaluate(CAKE, grams=100, day_totals=Nutrients(energy_kcal=1400, sodium_mg=0))
    assert result.conclusion == CAUTION
    assert any(r.source == "intake" and "1650" in r.message for r in result.reasons)


def test_unknown_needs_gives_info_only():
    result = _evaluate(SPINACH, needs=Needs(status="insufficient_profile", missing_fields=("weight_kg",)))
    assert result.conclusion == SUITABLE
    assert _sources(result) == [("intake", "info")]


def test_personal_avoidance_and_preference():
    result = _evaluate(HOTPOT, food_avoidances=("辣",))
    assert (result.conclusion, _sources(result)) == (CAUTION, [("preference", "caution")])
    assert _evaluate(BREAST, diet_preferences=("素食",)).conclusion == CAUTION


def test_output_is_deterministic_regardless_of_input_order():
    orders = [
        _avoid("m1", "忌辛辣", ["辛辣"]), _avoid("m2", "忌油腻", ["油腻"]), _avoid("m3", "忌发物", ["发物"]),
    ]
    first = _evaluate(HOTPOT, constraints=tuple(orders), cycle_phase="menstrual", goal="lose_fat")
    for seed in range(5):
        shuffled = orders[:]
        random.Random(seed).shuffle(shuffled)
        again = _evaluate(HOTPOT, constraints=tuple(shuffled), cycle_phase="menstrual", goal="lose_fat")
        assert again == first


def test_meal_takes_the_worst_conclusion_and_running_totals():
    context = _ctx(day_totals=Nutrients(energy_kcal=1300, sodium_mg=0),
                   constraints=(_avoid("m1", "禁酒", ["酒"]),))
    result = evaluate_meal([(RICE, 200), (CAKE, 100), (BEER, 300)], context, CATALOG)
    assert [i.conclusion for i in result.items] == [SUITABLE, CAUTION, NOT_RECOMMENDED]
    assert result.conclusion == NOT_RECOMMENDED
    assert result.total.energy_kcal == pytest.approx(232 + 350 + 120)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_nutrition_engine.py -q`
Expected: FAIL（`No module named 'app.nutrition.engine'`）

- [ ] **Step 3: 实现 rules 与 engine**

按"判断规则"十条实现 `rules.py` 与 `engine.py`（纯函数，不导入数据库或时间相关模块）。要点：
- 名称互相包含的判断：说法在食物名称或任一别名中，或食物名称、别名（长度不少于 2）在说法中；
- "说法是否可判断"：词汇表有这个说法，或 `catalog.name_matches(说法)` 为真；
- 阶段中文名：menstrual 月经期、follicular 卵泡期、ovulation 排卵期、luteal 黄体期；目标中文名：lose_fat 减脂、gain_muscle 增肌、maintain 维持；
- `Evaluation.nutrients` 为 `food.nutrients.scaled(grams)`；`grams` 为传入值；
- `data_source` 写成"<数据集>（<授权状态中文>）：<出处编号>"，授权状态中文：personal_study_only 为"仅供个人学习"，self_estimate_unverified 为"手动估算，未核对"；
- 所有结果都是 frozen 数据类，元组而非列表，便于比较与保证确定性。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_nutrition_engine.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。

- [ ] **Step 5: 提交**

```
git add backend/app/nutrition backend/tests/test_nutrition_engine.py
git commit -m "feat(nutrition): add deterministic constraint fusion engine with vocabulary and soft rules"
```

---

### Task 5: 组装上下文与判断接口

**Files:**
- Create: `backend/app/nutrition/context.py`
- Modify: `backend/app/nutrition/schemas.py`, `backend/app/nutrition/router.py`
- Test: `backend/tests/test_nutrition_evaluate.py`

**Interfaces:**
- Consumes: 引擎；`app.medical.items.get_current_constraints`；`app.cycle.insights.get_phase_info`；`get_or_create_profile`、`compute_capabilities`；`needs_for_profile`；`meals.day_totals`
- Produces:
  - `app.nutrition.context.build_context(db, user_id, today) -> EvaluationContext`
  - 接口：POST `/api/nutrition/evaluate`（body：food_id，grams 或 portion，二者都不给时用食物的默认份量）→ EvaluationOut；POST `/api/nutrition/evaluate-meal`（body：items 列表，1 至 20 项）→ MealEvaluationOut。两者都只针对今天。

上下文规则：
- 医嘱：`compute_capabilities` 开放 medical 时调用 `get_current_constraints(db, user_id, today)`，转换为 `HardConstraint`（item_id 转字符串，subjects 转元组）。
- 经期：开放 cycle 时调用 `get_phase_info(db, user_id, today, today)`，阶段不是 unknown 才填入 `cycle_phase`。
- 目标、忌口、饮食偏好来自档案；需求用 `needs_for_profile`；当日摄入用 `meals.day_totals(db, user_id, today)`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_evaluate.py`（四类验证用户，全部经由真实接口建立数据）：
```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from tests.helpers import ready_user

TODAY = date(2026, 10, 6)


@pytest.fixture
def medical_today():
    state = {"today": TODAY}
    app = create_app()
    app.dependency_overrides[get_today] = lambda: state["today"]
    with TestClient(app) as client:
        yield client, state


def _id(client, headers, name):
    return client.get("/api/nutrition/foods/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _evaluate(client, headers, name, **amount):
    body = {"food_id": _id(client, headers, name), **amount}
    response = client.post("/api/nutrition/evaluate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _confirmed_order(client, headers, text):
    order = client.post("/api/medical/orders", json={"text": text}, headers=headers).json()
    for item in order["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    return order["items"]


def test_user_with_medical_avoidance(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "alice")
    [item] = _confirmed_order(client, headers, "一周内忌食辛辣、油腻食物，禁酒。")
    for name in ("麻婆豆腐", "啤酒", "炸鸡"):
        result = _evaluate(client, headers, name)
        assert result["conclusion"] == "not_recommended", name
        assert any(r["source"] == "medical" and r["ref"] == item["id"] for r in result["reasons"]), name
    assert _evaluate(client, headers, "清炒西兰花")["conclusion"] == "suitable"


def test_pending_review_still_blocks_and_resolution_releases(medical_today):
    client, state = medical_today
    headers = ready_user(client, "alice")
    [item] = _confirmed_order(client, headers, "三天内禁酒。")
    state["today"] = date(2026, 10, 8)
    result = _evaluate(client, headers, "啤酒")
    assert result["conclusion"] == "not_recommended"
    assert any("待复核" in r["message"] for r in result["reasons"])
    client.post(f"/api/medical/items/{item['id']}/resolve", headers=headers)
    assert _evaluate(client, headers, "啤酒")["conclusion"] != "not_recommended"


def test_menstrual_user_gets_cycle_caution_for_cold_food(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "bella", {"gender": "female"})
    for start, end in [("2026-07-13", "2026-07-17"), ("2026-08-10", "2026-08-14"), ("2026-09-07", "2026-09-11"),
                       ("2026-10-05", None)]:
        assert client.post("/api/cycle/periods", json={"start_date": start, "end_date": end},
                           headers=headers).status_code == 201
    result = _evaluate(client, headers, "西瓜")
    assert result["conclusion"] == "caution"
    cycle = [r for r in result["reasons"] if r["source"] == "cycle"]
    assert cycle and all("不是医嘱" in r["message"] for r in cycle)
    assert not any(r["source"] == "medical" for r in result["reasons"])


def test_gain_muscle_user_prefers_protein(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "carl", {"gender": "male", "goal": "gain_muscle", "birth_year": 1990,
                                          "height_cm": 175, "weight_kg": 70, "activity_level": "moderate"})
    result = _evaluate(client, headers, "鸡胸肉", grams=150)
    assert result["conclusion"] == "suitable"
    assert any(r["source"] == "goal" and r["effect"] == "prefer" for r in result["reasons"])


def test_healthy_user_and_determinism(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "dora", {"birth_year": 1995, "height_cm": 165, "weight_kg": 55,
                                          "activity_level": "light"})
    first = _evaluate(client, headers, "番茄炒蛋")
    assert first["conclusion"] == "suitable"
    assert "不构成医疗建议" in first["disclaimer"]
    for _ in range(3):
        assert _evaluate(client, headers, "番茄炒蛋") == first


def test_hard_beats_soft_end_to_end(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "erin", {"gender": "male", "goal": "gain_muscle"})
    _confirmed_order(client, headers, "一个月内忌动物内脏。")
    result = _evaluate(client, headers, "猪肝")
    assert result["conclusion"] == "not_recommended"
    assert "医嘱优先" in (result["tradeoff"] or "")


def test_meal_evaluation_and_validation(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "fay")
    _confirmed_order(client, headers, "禁酒。")
    items = [{"food_id": _id(client, headers, n), "grams": 200} for n in ("米饭", "番茄炒蛋", "啤酒")]
    body = client.post("/api/nutrition/evaluate-meal", json={"items": items}, headers=headers).json()
    assert [i["conclusion"] for i in body["items"]][-1] == "not_recommended"
    assert body["conclusion"] == "not_recommended"
    assert body["total"]["energy_kcal"] > 0
    assert client.post("/api/nutrition/evaluate-meal", json={"items": []}, headers=headers).status_code == 422
    bad = client.post("/api/nutrition/evaluate", json={"food_id": "cfcd:nope"}, headers=headers)
    assert bad.json()["error"]["code"] == "food_not_found"
    assert client.post("/api/nutrition/evaluate", json={"food_id": items[0]["food_id"], "date": "2026-10-07"},
                       headers=headers).status_code == 422


def test_unrecognised_order_caps_at_caution(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "gina")
    order = client.post("/api/medical/orders", json={"text": "忌食发物。"}, headers=headers).json()
    client.post(f"/api/medical/items/{order['items'][0]['id']}/confirm", headers=headers)
    result = _evaluate(client, headers, "清炒西兰花")
    assert result["conclusion"] == "caution"
    assert any(r["effect"] == "unverifiable" and "发物" in r["message"] for r in result["reasons"])
```

（经期用户：最近一次开始日为 10 月 5 日、尚未结束，今天 10 月 6 日为经期第 2 天，属于月经期。）

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_nutrition_evaluate.py -q`
Expected: FAIL（接口不存在）

- [ ] **Step 3: 实现 context 与接口**

`context.py` 按上下文规则实现；`schemas.py` 追加 `EvaluateIn(food_id, grams: float | None, portion: PortionIn | None)`（extra forbid，grams 与 portion 最多给一个）、`MealItemIn`（同字段）、`EvaluateMealIn(items: list[MealItemIn]，1 至 20 项)`、`ReasonOut`、`EvaluationOut(food_id, food_name, grams, nutrients: NutrientsOut, conclusion, reasons, tradeoff, data_source, disclaimer)`、`MealEvaluationOut(items, conclusion, total, disclaimer)`；`router.py` 追加两个 POST 接口：解析食物（不存在时 `food_not_found`）与克数（未给时用 `food.default_grams`，给了用 `meals.resolve_grams` 的同样校验），`build_context(db, user.id, today)` 后调用引擎。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_nutrition_evaluate.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。

- [ ] **Step 5: 提交**

```
git add backend/app/nutrition backend/tests/test_nutrition_evaluate.py
git commit -m "feat(nutrition): wire constraint engine to medical, cycle and profile context"
```

---

### Task 6: 演示数据、交付文档与验收记录

**Files:**
- Create: `backend/app/nutrition/demo.py`
- Test: `backend/tests/test_nutrition_demo.py`, `backend/tests/test_nutrition_docs.py`
- Create: `docs/04-交付物/营养库数据与授权清单.md`、`食物标签定义与审核表.md`、`约束融合规则说明.md`、`接口清单.md`、`验证场景与预期结果.md`、`验收记录.md`（均不得出现代码、命令、反引号与代码块）
- Modify: `README.md`（新增"饮食与约束引擎演示"小节；同步开头完成情况与表数量），`docs/00-总览与串联.md`（步骤 04 改为"待验收"）

**Interfaces:**
- Produces: `app.nutrition.demo.DEMO_USERS`（四个演示账号：有忌口医嘱、经期、增肌、健康无约束）、`seed(db, today) -> list[str]`、`main()`（`uv run python -m app.nutrition.demo`）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_nutrition_demo.py`：调用 `seed(db, date(2026, 10, 6))` 两次，第一次返回四个用户名、第二次返回空列表；对四个用户分别用 `build_context` 与引擎判断一个代表食物（有忌口医嘱用户判断麻婆豆腐为不建议；经期用户判断西瓜为谨慎且依据来自经期；增肌用户判断鸡胸肉有健身目标的正面依据；健康用户判断番茄炒蛋为适合）。

`backend/tests/test_nutrition_docs.py`：
- `食物标签定义与审核表.md` 必须包含 tags.json 中每个标签编号；
- `docs/04-交付物/` 下所有文档不含反引号；
- `验证场景与预期结果.md` 必须包含"有忌口医嘱""经期""增肌""健康无约束"四个词。

- [ ] **Step 2: 运行确认失败**，然后实现 `demo.py`：四个账号的密码均为 `demo-pass-123`，确认免责声明并按需写入档案；忌口用户录入并确认"一周内忌食辛辣、油腻食物，禁酒。"；经期用户按今天倒推录入四次月经（最后一次从昨天开始、尚未结束）；增肌用户填写完整档案与增肌目标；健康用户填写完整档案。

- [ ] **Step 3: 写交付文档**（先阅读实际代码与数据文件，文档必须描述实际行为）：
1. `营养库数据与授权清单.md`：三类数据（成分表整理数据、自建菜品配方、手动补充）的来源、固定版本与哈希、条目数量、数值处理规则（微量、未测定、星号）、授权状态与商用前必须处理的事项；如实说明成分表整理数据由视觉大模型识别、作者不保证完全一致；列出全部手动补充食物及其估算依据。
2. `食物标签定义与审核表.md`：逐个标签列出编号、中文名、类别（营养学、成分、烹调、饮食、传统经验）、判定方式（数值门槛或成员规则）、依据、审核状态，另加一列"用户审核意见"留空；传统经验类单独成节并写明不是医学结论。
3. `约束融合规则说明.md`：分层、优先级、医嘱与食物的对应方式（词汇表、名称匹配、无法判断的处理）、经期与目标规则、当日摄入、个人偏好、结论规则、排序与确定性、权衡说明，并附"输入与预期输出"场景表（至少 12 个场景，与测试一致）。
4. `接口清单.md`：全部 `/api/nutrition/*` 接口与错误码；说明判断只针对今天的原因。
5. `验证场景与预期结果.md`：四类验证用户（有忌口医嘱、经期、增肌、健康无约束）各自的档案、医嘱或经期数据、代表食物与预期结论及依据。
6. `验收记录.md`：`docs/04-营养与饮食约束引擎.md` 的 8 条验收标准逐条列出自动化测试与手动核对方法，"用户验收"列留空。

- [ ] **Step 4: README 与总览**：README 新增演示小节（创建四个演示账号、在接口文档页面体验检索、记录三餐看汇总、对同一食物比较四个账号的判断结果）；同步开头的完成情况（步骤 04 待验收）与第 5 节表数量（新增 1 张，共 12 张）。总览中步骤 04 改为"待验收"。

- [ ] **Step 5: 运行确认通过**：`uv run pytest -q -W error` 全部通过；开发库 `uv run alembic upgrade head` 后运行 `uv run python -m app.nutrition.demo` 两次。

- [ ] **Step 6: 提交**

```
git add backend/app/nutrition/demo.py backend/tests docs README.md
git commit -m "docs(nutrition): add demo data, step 04 delivery docs and acceptance record"
```
