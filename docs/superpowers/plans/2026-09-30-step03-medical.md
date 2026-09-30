# 步骤 03 医嘱模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把用户录入的医嘱文字提取成结构化、带时效的候选条目，经用户逐条确认后成为硬约束；到期或到复查日自动进入待复核；提出解除建议不改变约束，只有用户确认才解除；全程留审计记录；医嘱原文、条目内容与图片证据加密且只对本人可见。满足 `docs/03-医嘱模块.md` 的 8 条验收标准。

**Architecture:** 新增 `app/medical` 包。`extraction.py` 定义提取器接口与本步骤的规则提取器（纯函数，不访问数据库；步骤 07 接入大模型后只需替换 `get_extractor()`）；`samples.py` 放三份演示与评测样例；`models.py` 四张表；`items.py` 负责条目的状态流转、审计、到期检查与约束查询（步骤 04 读取的入口）；`orders.py` 负责医嘱原文、提取入库、手动补充条目与证据文件；`deps.py` 的 `require_medical_user` 在免责声明闸门之上检查能力清单并在每次请求前刷新到期状态；`router.py` 提供 18 个接口。

**Tech Stack:** 沿用步骤 01、02：Python 3.12、FastAPI、SQLAlchemy 2、PostgreSQL 16、Alembic、pytest、httpx2；新增 `python-multipart`（Apache-2.0，FastAPI 接收上传文件所需）。

**Spec:** `docs/03-医嘱模块.md`（总览见 `docs/00-总览与串联.md`，底座约定见 `docs/01-交付物/`）

## Global Constraints

- 运行平台是 Windows 11，终端是 PowerShell 5.1（不支持 `&&`）；也可以用 Bash 工具。
- 所有后端命令都在 `E:\workspace\good-life\backend` 目录下执行，统一用 `uv run ...`；完整测试用 `uv run pytest -q -W error`，必须零失败、零警告。
- 数据库地址用 `127.0.0.1:5433`（不要用 localhost），测试库 `goodlife_test`。
- 统一错误格式：`{"error": {"code": "<机器可读码>", "message": "<中文提示>"}}`，业务错误一律抛 `app.errors.AppError(status_code, code, message)`。
- 每张业务表都必须有 `user_id` 列；查询统一从 `app.common.ownership.owned_by` 开始；按编号取单条记录统一用 `get_owned_or_404`（他人的记录与不存在的记录一样返回 404 `not_found`）。
- 任何接口都不接受客户端传入的 user_id；请求模型一律 `extra="forbid"`。
- 所有 `/api/medical/*` 接口依赖 `require_medical_user`（内部依赖 `require_disclaimer_user`）。是否开放医嘱模块只由 `app.profile.capabilities.compute_capabilities` 判断。
- "今天"一律通过依赖 `app.common.clock.get_today` 取得；服务层需要日期的函数显式接收 `today`，不得在服务层调用 `date.today()`。
- 医嘱原文、条目内容、涉及对象、原文片段、解除理由、审计详情、证据文件名与文件内容必须加密存储（`EncryptedJSON` 或本步骤新增的 `EncryptedBytes`）；类别、状态、把握程度、来源、各类日期明文存储（需要按它们查询与判断到期）。
- 医嘱只能由用户确认生效、只能由用户确认解除；系统与后续智能体只能"提出解除建议"。本步骤不判断药物剂量与药物相互作用。
- 不做：大模型提取、图片文字识别、自动解除、对话中推断病情好转、界面页面、账号注销时的数据删除（步骤 12）。
- 模型与迁移必须一致（`tests/test_migrations.py` 会检查）；新迁移接在 `0006_cycle_status_encrypt` 之后，revision 编号不超过 32 个字符。
- 提交信息以如下一行结尾：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（不要替换成你自己的模型名）；不得提交 `backend/.env` 与 `.superpowers/`。
- 交付文档（`docs/03-交付物/` 下）不得出现代码、命令或代码块。

## 关键决策（本计划据此编写）

| 决策 | 内容 | 理由 |
|---|---|---|
| 提取方式 | 本步骤用规则提取器（关键词加日期规则），提取器做成可替换接口，步骤 07 换成大模型 | 用户选定；接大模型的步骤 07 尚未完成 |
| 图片与文档 | 只加密保存为证据、可下载核对，不识别文字；用户对照图片录入文字 | 用户选定；识别图片文字需要视觉模型 |
| 状态 | 待确认 pending_confirmation、生效中 active、待复核 pending_review、已解除 resolved、已作废 voided | 规格列出的五种状态 |
| 硬约束 | 生效中与待复核的条目，且生效日期不晚于今天 | 规格：待复核期间保守对待 |
| 进入待复核 | 复查日当天起；或预计结束日前 1 天起（`REVIEW_LEAD_DAYS = 1`） | 规格：到期前与复查日到来时 |
| 自动作废 | 未确认的条目过了预计结束日自动作废 | "已过期作废"状态的来源 |
| 刷新时机 | 每个医嘱接口请求前由依赖刷新一次；约束查询与待复核查询函数自己也会刷新 | 不引入定时任务，步骤 04 直接调用也能拿到最新状态 |
| 解除 | 提出建议不改状态；用户可不经建议直接确认解除；待复核时可"继续执行"并设新日期 | 规格：只有用户确认后才解除 |
| 证据文件 | 按文件头识别类型，只收 JPG、PNG、WEBP、PDF，单个不超过 10 MB；下载文件名不使用用户原文件名 | 防伪造类型、防响应头注入 |

## 文件结构

```
backend/
├── app/
│   ├── security/crypto.py         # 追加 EncryptedBytes（任务 2）
│   ├── medical/
│   │   ├── __init__.py
│   │   ├── extraction.py          # 提取器接口与规则提取器（任务 1）
│   │   ├── samples.py             # 三份样例（任务 1）
│   │   ├── models.py              # 四张表（任务 2）
│   │   ├── items.py               # 状态流转、审计、到期、约束查询（任务 2 建核心，任务 3 补全）
│   │   ├── orders.py              # 原文、提取入库、手动条目（任务 2）、证据文件（任务 4）
│   │   ├── schemas.py             # 任务 4
│   │   ├── deps.py                # require_medical_user（任务 4）
│   │   ├── router.py              # 任务 4
│   │   └── demo.py                # 任务 5
│   ├── main.py、models.py          # 挂路由、导入模型
├── migrations/versions/0007_medical.py   # 任务 2
└── tests/
    ├── test_medical_extraction.py # 任务 1
    ├── test_medical_orders.py     # 任务 2
    ├── test_medical_items.py      # 任务 3
    ├── test_medical_api.py        # 任务 4
    ├── test_route_guards.py       # 追加医嘱接口准入检查（任务 4）
    ├── test_medical_demo.py、test_medical_docs.py   # 任务 5
docs/03-交付物/                     # 任务 5，全部不含代码与命令
```

---

### Task 1: 提取器接口、规则提取器与样例

**Files:**
- Create: `backend/app/medical/__init__.py`, `backend/app/medical/extraction.py`, `backend/app/medical/samples.py`
- Test: `backend/tests/test_medical_extraction.py`

**Interfaces:**
- Produces（`app.medical.extraction`）:
  - 常量 `CATEGORY_ORDER`、`AVOID_TRIGGERS`、`REQUIRE_STYLES`、`EXERCISE_WORDS`、`MEDICATION_WORDS`、`MEDICATION_DIET_HINTS`、`REVIEW_WORDS`、`CONDITIONAL_WORDS`、`LONG_TERM_WORDS`、`HEDGE_WORDS`；原因常量 `REASON_NO_REQUIREMENT`、`REASON_MEDICATION`、`REASON_CONDITIONAL`、`REASON_REVIEW_WITHOUT_DATE`；提示常量 `NOTE_NO_DURATION`、`NOTE_HEDGE`、`NOTE_MEDICATION`、`NOTE_LONG_SUBJECT`
  - 数据类 `ExtractedItem(category, content, subjects, start_date, end_date, review_date, confidence, source_excerpt, missing_fields=[], notes=[])`、`IgnoredSentence(text, reason)`、`ExtractionResult(extractor, items, ignored, notes)`（均 frozen）
  - 协议 `Extractor`（属性 `name: str`，方法 `extract(text: str, order_date: date) -> ExtractionResult`）
  - `RuleBasedExtractor`（`name = "rule-based-v1"`）、`get_extractor() -> Extractor`
  - 工具函数 `parse_number(text) -> int | None`、`add_months(day, months) -> date`、`add_duration(start, amount, unit) -> date`、`split_sentences(text) -> list[str]`
- Produces（`app.medical.samples`）：`SAMPLE_ORDERS: dict[str, str]`（键 `short_term`、`chronic`、`post_surgery`）、`SAMPLE_TITLES: dict[str, str]`

规则提取器的行为（测试按此断言，开具日期均为 2026-09-30）：
1. 按句号、分号、感叹号、问号、换行，以及"1." "2、" "（3）"这类编号切句；去掉句首不超过 6 个字的"诊断：""医嘱："一类标签；空句丢弃。
2. 含复查、复诊、随访的句子只用来取复查日期：写明日期的用日期，写了"X 周后"之类的用开具日期加上时长；多个时间取最早的并在结果说明里提示核对；没有时间时，带"如、若、必要时"等条件词的记为条件性提醒，否则记为"提到复查但没有写时间"，都不生成条目。
3. 含用药词的句子：去掉用药词后如果还有酒、饮食、吃、喝等饮食线索，生成"用药相关饮食注意"条目（把握程度一律为低）；否则整句忽略，原因是用药信息不在本系统判断范围。
4. 其余句子：禁、忌、避免、戒、限、少吃等触发词后面到下一个触发词或逗号之间的内容，按顿号、和、及、与、或拆成涉及对象；含运动类词语的对象归入"运动限制"，其余归入"饮食禁忌"；低盐、低脂、清淡、流质等饮食方式词归入"饮食要求"。同一句可同时生成多类条目，顺序为：用药相关饮食注意、饮食禁忌、饮食要求、运动限制。
5. 时长：句中第一个"数字加天、周、个月、年"作为持续时间，预计结束日期 = 开具日期加时长再减 1 天；含"长期、终身、永久、坚持"视为长期，没有结束日期；都没有时，结束日期留空并记入缺失字段。
6. 把握程度：用药相关、没有涉及对象、含"适量、酌情、必要时、视情况、尽量"、或涉及对象超过 12 个字，为低；否则缺结束日期为中；其余为高。
7. 识别到的复查日期写入结束日期为空、或复查日期不晚于结束日期的条目。
8. 所有条目的生效日期都等于开具日期（"出院后""术后"的起点无法从文字确定，作为已知误差在评测记录里说明）。

三份样例的预期提取结果：

| 样例 | 条目（类别、涉及对象、预计结束、复查、把握） | 忽略的句子 | 结果说明 |
|---|---|---|---|
| short_term | 饮食禁忌 [辛辣, 油腻, 生冷食物, 酒] 10-06 无 高；饮食要求 [清淡, 流质, 半流质] 10-02 无 高 | 急性胃肠炎（无要求）；口服补液盐，按说明服用（用药）；如腹泻加重或发热请及时复诊（条件性） | 无 |
| chronic | 饮食要求 [低盐, 低脂, 糖尿病饮食] 长期 12-30 高；饮食禁忌 [烟, 酒] 无 12-30 中；饮食禁忌 [含糖饮料, 甜点] 无 12-30 中；运动限制 [剧烈运动] 无 12-30 中 | 高血压、2型糖尿病（无要求） | 无 |
| post_surgery | 饮食禁忌 [油炸食物, 肥肉, 动物内脏] 10-29 10-14 高；饮食要求 [低脂] 10-29 10-14 高；运动限制 [提重物, 剧烈运动] 10-13 无 高 | 腹腔镜胆囊切除术后（无要求） | 识别到多个复查时间（2026-10-14、2026-10-20），已取最早的一个，请核对。 |

- [ ] **Step 1: 写失败测试**

`backend/tests/test_medical_extraction.py`
```python
from datetime import date

from app.medical.extraction import (
    NOTE_HEDGE,
    NOTE_MEDICATION,
    NOTE_NO_DURATION,
    REASON_CONDITIONAL,
    REASON_MEDICATION,
    REASON_NO_REQUIREMENT,
    REASON_REVIEW_WITHOUT_DATE,
    RuleBasedExtractor,
    add_months,
    get_extractor,
    parse_number,
    split_sentences,
)
from app.medical.samples import SAMPLE_ORDERS, SAMPLE_TITLES

ORDER_DATE = date(2026, 9, 30)


def _extract(text: str):
    return RuleBasedExtractor().extract(text, ORDER_DATE)


def _summary(result):
    return [(i.category, i.subjects, i.end_date, i.review_date, i.confidence) for i in result.items]


def _ignored(result):
    return [(i.text, i.reason) for i in result.ignored]


def test_parse_number():
    assert parse_number("12") == 12
    assert parse_number("两") == 2
    assert parse_number("十") == 10
    assert parse_number("十四") == 14
    assert parse_number("二十") == 20
    assert parse_number("二十一") == 21
    assert parse_number("一二") is None


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 9, 30), 3) == date(2026, 12, 30)
    assert add_months(date(2026, 11, 15), 2) == date(2027, 1, 15)


def test_split_sentences_handles_labels_and_numbering():
    text = "诊断：急性胃肠炎。\n医嘱：1. 少吃辛辣。2、多喝水；（3）两周后复查"
    assert split_sentences(text) == ["急性胃肠炎", "少吃辛辣", "多喝水", "两周后复查"]


def test_decimal_numbers_are_not_list_markers():
    assert split_sentences("阿莫西林0.5g口服") == ["阿莫西林0.5g口服"]


def test_short_term_sample():
    result = _extract(SAMPLE_ORDERS["short_term"])
    assert _summary(result) == [
        ("diet_avoid", ["辛辣", "油腻", "生冷食物", "酒"], date(2026, 10, 6), None, "high"),
        ("diet_require", ["清淡", "流质", "半流质"], date(2026, 10, 2), None, "high"),
    ]
    assert _ignored(result) == [
        ("急性胃肠炎", REASON_NO_REQUIREMENT),
        ("口服补液盐，按说明服用", REASON_MEDICATION),
        ("如腹泻加重或发热请及时复诊", REASON_CONDITIONAL),
    ]
    assert result.notes == []
    for item in result.items:
        assert item.start_date == ORDER_DATE
        assert item.content == item.source_excerpt
        assert item.missing_fields == []


def test_chronic_sample():
    result = _extract(SAMPLE_ORDERS["chronic"])
    review = date(2026, 12, 30)
    assert _summary(result) == [
        ("diet_require", ["低盐", "低脂", "糖尿病饮食"], None, review, "high"),
        ("diet_avoid", ["烟", "酒"], None, review, "medium"),
        ("diet_avoid", ["含糖饮料", "甜点"], None, review, "medium"),
        ("exercise_limit", ["剧烈运动"], None, review, "medium"),
    ]
    assert result.items[0].missing_fields == []
    assert [item.missing_fields for item in result.items[1:]] == [["end_date"]] * 3
    assert NOTE_NO_DURATION in result.items[1].notes
    assert _ignored(result) == [("高血压、2型糖尿病", REASON_NO_REQUIREMENT)]


def test_post_surgery_sample():
    result = _extract(SAMPLE_ORDERS["post_surgery"])
    assert _summary(result) == [
        ("diet_avoid", ["油炸食物", "肥肉", "动物内脏"], date(2026, 10, 29), date(2026, 10, 14), "high"),
        ("diet_require", ["低脂"], date(2026, 10, 29), date(2026, 10, 14), "high"),
        ("exercise_limit", ["提重物", "剧烈运动"], date(2026, 10, 13), None, "high"),
    ]
    assert result.notes == ["识别到多个复查时间（2026-10-14、2026-10-20），已取最早的一个，请核对。"]
    assert _ignored(result) == [("腹腔镜胆囊切除术后", REASON_NO_REQUIREMENT)]


def test_medication_diet_is_always_low_confidence():
    result = _extract("服用头孢期间及停药后一周内禁酒。")
    assert _summary(result) == [("medication_diet", ["酒"], date(2026, 10, 6), None, "low")]
    assert NOTE_MEDICATION in result.items[0].notes


def test_medication_without_diet_is_ignored():
    result = _extract("按时吃药。")
    assert result.items == []
    assert _ignored(result) == [("按时吃药", REASON_MEDICATION)]


def test_hedged_wording_is_low_confidence():
    result = _extract("酌情少吃甜食。")
    assert _summary(result) == [("diet_avoid", ["甜食"], None, None, "low")]
    assert result.items[0].missing_fields == ["end_date"]
    assert result.items[0].notes == [NOTE_NO_DURATION, NOTE_HEDGE]


def test_review_without_date_is_ignored():
    result = _extract("定期复查。")
    assert result.items == []
    assert _ignored(result) == [("定期复查", REASON_REVIEW_WITHOUT_DATE)]


def test_explicit_review_dates_without_year():
    assert _extract("少吃辛辣。10月8日复诊。").items[0].review_date == date(2026, 10, 8)
    assert _extract("少吃辛辣。3月1日复查。").items[0].review_date == date(2027, 3, 1)


def test_review_date_not_applied_after_end_date():
    result = _extract("三天内忌酒。两周后复查。")
    assert _summary(result) == [("diet_avoid", ["酒"], date(2026, 10, 2), None, "high")]


def test_get_extractor_returns_rule_based_extractor():
    extractor = get_extractor()
    assert isinstance(extractor, RuleBasedExtractor)
    assert extractor.name == "rule-based-v1"


def test_samples_have_titles():
    assert set(SAMPLE_ORDERS) == set(SAMPLE_TITLES) == {"short_term", "chronic", "post_surgery"}
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_medical_extraction.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.medical'`

- [ ] **Step 3: 实现样例**

`backend/app/medical/__init__.py`：空文件。

`backend/app/medical/samples.py`
```python
"""三份演示与评测用的医嘱样例。内容为虚构，只用于演示与检验提取效果，不是医疗建议。"""

SAMPLE_ORDERS = {
    "short_term": (
        "诊断：急性胃肠炎。\n"
        "医嘱：1. 口服补液盐，按说明服用。2. 一周内忌食辛辣、油腻、生冷食物，禁酒。"
        "3. 清淡流质或半流质饮食三天。4. 如腹泻加重或发热请及时复诊。"
    ),
    "chronic": (
        "高血压、2型糖尿病。长期低盐低脂糖尿病饮食，每日食盐不超过5克。戒烟限酒。"
        "避免含糖饮料和甜点。每天快走30分钟，避免剧烈运动。三个月后复查血糖、血脂。"
    ),
    "post_surgery": (
        "腹腔镜胆囊切除术后。出院后1个月内低脂饮食，忌油炸食物、肥肉和动物内脏。"
        "术后两周内避免提重物及剧烈运动。术后2周门诊复查，2026年10月20日复诊。"
    ),
}

SAMPLE_TITLES = {
    "short_term": "短期忌口：急性胃肠炎",
    "chronic": "长期慢病饮食：高血压合并 2 型糖尿病",
    "post_surgery": "带复查日的术后饮食限制：腹腔镜胆囊切除术后",
}
```

- [ ] **Step 4: 实现提取器**

`backend/app/medical/extraction.py`
```python
"""医嘱提取。

提取器只产出"候选条目"，全部是待确认状态，必须由用户逐条确认后才生效。
步骤 03 使用基于关键词与日期规则的提取器；步骤 07 接入大模型后，
实现同一个 Extractor 接口的模型提取器，并在 get_extractor() 中切换即可。
"""

import calendar
import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Protocol

CATEGORY_ORDER = ("medication_diet", "diet_avoid", "diet_require", "exercise_limit", "other")

AVOID_TRIGGERS = (
    "不要吃", "不能吃", "不要喝", "不能喝", "禁止", "禁食", "忌食", "忌口", "限制",
    "不宜", "避免", "少吃", "少喝", "禁", "忌", "戒", "勿", "限",
)
REQUIRE_STYLES = (
    "糖尿病饮食", "少量多餐", "优质蛋白", "高蛋白", "高纤维", "半流质", "流质",
    "低盐", "低脂", "低糖", "低嘌呤", "清淡", "软食", "多饮水", "多喝水",
)
EXERCISE_WORDS = ("剧烈运动", "运动", "锻炼", "健身", "提重物", "负重", "跑步", "游泳", "弯腰", "久坐", "久站", "卧床")
MEDICATION_WORDS = ("服药", "用药", "吃药", "停药", "药物", "服用", "口服", "输液", "注射", "抗生素", "头孢", "华法林")
MEDICATION_DIET_HINTS = ("酒", "饮食", "吃", "喝", "茶", "咖啡", "葡萄柚", "西柚", "牛奶", "食物")
REVIEW_WORDS = ("复查", "复诊", "随访")
CONDITIONAL_WORDS = ("如", "若", "如果", "必要时", "一旦")
LONG_TERM_WORDS = ("长期", "终身", "永久", "坚持")
HEDGE_WORDS = ("适量", "酌情", "必要时", "视情况", "尽量")
LONG_SUBJECT_CHARS = 12

REASON_NO_REQUIREMENT = "没有识别到饮食、用药相关饮食或运动方面的要求"
REASON_MEDICATION = "用药信息（药名、用法、剂量）不在本系统判断范围内，请遵医嘱或咨询医生、药师"
REASON_CONDITIONAL = "条件性提醒（出现某种情况时就医），不作为固定约束，请留意身体变化"
REASON_REVIEW_WITHOUT_DATE = "提到复查但没有写明时间，请在条目里手动填写复查日期"

NOTE_NO_DURATION = "没有识别到持续时间，请补充预计结束日期，或确认这是长期要求"
NOTE_HEDGE = "原文措辞不确定（如适量、酌情），请核对具体要求"
NOTE_MEDICATION = "涉及用药，时间范围可能以用药或停药为起点，请务必对照原文核对；药物本身的用法用量请遵医嘱或咨询药师"
NOTE_LONG_SUBJECT = "涉及对象较长，可能没有正确拆分，请核对"

_NUM = r"(\d+|[一二两三四五六七八九十]+)"
DURATION_RE = re.compile(_NUM + r"\s*(个月|个星期|星期|周|天|日|月|年)")
EXPLICIT_DATE_RE = re.compile(
    r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*[日号]?"
    r"|(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
)
SENTENCE_SPLIT_RE = re.compile(r"[。；;！!？?\n]+|(?<![\d.])\d{1,2}[.、．](?!\d)|[（(]\d{1,2}[)）]")
LABEL_RE = re.compile(r"^[^：:，,]{1,6}[：:]")
PART_SPLIT_RE = re.compile(r"以及|[、和及与或/]")
CLAUSE_END_RE = re.compile(r"[，,]")
_TRIGGER_RE = re.compile("|".join(map(re.escape, sorted(AVOID_TRIGGERS, key=len, reverse=True))))
_STYLE_RE = re.compile("|".join(map(re.escape, sorted(REQUIRE_STYLES, key=len, reverse=True))))
_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


@dataclass(frozen=True)
class ExtractedItem:
    category: str
    content: str
    subjects: list[str]
    start_date: date
    end_date: date | None
    review_date: date | None
    confidence: str  # high / medium / low
    source_excerpt: str
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IgnoredSentence:
    text: str
    reason: str


@dataclass(frozen=True)
class ExtractionResult:
    extractor: str
    items: list[ExtractedItem]
    ignored: list[IgnoredSentence]
    notes: list[str]


class Extractor(Protocol):
    name: str

    def extract(self, text: str, order_date: date) -> ExtractionResult: ...


def parse_number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    if "十" in text:
        tens, _, ones = text.partition("十")
        if (tens and tens not in _DIGITS) or (ones and ones not in _DIGITS):
            return None
        return (_DIGITS[tens] if tens else 1) * 10 + (_DIGITS[ones] if ones else 0)
    return _DIGITS.get(text)


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def add_duration(start: date, amount: int, unit: str) -> date:
    if unit in ("天", "日"):
        return start + timedelta(days=amount)
    if unit in ("周", "星期", "个星期"):
        return start + timedelta(weeks=amount)
    if unit in ("个月", "月"):
        return add_months(start, amount)
    return add_months(start, 12 * amount)


def split_sentences(text: str) -> list[str]:
    sentences = []
    for raw in SENTENCE_SPLIT_RE.split(text):
        sentence = LABEL_RE.sub("", raw.strip()).strip(" ，,")
        if sentence:
            sentences.append(sentence)
    return sentences


def _first_duration(text: str) -> tuple[int, str] | None:
    for match in DURATION_RE.finditer(text):
        amount = parse_number(match.group(1))
        if amount:
            return amount, match.group(2)
    return None


def _explicit_dates(text: str, order_date: date) -> list[date]:
    found = []
    for match in EXPLICIT_DATE_RE.finditer(text):
        has_year = match.group(1) is not None
        if has_year:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        else:
            year, month, day = order_date.year, int(match.group(4)), int(match.group(5))
        try:
            value = date(year, month, day)
            if not has_year and value < order_date:
                value = date(year + 1, month, day)  # 没写年份且早于开具日期，按明年理解
        except ValueError:
            continue
        found.append(value)
    return found


def _clean_subject(part: str) -> str:
    part = DURATION_RE.sub("", part)
    for word in ("期间", "以内", "之内", "食用", "饮用"):
        part = part.replace(word, "")
    return part.strip(" 　的等内")


def _avoid_subjects(sentence: str) -> list[str]:
    subjects: list[str] = []
    matches = list(_TRIGGER_RE.finditer(sentence))
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(sentence)
        segment = CLAUSE_END_RE.split(sentence[match.end():stop])[0]
        for part in PART_SPLIT_RE.split(segment):
            cleaned = _clean_subject(part)
            if cleaned and cleaned not in subjects:
                subjects.append(cleaned)
    return subjects


def _styles(sentence: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in _STYLE_RE.finditer(sentence)))


class RuleBasedExtractor:
    name = "rule-based-v1"

    def extract(self, text: str, order_date: date) -> ExtractionResult:
        items: list[ExtractedItem] = []
        ignored: list[IgnoredSentence] = []
        reviews: list[date] = []
        notes: list[str] = []
        for sentence in split_sentences(text):
            if any(word in sentence for word in REVIEW_WORDS):
                found = self._review_dates(sentence, order_date)
                if found:
                    reviews.extend(found)
                elif any(word in sentence for word in CONDITIONAL_WORDS):
                    ignored.append(IgnoredSentence(sentence, REASON_CONDITIONAL))
                else:
                    ignored.append(IgnoredSentence(sentence, REASON_REVIEW_WITHOUT_DATE))
                continue
            new_items, skipped = self._sentence_items(sentence, order_date)
            items.extend(new_items)
            if skipped is not None:
                ignored.append(skipped)

        if reviews:
            review_date = min(reviews)
            distinct = sorted({day.isoformat() for day in reviews})
            if len(distinct) > 1:
                notes.append(f"识别到多个复查时间（{'、'.join(distinct)}），已取最早的一个，请核对。")
            items = [
                replace(item, review_date=review_date)
                if item.end_date is None or review_date <= item.end_date
                else item
                for item in items
            ]
        return ExtractionResult(extractor=self.name, items=items, ignored=ignored, notes=notes)

    @staticmethod
    def _review_dates(sentence: str, order_date: date) -> list[date]:
        found = _explicit_dates(sentence, order_date)
        duration = _first_duration(EXPLICIT_DATE_RE.sub(" ", sentence))
        if duration:
            found.append(add_duration(order_date, *duration))
        return found

    def _sentence_items(
        self, sentence: str, order_date: date
    ) -> tuple[list[ExtractedItem], IgnoredSentence | None]:
        candidates: list[tuple[str, list[str], list[str]]] = []
        if any(word in sentence for word in MEDICATION_WORDS):
            rest = sentence
            for word in MEDICATION_WORDS:
                rest = rest.replace(word, "")
            if not any(hint in rest for hint in MEDICATION_DIET_HINTS):
                return [], IgnoredSentence(sentence, REASON_MEDICATION)
            candidates.append(("medication_diet", _avoid_subjects(sentence) or _styles(sentence), [NOTE_MEDICATION]))
        else:
            avoid = _avoid_subjects(sentence)
            exercise = [s for s in avoid if any(word in s for word in EXERCISE_WORDS)]
            diet = [s for s in avoid if s not in exercise]
            styles = _styles(sentence)
            if diet:
                candidates.append(("diet_avoid", diet, []))
            if styles:
                candidates.append(("diet_require", styles, []))
            if exercise:
                candidates.append(("exercise_limit", exercise, []))
        if not candidates:
            return [], IgnoredSentence(sentence, REASON_NO_REQUIREMENT)

        long_term = any(word in sentence for word in LONG_TERM_WORDS)
        duration = _first_duration(EXPLICIT_DATE_RE.sub(" ", sentence))
        end_date = None
        if duration and not long_term:
            end_date = add_duration(order_date, *duration) - timedelta(days=1)
        hedge = any(word in sentence for word in HEDGE_WORDS)
        items = [
            self._build(category, subjects, extra, sentence, order_date, end_date, long_term, hedge)
            for category, subjects, extra in candidates
        ]
        return items, None

    @staticmethod
    def _build(
        category: str,
        subjects: list[str],
        extra_notes: list[str],
        sentence: str,
        order_date: date,
        end_date: date | None,
        long_term: bool,
        hedge: bool,
    ) -> ExtractedItem:
        notes = list(extra_notes)
        missing: list[str] = []
        if end_date is None and not long_term:
            missing.append("end_date")
            notes.append(NOTE_NO_DURATION)
        long_subject = any(len(subject) > LONG_SUBJECT_CHARS for subject in subjects)
        if category == "medication_diet" or not subjects or hedge or long_subject:
            confidence = "low"
            if hedge:
                notes.append(NOTE_HEDGE)
            if long_subject:
                notes.append(NOTE_LONG_SUBJECT)
            if not subjects:
                missing.append("subjects")
        elif missing:
            confidence = "medium"
        else:
            confidence = "high"
        return ExtractedItem(
            category=category,
            content=sentence,
            subjects=subjects,
            start_date=order_date,
            end_date=end_date,
            review_date=None,
            confidence=confidence,
            source_excerpt=sentence,
            missing_fields=missing,
            notes=notes,
        )


def get_extractor() -> Extractor:
    """当前使用的提取器。步骤 07 接入大模型后在这里切换。"""
    return RuleBasedExtractor()
```

- [ ] **Step 5: 运行确认通过**

Run: `uv run pytest tests/test_medical_extraction.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。若某个样例断言失败，先对照"规则提取器的行为"逐句推演；确认是计划的推演错误时，在报告中写明实际输出与原因后再改断言，不要为凑断言去改规则。

- [ ] **Step 6: 提交**

```
git add backend/app/medical backend/tests/test_medical_extraction.py
git commit -m "feat(medical): add pluggable order extractor with rule-based implementation and samples"
```

---

### Task 2: 加密二进制类型、数据表、医嘱录入与条目核心操作

**Files:**
- Modify: `backend/app/security/crypto.py`（追加 `EncryptedBytes`）
- Create: `backend/app/medical/models.py`, `backend/app/medical/items.py`, `backend/app/medical/orders.py`
- Create: `backend/migrations/versions/0007_medical.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_medical_orders.py`

**Interfaces:**
- Consumes: 任务 1 的 `get_extractor`、`ExtractionResult`；`UserOwnedMixin`、`owned_by`、`get_owned_or_404`、`EncryptedJSON`、`AppError`
- Produces:
  - `app.security.crypto.EncryptedBytes`：原始字节加密后以二进制存储
  - ORM（表名）：`MedicalOrder`（medical_orders）、`MedicalEvidence`（medical_evidence）、`MedicalItem`（medical_items）、`MedicalItemEvent`（medical_item_events）
  - `app.medical.items`：状态常量 `PENDING_CONFIRMATION`、`ACTIVE`、`PENDING_REVIEW`、`RESOLVED`、`VOIDED`、`STATUSES`、`HARD_CONSTRAINT_STATUSES`、`EDITABLE_STATUSES`；`EDITABLE_FIELDS`；`validate_item_dates(start, end, review)`；`record_event(db, item, action, *, from_status, source, detail=None)`；`get_item(db, user_id, item_id)`；`list_items(db, user_id, status=None, category=None)`；`list_events(db, user_id, item_id)`
  - `app.medical.orders`：`create_order(db, user_id, text, order_date, today) -> MedicalOrder`、`list_orders(db, user_id)`、`get_order(db, user_id, order_id)`、`list_order_items(db, user_id, order_id)`、`add_manual_item(db, user_id, order_id, fields: dict) -> MedicalItem`
  - 错误码：`order_in_future`(422)、`invalid_item_dates`(422)、`not_found`(404)
  - 审计动作名（本任务用到）：`created`；来源取值 `user`、`system`、`extractor`、`agent`

表结构要点：
- medical_orders：id、user_id、order_date（日期）、source_text（加密）、extractor（字符串 32）、extraction_notes（加密，内容为忽略句子列表与结果说明）、created_at。
- medical_evidence：id、user_id、order_id（外键，级联删除，带索引）、filename（加密）、content_type、size_bytes、content（EncryptedBytes，延迟加载）、created_at。
- medical_items：id、user_id、order_id（外键，级联删除，带索引）、position（在所属医嘱中的顺序）、category、status、origin（extracted 或 manual）、confidence（可空，手动条目为空）、content（加密）、subjects（加密）、source_excerpt（加密，可空）、start_date、end_date、review_date、missing_fields（JSONB）、notes（JSONB）、resolution_proposed_at、resolution_reason（加密，可空）、confirmed_at、closed_at、created_at、updated_at。
- medical_item_events：id、user_id、item_id（外键，级联删除，带索引）、seq（自增序号，用于稳定排序）、occurred_at、action、from_status（可空）、to_status、source、detail（加密，可空）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_medical_orders.py`
```python
from datetime import date

import pytest
from sqlalchemy import select, text

from app.auth.service import register_user
from app.db import get_engine, get_sessionmaker
from app.errors import AppError
from app.medical import items, orders
from app.medical.models import MedicalItemEvent
from app.medical.samples import SAMPLE_ORDERS
from app.security.crypto import EncryptedBytes, decrypt_value

TODAY = date(2026, 9, 30)


@pytest.fixture
def db():
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def alice(db):
    return register_user(db, "alice", "secret-pass-1").id


@pytest.fixture
def bella(db):
    return register_user(db, "bella", "secret-pass-1").id


def test_encrypted_bytes_roundtrip():
    column = EncryptedBytes()
    raw = b"\x89PNG\r\n\x1a\n" + b"secret-image-bytes"
    stored = column.process_bind_param(raw, None)
    assert stored != raw
    assert b"secret-image-bytes" not in stored
    assert column.process_result_value(stored, None) == raw
    assert column.process_bind_param(None, None) is None


def test_create_order_extracts_pending_items(db, alice):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    assert order.extractor == "rule-based-v1"
    assert order.order_date == TODAY
    assert order.source_text == SAMPLE_ORDERS["short_term"]
    assert len(order.extraction_notes["ignored"]) == 3
    assert order.extraction_notes["notes"] == []
    created = orders.list_order_items(db, alice, order.id)
    assert [item.category for item in created] == ["diet_avoid", "diet_require"]
    assert [item.position for item in created] == [1, 2]
    assert {item.status for item in created} == {items.PENDING_CONFIRMATION}
    assert {item.origin for item in created} == {"extracted"}
    assert created[0].subjects == ["辛辣", "油腻", "生冷食物", "酒"]
    assert created[0].end_date == date(2026, 10, 6)
    assert created[0].confirmed_at is None
    events = db.scalars(select(MedicalItemEvent).where(MedicalItemEvent.item_id == created[0].id)).all()
    assert [(e.action, e.from_status, e.to_status, e.source) for e in events] == [
        ("created", None, "pending_confirmation", "extractor")
    ]


def test_order_date_cannot_be_in_future(db, alice):
    with pytest.raises(AppError) as exc:
        orders.create_order(db, alice, "少吃辛辣。", date(2026, 10, 1), TODAY)
    assert exc.value.code == "order_in_future"


def test_orders_are_listed_newest_first(db, alice):
    first = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    second = orders.create_order(db, alice, SAMPLE_ORDERS["chronic"], TODAY, TODAY)
    assert [o.id for o in orders.list_orders(db, alice)] == [second.id, first.id]


def test_manual_item(db, alice):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    item = orders.add_manual_item(db, alice, order.id, {"category": "other", "content": "每天测血压", "subjects": []})
    assert (item.origin, item.confidence, item.status) == ("manual", None, "pending_confirmation")
    assert item.start_date == TODAY
    assert item.position == 3
    assert item.source_excerpt is None
    assert [e.action for e in items.list_events(db, alice, item.id)] == ["created"]
    assert items.list_events(db, alice, item.id)[0].source == "user"
    with pytest.raises(AppError) as exc:
        orders.add_manual_item(
            db, alice, order.id,
            {"category": "other", "content": "x", "start_date": date(2026, 10, 5), "end_date": date(2026, 10, 1)},
        )
    assert exc.value.code == "invalid_item_dates"


def test_list_items_filters(db, alice):
    orders.create_order(db, alice, SAMPLE_ORDERS["chronic"], TODAY, TODAY)
    assert len(items.list_items(db, alice)) == 4
    assert len(items.list_items(db, alice, category="diet_avoid")) == 2
    assert len(items.list_items(db, alice, status="active")) == 0


def test_orders_and_items_are_private(db, alice, bella):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    item_id = orders.list_order_items(db, alice, order.id)[0].id
    for call in (
        lambda: orders.get_order(db, bella, order.id),
        lambda: orders.add_manual_item(db, bella, order.id, {"category": "other", "content": "x"}),
        lambda: items.get_item(db, bella, item_id),
        lambda: items.list_events(db, bella, item_id),
    ):
        with pytest.raises(AppError) as exc:
            call()
        assert exc.value.code == "not_found"
    assert orders.list_orders(db, bella) == []
    assert items.list_items(db, bella) == []
    assert orders.list_order_items(db, bella, order.id) == []


def test_sensitive_columns_are_encrypted_at_rest(db, alice):
    orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    with get_engine().connect() as conn:
        source = conn.execute(text("SELECT source_text, extraction_notes FROM medical_orders")).one()
        rows = conn.execute(text("SELECT content, subjects, source_excerpt FROM medical_items")).all()
    raw = " ".join(source) + " ".join(" ".join(row) for row in rows)
    for plaintext in ("急性胃肠炎", "辛辣", "生冷食物", "补液盐"):
        assert plaintext not in raw
    assert decrypt_value(source[0]) == SAMPLE_ORDERS["short_term"]
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_medical_orders.py -v`
Expected: FAIL（`ImportError: cannot import name 'EncryptedBytes'`）

- [ ] **Step 3: EncryptedBytes**

`backend/app/security/crypto.py`：import 行加上 `LargeBinary`，文件末尾追加：
```python
class EncryptedBytes(TypeDecorator):
    """原始字节（如医嘱图片）加密后以二进制存储。"""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: bytes | None, dialect: Any) -> bytes | None:
        return None if value is None else _fernet().encrypt(value)

    def process_result_value(self, value: bytes | None, dialect: Any) -> bytes | None:
        return None if value is None else _fernet().decrypt(value)
```

- [ ] **Step 4: 模型与迁移**

`backend/app/medical/models.py`
```python
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Identity, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedBytes, EncryptedJSON


class MedicalOrder(UserOwnedMixin, Base):
    """用户录入的一份医嘱原文，以及提取时被忽略的句子与说明。"""

    __tablename__ = "medical_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_date: Mapped[date] = mapped_column(Date)
    source_text: Mapped[str] = mapped_column(EncryptedJSON)
    extractor: Mapped[str] = mapped_column(String(32))
    extraction_notes: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicalEvidence(UserOwnedMixin, Base):
    """医嘱图片或文档，加密保存，只对本人可见。"""

    __tablename__ = "medical_evidence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_orders.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(EncryptedJSON)
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(EncryptedBytes, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicalItem(UserOwnedMixin, Base):
    """一条结构化医嘱约束。日期、类别、状态明文，便于查询与判断到期；内容加密。"""

    __tablename__ = "medical_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    origin: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str | None] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(EncryptedJSON)
    subjects: Mapped[list[str]] = mapped_column(EncryptedJSON)
    source_excerpt: Mapped[str | None] = mapped_column(EncryptedJSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    notes: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    resolution_proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(EncryptedJSON)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MedicalItemEvent(UserOwnedMixin, Base):
    """审计记录：每次创建、修改与状态变化各一条。"""

    __tablename__ = "medical_item_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_items.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict[str, Any] | None] = mapped_column(EncryptedJSON)
```

`backend/app/models.py` 追加一行：
```python
from app.medical import models as medical_models  # noqa: F401
```

`backend/migrations/versions/0007_medical.py`
```python
"""create medical tables

Revision ID: 0007_medical
Revises: 0006_cycle_status_encrypt
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_medical"
down_revision = "0006_cycle_status_encrypt"
branch_labels = None
depends_on = None


def _user_fk() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "medical_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("extractor", sa.String(32), nullable=False),
        sa.Column("extraction_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_orders_user_id", "medical_orders", ["user_id"])

    op.create_table(
        "medical_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("medical_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_evidence_user_id", "medical_evidence", ["user_id"])
    op.create_index("ix_medical_evidence_order_id", "medical_evidence", ["order_id"])

    op.create_table(
        "medical_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("medical_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(8)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("subjects", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("review_date", sa.Date()),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("resolution_proposed_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_reason", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_items_user_id", "medical_items", ["user_id"])
    op.create_index("ix_medical_items_order_id", "medical_items", ["order_id"])

    op.create_table(
        "medical_item_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("medical_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(24)),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("detail", sa.Text()),
    )
    op.create_index("ix_medical_item_events_user_id", "medical_item_events", ["user_id"])
    op.create_index("ix_medical_item_events_item_id", "medical_item_events", ["item_id"])


def downgrade() -> None:
    op.drop_table("medical_item_events")
    op.drop_table("medical_items")
    op.drop_table("medical_evidence")
    op.drop_table("medical_orders")
```

- [ ] **Step 5: items 核心与 orders**

`backend/app/medical/items.py`
```python
"""医嘱条目的状态流转、审计记录与约束查询。每一次创建、修改与状态变化都写审计记录。"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.medical.models import MedicalItem, MedicalItemEvent

PENDING_CONFIRMATION = "pending_confirmation"
ACTIVE = "active"
PENDING_REVIEW = "pending_review"
RESOLVED = "resolved"
VOIDED = "voided"
STATUSES = (PENDING_CONFIRMATION, ACTIVE, PENDING_REVIEW, RESOLVED, VOIDED)
HARD_CONSTRAINT_STATUSES = (ACTIVE, PENDING_REVIEW)  # 待复核期间仍按原要求执行
EDITABLE_STATUSES = (PENDING_CONFIRMATION, ACTIVE, PENDING_REVIEW)
EDITABLE_FIELDS = ("category", "content", "subjects", "start_date", "end_date", "review_date")
SOURCES = ("user", "system", "extractor", "agent")


def now() -> datetime:
    return datetime.now(UTC)


def validate_item_dates(start: date, end: date | None, review: date | None) -> None:
    if end is not None and end < start:
        raise AppError(422, "invalid_item_dates", "预计结束日期不能早于生效日期")
    if review is not None and review < start:
        raise AppError(422, "invalid_item_dates", "复查日期不能早于生效日期")


def record_event(
    db: Session,
    item: MedicalItem,
    action: str,
    *,
    from_status: str | None,
    source: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if source not in SOURCES:
        raise ValueError(f"unknown event source: {source}")
    db.add(
        MedicalItemEvent(
            user_id=item.user_id,
            item_id=item.id,
            action=action,
            from_status=from_status,
            to_status=item.status,
            source=source,
            detail=detail,
        )
    )


def get_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> MedicalItem:
    return get_owned_or_404(db, MedicalItem, user_id, item_id)


def list_items(
    db: Session, user_id: uuid.UUID, status: str | None = None, category: str | None = None
) -> list[MedicalItem]:
    query = owned_by(MedicalItem, user_id)
    if status is not None:
        query = query.where(MedicalItem.status == status)
    if category is not None:
        query = query.where(MedicalItem.category == category)
    return list(db.scalars(query.order_by(MedicalItem.created_at.desc(), MedicalItem.position)))


def list_events(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> list[MedicalItemEvent]:
    item = get_item(db, user_id, item_id)
    query = owned_by(MedicalItemEvent, user_id).where(MedicalItemEvent.item_id == item.id)
    return list(db.scalars(query.order_by(MedicalItemEvent.seq)))
```

`backend/app/medical/orders.py`
```python
"""医嘱原文、提取入库与手动补充条目。"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.medical.extraction import get_extractor
from app.medical.items import PENDING_CONFIRMATION, record_event, validate_item_dates
from app.medical.models import MedicalItem, MedicalOrder


def create_order(db: Session, user_id: uuid.UUID, text: str, order_date: date, today: date) -> MedicalOrder:
    if order_date > today:
        raise AppError(422, "order_in_future", "医嘱日期不能晚于今天")
    result = get_extractor().extract(text, order_date)
    order = MedicalOrder(
        user_id=user_id,
        order_date=order_date,
        source_text=text,
        extractor=result.extractor,
        extraction_notes={
            "ignored": [{"text": ignored.text, "reason": ignored.reason} for ignored in result.ignored],
            "notes": result.notes,
        },
    )
    db.add(order)
    db.flush()
    for position, extracted in enumerate(result.items, start=1):
        item = MedicalItem(
            user_id=user_id,
            order_id=order.id,
            position=position,
            category=extracted.category,
            status=PENDING_CONFIRMATION,
            origin="extracted",
            confidence=extracted.confidence,
            content=extracted.content,
            subjects=extracted.subjects,
            source_excerpt=extracted.source_excerpt,
            start_date=extracted.start_date,
            end_date=extracted.end_date,
            review_date=extracted.review_date,
            missing_fields=extracted.missing_fields,
            notes=extracted.notes,
        )
        db.add(item)
        db.flush()
        record_event(db, item, "created", from_status=None, source="extractor")
    db.commit()
    db.refresh(order)
    return order


def list_orders(db: Session, user_id: uuid.UUID) -> list[MedicalOrder]:
    return list(db.scalars(owned_by(MedicalOrder, user_id).order_by(MedicalOrder.created_at.desc())))


def get_order(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> MedicalOrder:
    return get_owned_or_404(db, MedicalOrder, user_id, order_id)


def list_order_items(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> list[MedicalItem]:
    query = owned_by(MedicalItem, user_id).where(MedicalItem.order_id == order_id).order_by(MedicalItem.position)
    return list(db.scalars(query))


def add_manual_item(db: Session, user_id: uuid.UUID, order_id: uuid.UUID, fields: dict[str, Any]) -> MedicalItem:
    """用户手动补充提取器漏掉的条目。与提取的条目一样先进入待确认。"""
    order = get_order(db, user_id, order_id)
    start = fields.get("start_date") or order.order_date
    end = fields.get("end_date")
    review = fields.get("review_date")
    validate_item_dates(start, end, review)
    last = db.scalar(select(func.max(MedicalItem.position)).where(MedicalItem.order_id == order.id)) or 0
    item = MedicalItem(
        user_id=user_id,
        order_id=order.id,
        position=last + 1,
        category=fields["category"],
        status=PENDING_CONFIRMATION,
        origin="manual",
        confidence=None,
        content=fields["content"],
        subjects=fields.get("subjects") or [],
        source_excerpt=None,
        start_date=start,
        end_date=end,
        review_date=review,
        missing_fields=[],
        notes=[],
    )
    db.add(item)
    db.flush()
    record_event(db, item, "created", from_status=None, source="user")
    db.commit()
    db.refresh(item)
    return item
```

- [ ] **Step 6: 运行确认通过**

Run: `uv run pytest tests/test_medical_orders.py -v`，然后 `uv run pytest -q -W error`，再对开发库执行 `uv run alembic upgrade head`
Expected: 全部通过、无警告（`test_migrations.py`、`test_every_business_table_has_user_id`、路由闸门测试都要通过）；开发库迁移到 0007。

- [ ] **Step 7: 提交**

```
git add backend/app backend/migrations backend/tests/test_medical_orders.py
git commit -m "feat(medical): add medical tables, encrypted evidence type and order extraction intake"
```

---

### Task 3: 条目生命周期、到期检查与约束查询

**Files:**
- Modify: `backend/app/medical/items.py`（追加）
- Test: `backend/tests/test_medical_items.py`

**Interfaces:**
- Consumes: 任务 2 的 items 核心、orders、models
- Produces（`app.medical.items`）:
  - 常量 `REVIEW_LEAD_DAYS = 1`、`CONSTRAINT_REMINDER: str`
  - 数据类 `Constraint(item_id, category, content, subjects, start_date, end_date, review_date, status, needs_review, resolution_proposed)`（frozen）
  - `update_item(db, user_id, item_id, changes) -> MedicalItem`
  - `confirm_item(db, user_id, item_id, changes, today) -> MedicalItem`
  - `void_item(db, user_id, item_id, reason) -> MedicalItem`
  - `continue_item(db, user_id, item_id, end_date, review_date, today) -> MedicalItem`
  - `propose_resolution(db, user_id, item_id, reason, source) -> MedicalItem`（source 为 user 或 agent）
  - `cancel_resolution_proposal(db, user_id, item_id) -> MedicalItem`
  - `resolve_item(db, user_id, item_id, reason) -> MedicalItem`
  - `refresh_statuses(db, user_id, today) -> int`（返回本次改变状态的条目数）
  - `get_current_constraints(db, user_id, today, category=None) -> list[Constraint]`（步骤 04 读取的入口）
  - `list_reviews(db, user_id, today) -> list[MedicalItem]`
  - 错误码：`item_closed`(409)、`invalid_transition`(409)、`still_due`(422)、`no_proposal`(409)
  - 审计动作名：`edited`、`confirmed`、`voided`、`review_due`、`expired`、`continued`、`resolution_proposed`、`resolution_proposal_cancelled`、`resolved`

状态流转规则（在本文件一处实现）：

| 动作 | 允许的起始状态 | 结果状态 | 来源 |
|---|---|---|---|
| 修改 | 待确认、生效中、待复核 | 不变 | user |
| 确认 | 待确认 | 生效中（若已到期，随后立即刷新为待复核） | user |
| 作废 | 待确认、生效中、待复核 | 已作废 | user |
| 到期检查 | 生效中 | 待复核 | system |
| 过期作废 | 待确认且预计结束日期早于今天 | 已作废 | system |
| 继续执行 | 待复核（新日期不能仍已到期） | 生效中 | user |
| 提出解除建议 | 生效中、待复核 | 不变 | user 或 agent |
| 取消解除建议 | 有待处理建议时 | 不变 | user |
| 确认解除 | 生效中、待复核 | 已解除 | user |

到期判断：复查日期不晚于今天，或"预计结束日期减 1 天"不晚于今天。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_medical_items.py`
```python
from datetime import date

import pytest

from app.auth.service import register_user
from app.db import get_sessionmaker
from app.errors import AppError
from app.medical import items, orders
from app.medical.samples import SAMPLE_ORDERS

TODAY = date(2026, 9, 30)


@pytest.fixture
def db():
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def alice(db):
    return register_user(db, "alice", "secret-pass-1").id


@pytest.fixture
def bella(db):
    return register_user(db, "bella", "secret-pass-1").id


def _order(db, user_id, key="short_term"):
    order = orders.create_order(db, user_id, SAMPLE_ORDERS[key], TODAY, TODAY)
    return orders.list_order_items(db, user_id, order.id)


def _events(db, user_id, item_id):
    return [(e.action, e.from_status, e.to_status, e.source) for e in items.list_events(db, user_id, item_id)]


def _code(call) -> str:
    with pytest.raises(AppError) as exc:
        call()
    return exc.value.code


def test_unconfirmed_items_are_not_constraints(db, alice):
    _order(db, alice)
    assert items.get_current_constraints(db, alice, TODAY) == []


def test_confirm_makes_item_a_constraint(db, alice):
    avoid, _ = _order(db, alice)
    subjects = ["辛辣", "油腻", "生冷食物", "酒", "咖啡"]
    confirmed = items.confirm_item(db, alice, avoid.id, {"subjects": subjects}, TODAY)
    assert confirmed.status == "active"
    assert confirmed.confirmed_at is not None
    assert confirmed.missing_fields == []
    constraints = items.get_current_constraints(db, alice, TODAY)
    assert [(c.item_id, c.subjects, c.needs_review, c.resolution_proposed) for c in constraints] == [
        (avoid.id, subjects, False, False)
    ]
    assert _events(db, alice, avoid.id) == [
        ("created", None, "pending_confirmation", "extractor"),
        ("confirmed", "pending_confirmation", "active", "user"),
    ]
    assert _code(lambda: items.confirm_item(db, alice, avoid.id, {}, TODAY)) == "invalid_transition"


def test_constraints_filter_by_category(db, alice):
    avoid, require = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.confirm_item(db, alice, require.id, {}, TODAY)
    assert [c.category for c in items.get_current_constraints(db, alice, TODAY)] == ["diet_avoid", "diet_require"]
    only = items.get_current_constraints(db, alice, TODAY, category="diet_require")
    assert [c.item_id for c in only] == [require.id]


def test_future_start_is_not_yet_a_constraint(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(
        db, alice, avoid.id, {"start_date": date(2026, 10, 5), "end_date": date(2026, 10, 20)}, TODAY
    )
    assert items.get_current_constraints(db, alice, TODAY) == []
    assert [c.item_id for c in items.get_current_constraints(db, alice, date(2026, 10, 5))] == [avoid.id]


def test_edit_records_fields_and_rejects_bad_dates(db, alice):
    avoid, _ = _order(db, alice)
    items.update_item(db, alice, avoid.id, {"content": "一周内忌辛辣油腻", "end_date": date(2026, 10, 8)})
    edited = items.get_item(db, alice, avoid.id)
    assert (edited.content, edited.end_date) == ("一周内忌辛辣油腻", date(2026, 10, 8))
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status, last.source) == (
        "edited", "pending_confirmation", "pending_confirmation", "user"
    )
    assert last.detail == {"fields": ["content", "end_date"]}
    assert _code(lambda: items.update_item(db, alice, avoid.id, {"end_date": date(2026, 9, 1)})) == "invalid_item_dates"
    db.refresh(edited)
    assert edited.end_date == date(2026, 10, 8)


def test_missing_fields_shrink_when_filled(db, alice):
    order = orders.create_order(db, alice, "少吃辛辣。", TODAY, TODAY)
    item = orders.list_order_items(db, alice, order.id)[0]
    assert (item.confidence, item.missing_fields) == ("medium", ["end_date"])
    updated = items.update_item(db, alice, item.id, {"end_date": date(2026, 10, 30)})
    assert updated.missing_fields == []


def test_active_item_enters_review_before_end_date(db, alice):
    avoid, require = _order(db, alice)  # 预计结束 10-06
    items.void_item(db, alice, require.id, None)  # 避免未确认条目过期作废干扰计数
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    assert items.refresh_statuses(db, alice, date(2026, 10, 4)) == 0
    assert items.get_item(db, alice, avoid.id).status == "active"
    assert items.refresh_statuses(db, alice, date(2026, 10, 5)) == 1
    item = items.get_item(db, alice, avoid.id)
    assert item.status == "pending_review"
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status, last.source) == (
        "review_due", "active", "pending_review", "system"
    )
    assert "预计结束日期" in last.detail["reason"]
    for later in (date(2026, 10, 7), date(2026, 12, 31)):
        constraints = items.get_current_constraints(db, alice, later)
        assert [(c.item_id, c.needs_review) for c in constraints] == [(avoid.id, True)]


def test_review_date_triggers_review(db, alice):
    first = _order(db, alice, "chronic")[0]  # 长期，复查 12-30
    items.confirm_item(db, alice, first.id, {}, TODAY)
    assert items.refresh_statuses(db, alice, date(2026, 12, 29)) == 0
    assert items.refresh_statuses(db, alice, date(2026, 12, 30)) == 1
    assert "复查" in items.list_events(db, alice, first.id)[-1].detail["reason"]


def test_confirming_an_already_due_item_goes_straight_to_review(db, alice):
    _, require = _order(db, alice)  # 预计结束 10-02
    confirmed = items.confirm_item(db, alice, require.id, {}, date(2026, 10, 1))
    assert confirmed.status == "pending_review"
    assert [e[0] for e in _events(db, alice, require.id)] == ["created", "confirmed", "review_due"]


def test_unconfirmed_item_expires_after_end_date(db, alice):
    avoid, require = _order(db, alice)
    assert items.refresh_statuses(db, alice, date(2026, 10, 2)) == 0
    assert items.refresh_statuses(db, alice, date(2026, 10, 3)) == 1
    expired = items.get_item(db, alice, require.id)
    assert expired.status == "voided"
    assert expired.closed_at is not None
    assert _events(db, alice, require.id)[-1] == ("expired", "pending_confirmation", "voided", "system")
    assert items.get_item(db, alice, avoid.id).status == "pending_confirmation"


def test_proposal_does_not_change_constraint(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    proposed = items.propose_resolution(db, alice, avoid.id, "用户说医生告诉她已经好了", "agent")
    assert proposed.status == "active"
    assert proposed.resolution_proposed_at is not None
    constraints = items.get_current_constraints(db, alice, TODAY)
    assert [(c.item_id, c.resolution_proposed) for c in constraints] == [(avoid.id, True)]
    assert [i.id for i in items.list_reviews(db, alice, TODAY)] == [avoid.id]
    cancelled = items.cancel_resolution_proposal(db, alice, avoid.id)
    assert cancelled.resolution_proposed_at is None and cancelled.resolution_reason is None
    assert items.list_reviews(db, alice, TODAY) == []
    assert _code(lambda: items.cancel_resolution_proposal(db, alice, avoid.id)) == "no_proposal"
    assert [e[0] for e in _events(db, alice, avoid.id)] == [
        "created", "confirmed", "resolution_proposed", "resolution_proposal_cancelled"
    ]
    assert _events(db, alice, avoid.id)[2][3] == "agent"


def test_proposal_requires_a_hard_constraint_and_a_valid_source(db, alice):
    avoid, _ = _order(db, alice)
    assert _code(lambda: items.propose_resolution(db, alice, avoid.id, "x", "user")) == "invalid_transition"
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    with pytest.raises(ValueError):
        items.propose_resolution(db, alice, avoid.id, "x", "robot")


def test_resolve_removes_constraint_but_keeps_history(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.propose_resolution(db, alice, avoid.id, "复诊后医生说可以恢复正常饮食", "user")
    resolved = items.resolve_item(db, alice, avoid.id, None)
    assert resolved.status == "resolved"
    assert resolved.closed_at is not None
    assert resolved.resolution_reason == "复诊后医生说可以恢复正常饮食"
    assert resolved.resolution_proposed_at is None
    assert items.get_current_constraints(db, alice, TODAY) == []
    assert [i.id for i in items.list_items(db, alice, status="resolved")] == [avoid.id]
    assert _events(db, alice, avoid.id)[-1] == ("resolved", "active", "resolved", "user")
    assert _code(lambda: items.update_item(db, alice, avoid.id, {"content": "x"})) == "item_closed"
    assert _code(lambda: items.resolve_item(db, alice, avoid.id, None)) == "invalid_transition"


def test_resolve_directly_from_review(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    resolved = items.resolve_item(db, alice, avoid.id, "复查正常")
    assert resolved.resolution_reason == "复查正常"
    assert _events(db, alice, avoid.id)[-1] == ("resolved", "pending_review", "resolved", "user")


def test_continue_after_review(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    later = date(2026, 10, 5)
    assert _code(lambda: items.continue_item(db, alice, avoid.id, date(2026, 10, 6), None, later)) == "still_due"
    assert _code(lambda: items.continue_item(db, alice, avoid.id, None, date(2026, 10, 5), later)) == "still_due"
    continued = items.continue_item(db, alice, avoid.id, date(2026, 10, 20), None, later)
    assert (continued.status, continued.end_date) == ("active", date(2026, 10, 20))
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status) == ("continued", "pending_review", "active")
    assert last.detail == {"end_date": "2026-10-20", "review_date": None}
    assert _code(lambda: items.continue_item(db, alice, avoid.id, None, None, later)) == "invalid_transition"


def test_continue_as_long_term(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    continued = items.continue_item(db, alice, avoid.id, None, None, date(2026, 10, 5))
    assert (continued.status, continued.end_date, continued.review_date) == ("active", None, None)


def test_void(db, alice):
    avoid, _ = _order(db, alice)
    voided = items.void_item(db, alice, avoid.id, "提取错误，这条不是医嘱")
    assert voided.status == "voided"
    assert voided.closed_at is not None
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.source, last.detail) == ("voided", "user", {"reason": "提取错误，这条不是医嘱"})
    assert _code(lambda: items.void_item(db, alice, avoid.id, None)) == "item_closed"


def test_items_are_private(db, alice, bella):
    avoid, _ = _order(db, alice)
    calls = (
        lambda: items.get_item(db, bella, avoid.id),
        lambda: items.update_item(db, bella, avoid.id, {"content": "x"}),
        lambda: items.confirm_item(db, bella, avoid.id, {}, TODAY),
        lambda: items.void_item(db, bella, avoid.id, None),
        lambda: items.resolve_item(db, bella, avoid.id, None),
        lambda: items.list_events(db, bella, avoid.id),
    )
    for call in calls:
        assert _code(call) == "not_found"
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    assert items.get_current_constraints(db, bella, TODAY) == []
    assert items.list_reviews(db, bella, TODAY) == []
    assert items.refresh_statuses(db, bella, date(2026, 10, 5)) == 0
    assert items.get_item(db, alice, avoid.id).status == "active"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_medical_items.py -v`
Expected: FAIL（`AttributeError: module 'app.medical.items' has no attribute 'get_current_constraints'` 等）

- [ ] **Step 3: 实现**

`backend/app/medical/items.py`：import 补上 `from dataclasses import dataclass`、`from datetime import timedelta`、`from types import SimpleNamespace`，并在文件末尾追加：
```python
REVIEW_LEAD_DAYS = 1
CONSTRAINT_REMINDER = "以上是你确认过的医嘱约束，请遵医嘱；待复核的条目在你确认解除之前仍按原要求执行，如有疑问请咨询医生。"


@dataclass(frozen=True)
class Constraint:
    item_id: uuid.UUID
    category: str
    content: str
    subjects: list[str]
    start_date: date
    end_date: date | None
    review_date: date | None
    status: str
    needs_review: bool
    resolution_proposed: bool


def _transition(
    db: Session, item: MedicalItem, action: str, to_status: str, source: str, detail: dict[str, Any] | None = None
) -> None:
    from_status = item.status
    item.status = to_status
    if to_status in (RESOLVED, VOIDED):
        item.closed_at = now()
    record_event(db, item, action, from_status=from_status, source=source, detail=detail)


def _apply_changes(item: MedicalItem, changes: dict[str, Any]) -> None:
    """先校验合并后的日期，校验通过才写入，避免出错时留下改了一半的数据。"""
    merged = {name: changes.get(name, getattr(item, name)) for name in EDITABLE_FIELDS}
    validate_item_dates(merged["start_date"], merged["end_date"], merged["review_date"])
    for name, value in changes.items():
        setattr(item, name, value)
    item.missing_fields = [name for name in item.missing_fields if not getattr(item, name)]


def _due_reason(item: Any, today: date) -> str | None:
    if item.review_date is not None and item.review_date <= today:
        return "已到复查日期，请确认是否还需要继续遵守"
    if item.end_date is not None and item.end_date - timedelta(days=REVIEW_LEAD_DAYS) <= today:
        if item.end_date < today:
            return "已过预计结束日期，请确认是否还需要继续遵守"
        return "即将到预计结束日期，请确认是否还需要继续遵守"
    return None


def _clear_proposal(item: MedicalItem) -> None:
    item.resolution_proposed_at = None
    item.resolution_reason = None


def refresh_statuses(db: Session, user_id: uuid.UUID, today: date) -> int:
    """到期的生效条目转为待复核；过了预计结束日期仍未确认的条目自动作废。"""
    changed = 0
    query = owned_by(MedicalItem, user_id).where(MedicalItem.status.in_([ACTIVE, PENDING_CONFIRMATION]))
    for item in list(db.scalars(query)):
        if item.status == ACTIVE:
            reason = _due_reason(item, today)
            if reason:
                _transition(db, item, "review_due", PENDING_REVIEW, "system", {"reason": reason})
                changed += 1
        elif item.end_date is not None and item.end_date < today:
            _transition(db, item, "expired", VOIDED, "system", {"reason": "未确认的条目已过预计结束日期，自动作废"})
            changed += 1
    if changed:
        db.commit()
    return changed


def update_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, changes: dict[str, Any]) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise AppError(409, "item_closed", "已解除或已作废的条目不能再修改")
    if changes:
        _apply_changes(item, changes)
        record_event(db, item, "edited", from_status=item.status, source="user", detail={"fields": sorted(changes)})
        db.commit()
        db.refresh(item)
    return item


def confirm_item(
    db: Session, user_id: uuid.UUID, item_id: uuid.UUID, changes: dict[str, Any], today: date
) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status != PENDING_CONFIRMATION:
        raise AppError(409, "invalid_transition", "只有待确认的条目可以确认")
    if changes:
        _apply_changes(item, changes)
    item.missing_fields = []  # 用户确认即表示接受当前内容，未填结束日期视为长期
    item.confirmed_at = now()
    _transition(db, item, "confirmed", ACTIVE, "user", {"fields": sorted(changes)} if changes else None)
    db.commit()
    refresh_statuses(db, user_id, today)
    db.refresh(item)
    return item


def void_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str | None) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise AppError(409, "item_closed", "已解除或已作废的条目不能再作废")
    _clear_proposal(item)
    _transition(db, item, "voided", VOIDED, "user", {"reason": reason} if reason else None)
    db.commit()
    db.refresh(item)
    return item


def continue_item(
    db: Session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    end_date: date | None,
    review_date: date | None,
    today: date,
) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status != PENDING_REVIEW:
        raise AppError(409, "invalid_transition", "只有待复核的条目可以继续执行")
    validate_item_dates(item.start_date, end_date, review_date)
    if _due_reason(SimpleNamespace(end_date=end_date, review_date=review_date), today):
        raise AppError(422, "still_due", "新的预计结束日期或复查日期仍然已到期，请设置更晚的日期，或者确认解除")
    item.end_date, item.review_date = end_date, review_date
    _clear_proposal(item)
    detail = {
        "end_date": end_date.isoformat() if end_date else None,
        "review_date": review_date.isoformat() if review_date else None,
    }
    _transition(db, item, "continued", ACTIVE, "user", detail)
    db.commit()
    db.refresh(item)
    return item


def propose_resolution(
    db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str, source: str
) -> MedicalItem:
    """只记录"建议解除"，不改变约束。source 为 user 或 agent（步骤 08 的智能体）。"""
    if source not in ("user", "agent"):
        raise ValueError(f"resolution can only be proposed by user or agent, got {source}")
    item = get_item(db, user_id, item_id)
    if item.status not in HARD_CONSTRAINT_STATUSES:
        raise AppError(409, "invalid_transition", "只有生效中或待复核的条目可以提出解除建议")
    item.resolution_proposed_at = now()
    item.resolution_reason = reason
    record_event(db, item, "resolution_proposed", from_status=item.status, source=source, detail={"reason": reason})
    db.commit()
    db.refresh(item)
    return item


def cancel_resolution_proposal(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.resolution_proposed_at is None:
        raise AppError(409, "no_proposal", "这个条目没有待处理的解除建议")
    _clear_proposal(item)
    record_event(db, item, "resolution_proposal_cancelled", from_status=item.status, source="user")
    db.commit()
    db.refresh(item)
    return item


def resolve_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str | None) -> MedicalItem:
    """只能由用户确认解除。可以先有解除建议，也可以直接解除。"""
    item = get_item(db, user_id, item_id)
    if item.status not in HARD_CONSTRAINT_STATUSES:
        raise AppError(409, "invalid_transition", "只有生效中或待复核的条目可以解除")
    if reason:
        item.resolution_reason = reason
    item.resolution_proposed_at = None
    _transition(db, item, "resolved", RESOLVED, "user", {"reason": item.resolution_reason})
    db.commit()
    db.refresh(item)
    return item


def get_current_constraints(
    db: Session, user_id: uuid.UUID, today: date, category: str | None = None
) -> list[Constraint]:
    """当天生效的全部医嘱硬约束（生效中与待复核）。步骤 04 的约束引擎从这里读取。"""
    refresh_statuses(db, user_id, today)
    query = owned_by(MedicalItem, user_id).where(
        MedicalItem.status.in_(HARD_CONSTRAINT_STATUSES), MedicalItem.start_date <= today
    )
    if category is not None:
        query = query.where(MedicalItem.category == category)
    query = query.order_by(MedicalItem.category, MedicalItem.start_date, MedicalItem.position)
    return [
        Constraint(
            item_id=item.id,
            category=item.category,
            content=item.content,
            subjects=item.subjects,
            start_date=item.start_date,
            end_date=item.end_date,
            review_date=item.review_date,
            status=item.status,
            needs_review=item.status == PENDING_REVIEW,
            resolution_proposed=item.resolution_proposed_at is not None,
        )
        for item in db.scalars(query)
    ]


def list_reviews(db: Session, user_id: uuid.UUID, today: date) -> list[MedicalItem]:
    """需要用户处理的条目：待复核的，以及有待处理解除建议的。步骤 08 的智能体开场时读取。"""
    refresh_statuses(db, user_id, today)
    query = owned_by(MedicalItem, user_id).where(
        MedicalItem.status.in_(HARD_CONSTRAINT_STATUSES),
        (MedicalItem.status == PENDING_REVIEW) | MedicalItem.resolution_proposed_at.is_not(None),
    )
    return list(db.scalars(query.order_by(MedicalItem.start_date, MedicalItem.position)))
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_medical_items.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。

- [ ] **Step 5: 提交**

```
git add backend/app/medical/items.py backend/tests/test_medical_items.py
git commit -m "feat(medical): add item lifecycle, due review, audited resolution and constraint query"
```

---

### Task 4: 接口、证据文件与访问控制

**Files:**
- Modify: `backend/pyproject.toml`、`backend/uv.lock`（`uv add python-multipart`）
- Modify: `backend/app/medical/orders.py`（追加证据文件函数）
- Create: `backend/app/medical/schemas.py`, `backend/app/medical/deps.py`, `backend/app/medical/router.py`
- Modify: `backend/app/main.py`、`backend/tests/test_route_guards.py`
- Test: `backend/tests/test_medical_api.py`

**Interfaces:**
- Consumes: 任务 1 至 3 的全部；`get_today`、`require_disclaimer_user`、`get_or_create_profile`、`compute_capabilities`、`tests.helpers.ready_user`
- Produces:
  - `app.medical.orders`：`MAX_EVIDENCE_BYTES = 10 * 1024 * 1024`、`EVIDENCE_EXTENSIONS`、`sniff_content_type(content) -> str | None`、`add_evidence(db, user_id, order_id, filename, content) -> MedicalEvidence`、`list_evidence(db, user_id, order_id)`、`get_evidence(db, user_id, evidence_id)`
  - `app.medical.deps.require_medical_user(...) -> User`：能力清单未开放时 403 `medical_not_available`；通过后刷新该用户的到期状态
  - 18 个接口（前缀 `/api/medical`）：POST/GET `/orders`、GET `/orders/{order_id}`、POST `/orders/{order_id}/items`、POST `/orders/{order_id}/evidence`、GET `/evidence/{evidence_id}`、GET `/items`（可按 status、category 过滤）、GET/PATCH `/items/{item_id}`、POST `/items/{item_id}/confirm`、`/void`、`/continue`、`/propose-resolution`、`/cancel-proposal`、`/resolve`、GET `/items/{item_id}/events`、GET `/constraints`（可按 category 过滤）、GET `/reviews`
  - 错误码：`evidence_empty`(422)、`evidence_too_large`(413)、`evidence_type_not_allowed`(415)、`medical_not_available`(403)

- [ ] **Step 1: 安装依赖**

在 `backend/` 执行 `uv add python-multipart`。

- [ ] **Step 2: 写失败测试**

`backend/tests/test_route_guards.py` 末尾追加（复用文件中已有的 `_api_routes`、`_dependency_calls`）：
```python
def test_every_medical_route_requires_medical_user():
    from app.medical.deps import require_medical_user

    routes = [ctx for ctx in _api_routes(create_app()) if ctx.path.startswith("/api/medical/")]
    assert len(routes) >= 18
    missing = [ctx.path for ctx in routes if require_medical_user not in _dependency_calls(ctx.dependant)]
    assert missing == []
```

`backend/tests/test_medical_api.py`
```python
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from app.medical.orders import MAX_EVIDENCE_BYTES
from app.medical.samples import SAMPLE_ORDERS
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 9, 30)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def medical():
    state = {"today": TODAY}
    app = create_app()
    app.dependency_overrides[get_today] = lambda: state["today"]
    with TestClient(app) as test_client:
        yield test_client, state


def _order(client, headers, key="short_term"):
    response = client.post("/api/medical/orders", json={"text": SAMPLE_ORDERS[key]}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_order_returns_pending_items_and_ignored(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    body = _order(client, headers)
    assert body["order_date"] == "2026-09-30"
    assert body["extractor"] == "rule-based-v1"
    assert body["source_text"] == SAMPLE_ORDERS["short_term"]
    assert [item["category"] for item in body["items"]] == ["diet_avoid", "diet_require"]
    assert {item["status"] for item in body["items"]} == {"pending_confirmation"}
    assert {item["low_confidence"] for item in body["items"]} == {False}
    assert len(body["ignored"]) == 3
    assert body["evidence"] == []
    constraints = client.get("/api/medical/constraints", headers=headers).json()
    assert constraints["constraints"] == []
    assert "遵医嘱" in constraints["reminder"]
    listed = client.get("/api/medical/orders", headers=headers).json()
    assert [o["id"] for o in listed] == [body["id"]]
    assert client.get(f"/api/medical/orders/{body['id']}", headers=headers).json()["id"] == body["id"]


def test_order_validation(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    future = client.post("/api/medical/orders", json={"text": "少吃辛辣。", "order_date": "2026-10-01"}, headers=headers)
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "order_in_future"
    for bad in ({"text": ""}, {"text": "x", "user_id": "x"}, {}):
        assert client.post("/api/medical/orders", json=bad, headers=headers).status_code == 422


def test_low_confidence_items_are_flagged(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    response = client.post(
        "/api/medical/orders", json={"text": "酌情少吃甜食。服用头孢期间禁酒。"}, headers=headers
    )
    items = response.json()["items"]
    assert [(i["category"], i["confidence"], i["low_confidence"]) for i in items] == [
        ("diet_avoid", "low", True),
        ("medication_diet", "low", True),
    ]
    assert all(item["notes"] for item in items)


def test_confirm_and_query_constraints(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid, require = _order(client, headers)["items"]
    confirmed = client.post(
        f"/api/medical/items/{avoid['id']}/confirm",
        json={"subjects": ["辛辣", "油腻", "生冷食物", "酒", "咖啡"]},
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
    assert client.post(f"/api/medical/items/{require['id']}/confirm", headers=headers).status_code == 200
    body = client.get("/api/medical/constraints", headers=headers).json()
    assert [(c["item_id"], c["needs_review"]) for c in body["constraints"]] == [
        (avoid["id"], False), (require["id"], False)
    ]
    assert body["constraints"][0]["subjects"][-1] == "咖啡"
    only = client.get("/api/medical/constraints", params={"category": "diet_require"}, headers=headers).json()
    assert [c["item_id"] for c in only["constraints"]] == [require["id"]]
    twice = client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "invalid_transition")


def test_edit_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    edited = client.patch(
        f"/api/medical/items/{avoid['id']}", json={"content": "一周内忌辛辣", "end_date": "2026-10-08"}, headers=headers
    )
    assert (edited.status_code, edited.json()["end_date"]) == (200, "2026-10-08")
    bad = client.patch(f"/api/medical/items/{avoid['id']}", json={"end_date": "2026-09-01"}, headers=headers)
    assert bad.json()["error"]["code"] == "invalid_item_dates"
    for body in ({"content": None}, {"category": "robot"}, {"status": "active"}):
        assert client.patch(f"/api/medical/items/{avoid['id']}", json=body, headers=headers).status_code == 422


def test_review_proposal_and_resolution_flow(medical):
    client, state = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    state["today"] = date(2026, 10, 5)
    reviews = client.get("/api/medical/reviews", headers=headers).json()
    assert [(i["id"], i["status"]) for i in reviews] == [(avoid["id"], "pending_review")]
    constraints = client.get("/api/medical/constraints", headers=headers).json()["constraints"]
    assert [(c["item_id"], c["needs_review"]) for c in constraints] == [(avoid["id"], True)]
    proposed = client.post(
        f"/api/medical/items/{avoid['id']}/propose-resolution", json={"reason": "复诊正常"}, headers=headers
    ).json()
    assert proposed["status"] == "pending_review"
    assert proposed["resolution_proposed_at"] is not None
    assert len(client.get("/api/medical/constraints", headers=headers).json()["constraints"]) == 1
    resolved = client.post(f"/api/medical/items/{avoid['id']}/resolve", headers=headers).json()
    assert (resolved["status"], resolved["resolution_reason"]) == ("resolved", "复诊正常")
    assert client.get("/api/medical/constraints", headers=headers).json()["constraints"] == []
    history = client.get("/api/medical/items", params={"status": "resolved"}, headers=headers).json()
    assert [i["id"] for i in history] == [avoid["id"]]
    events = client.get(f"/api/medical/items/{avoid['id']}/events", headers=headers).json()
    assert [(e["action"], e["source"]) for e in events] == [
        ("created", "extractor"),
        ("confirmed", "user"),
        ("review_due", "system"),
        ("resolution_proposed", "user"),
        ("resolved", "user"),
    ]
    assert events[-1]["detail"] == {"reason": "复诊正常"}


def test_continue_and_cancel_proposal(medical):
    client, state = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    none = client.post(f"/api/medical/items/{avoid['id']}/cancel-proposal", headers=headers)
    assert (none.status_code, none.json()["error"]["code"]) == (409, "no_proposal")
    client.post(f"/api/medical/items/{avoid['id']}/propose-resolution", json={"reason": "感觉好了"}, headers=headers)
    cancelled = client.post(f"/api/medical/items/{avoid['id']}/cancel-proposal", headers=headers).json()
    assert cancelled["resolution_proposed_at"] is None
    state["today"] = date(2026, 10, 5)
    due = client.post(f"/api/medical/items/{avoid['id']}/continue", json={"end_date": "2026-10-06"}, headers=headers)
    assert (due.status_code, due.json()["error"]["code"]) == (422, "still_due")
    ok = client.post(f"/api/medical/items/{avoid['id']}/continue", json={"end_date": "2026-10-31"}, headers=headers)
    assert (ok.status_code, ok.json()["status"], ok.json()["end_date"]) == (200, "active", "2026-10-31")


def test_void_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    voided = client.post(f"/api/medical/items/{avoid['id']}/void", json={"reason": "不是医嘱"}, headers=headers)
    assert voided.json()["status"] == "voided"
    again = client.post(f"/api/medical/items/{avoid['id']}/void", headers=headers)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "item_closed")


def test_manual_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    order = _order(client, headers)
    created = client.post(
        f"/api/medical/orders/{order['id']}/items",
        json={"category": "other", "content": "每天早晚测血压"},
        headers=headers,
    )
    assert created.status_code == 201
    assert (created.json()["origin"], created.json()["confidence"], created.json()["low_confidence"]) == (
        "manual", None, False
    )
    assert created.json()["start_date"] == "2026-09-30"
    bad_dates = client.post(
        f"/api/medical/orders/{order['id']}/items",
        json={"category": "other", "content": "x", "start_date": "2026-10-05", "end_date": "2026-10-01"},
        headers=headers,
    )
    assert bad_dates.json()["error"]["code"] == "invalid_item_dates"
    for bad in ({"category": "robot", "content": "x"}, {"category": "other"}, {"category": "other", "content": "x", "user_id": "x"}):
        assert client.post(f"/api/medical/orders/{order['id']}/items", json=bad, headers=headers).status_code == 422


def test_evidence_upload_download_and_privacy(medical):
    client, _ = medical
    alice = ready_user(client, "alice")
    order = _order(client, alice)
    uploaded = client.post(
        f"/api/medical/orders/{order['id']}/evidence", files={"file": ("order-photo.png", PNG, "image/png")}, headers=alice
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    assert (evidence["filename"], evidence["content_type"], evidence["size_bytes"]) == ("order-photo.png", "image/png", len(PNG))
    detail = client.get(f"/api/medical/orders/{order['id']}", headers=alice).json()
    assert [e["id"] for e in detail["evidence"]] == [evidence["id"]]
    downloaded = client.get(f"/api/medical/evidence/{evidence['id']}", headers=alice)
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
    assert downloaded.headers["content-type"] == "image/png"
    assert downloaded.headers["cache-control"] == "no-store"
    assert f"evidence-{evidence['id']}.png" in downloaded.headers["content-disposition"]
    bella = ready_user(client, "bella")
    assert client.get(f"/api/medical/evidence/{evidence['id']}", headers=bella).status_code == 404
    assert client.get(f"/api/medical/orders/{order['id']}", headers=bella).status_code == 404
    assert client.post(
        f"/api/medical/orders/{order['id']}/evidence", files={"file": ("x.png", PNG, "image/png")}, headers=bella
    ).status_code == 404
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT filename, content FROM medical_evidence")).one()
    assert "order-photo" not in row[0]
    assert not bytes(row[1]).startswith(b"\x89PNG")


def test_evidence_rejects_bad_files(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    order_id = _order(client, headers)["id"]
    url = f"/api/medical/orders/{order_id}/evidence"
    cases = [
        (("note.txt", b"hello world", "text/plain"), 415, "evidence_type_not_allowed"),
        (("fake.png", b"not really a png", "image/png"), 415, "evidence_type_not_allowed"),
        (("empty.png", b"", "image/png"), 422, "evidence_empty"),
        (("big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_EVIDENCE_BYTES, "image/png"), 413, "evidence_too_large"),
    ]
    for file, status, code in cases:
        response = client.post(url, files={"file": file}, headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), file[0]
    pdf = client.post(url, files={"file": ("a.pdf", b"%PDF-1.7\n...", "application/pdf")}, headers=headers)
    assert pdf.json()["content_type"] == "application/pdf"


def test_other_users_cannot_touch_items(medical):
    client, _ = medical
    alice = ready_user(client, "alice")
    avoid = _order(client, alice)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=alice)
    bella = ready_user(client, "bella")
    for method, path, kwargs in [
        ("get", f"/api/medical/items/{avoid['id']}", {}),
        ("patch", f"/api/medical/items/{avoid['id']}", {"json": {"content": "x"}}),
        ("post", f"/api/medical/items/{avoid['id']}/resolve", {}),
        ("post", f"/api/medical/items/{avoid['id']}/propose-resolution", {"json": {"reason": "x"}}),
        ("get", f"/api/medical/items/{avoid['id']}/events", {}),
    ]:
        response = getattr(client, method)(path, headers=bella, **kwargs)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found"), path
    assert client.get("/api/medical/items", headers=bella).json() == []
    assert client.get("/api/medical/constraints", headers=bella).json()["constraints"] == []
    assert client.get("/api/medical/reviews", headers=bella).json() == []
    assert client.get(f"/api/medical/items/{avoid['id']}", headers=alice).json()["status"] == "active"


def test_medical_requires_login_and_disclaimer_but_any_gender(medical):
    client, _ = medical
    assert client.get("/api/medical/orders").status_code == 401
    unaccepted = register_and_login(client, "carl")
    assert client.get("/api/medical/orders", headers=unaccepted).json()["error"]["code"] == "disclaimer_not_accepted"
    male = ready_user(client, "bob", {"gender": "male"})
    assert client.post("/api/medical/orders", json={"text": "少吃辛辣。"}, headers=male).status_code == 201
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_medical_api.py tests/test_route_guards.py -v`
Expected: FAIL（接口返回 404；`No module named 'app.medical.deps'`）

- [ ] **Step 4: 证据文件函数**

`backend/app/medical/orders.py`：import 行补上 `MedicalEvidence`，末尾追加：
```python
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
EVIDENCE_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def sniff_content_type(content: bytes) -> str | None:
    """按文件头判断类型，不相信客户端声明的类型。"""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def add_evidence(
    db: Session, user_id: uuid.UUID, order_id: uuid.UUID, filename: str, content: bytes
) -> MedicalEvidence:
    order = get_order(db, user_id, order_id)
    if not content:
        raise AppError(422, "evidence_empty", "上传的文件是空的")
    if len(content) > MAX_EVIDENCE_BYTES:
        raise AppError(413, "evidence_too_large", "文件不能超过 10 MB")
    content_type = sniff_content_type(content)
    if content_type is None:
        raise AppError(415, "evidence_type_not_allowed", "只支持 JPG、PNG、WEBP 图片或 PDF 文件")
    evidence = MedicalEvidence(
        user_id=user_id,
        order_id=order.id,
        filename=(filename or "未命名文件")[:200],
        content_type=content_type,
        size_bytes=len(content),
        content=content,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> list[MedicalEvidence]:
    query = owned_by(MedicalEvidence, user_id).where(MedicalEvidence.order_id == order_id)
    return list(db.scalars(query.order_by(MedicalEvidence.created_at)))


def get_evidence(db: Session, user_id: uuid.UUID, evidence_id: uuid.UUID) -> MedicalEvidence:
    return get_owned_or_404(db, MedicalEvidence, user_id, evidence_id)
```

- [ ] **Step 5: schemas、deps、router**

`backend/app/medical/schemas.py`
```python
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_validator

Category = Literal["diet_avoid", "diet_require", "medication_diet", "exercise_limit", "other"]
ItemStatus = Literal["pending_confirmation", "active", "pending_review", "resolved", "voided"]
Confidence = Literal["high", "medium", "low"]
EventSource = Literal["user", "system", "extractor", "agent"]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    order_date: date | None = None


class ManualItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    content: Content
    subjects: list[Subject] = Field(default_factory=list, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    review_date: date | None = None


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category | None = None
    content: Content | None = None
    subjects: list[Subject] | None = Field(default=None, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    review_date: date | None = None

    @field_validator("category", "content", "subjects", "start_date")
    @classmethod
    def not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("这个字段不能为空")
        return value


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


class ProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class ContinueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    end_date: date | None = None
    review_date: date | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    category: Category
    status: ItemStatus
    origin: Literal["extracted", "manual"]
    confidence: Confidence | None
    content: str
    subjects: list[str]
    source_excerpt: str | None
    start_date: date
    end_date: date | None
    review_date: date | None
    missing_fields: list[str]
    notes: list[str]
    resolution_proposed_at: datetime | None
    resolution_reason: str | None
    confirmed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def low_confidence(self) -> bool:
        return self.confidence == "low"


class IgnoredOut(BaseModel):
    text: str
    reason: str


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class OrderOut(BaseModel):
    id: uuid.UUID
    order_date: date
    source_text: str
    extractor: str
    created_at: datetime
    ignored: list[IgnoredOut]
    notes: list[str]
    items: list[ItemOut]
    evidence: list[EvidenceOut]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    occurred_at: datetime
    action: str
    from_status: ItemStatus | None
    to_status: ItemStatus
    source: EventSource
    detail: dict[str, Any] | None


class ConstraintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    category: Category
    content: str
    subjects: list[str]
    start_date: date
    end_date: date | None
    review_date: date | None
    status: ItemStatus
    needs_review: bool
    resolution_proposed: bool


class ConstraintsOut(BaseModel):
    constraints: list[ConstraintOut]
    reminder: str
```

`backend/app/medical/deps.py`
```python
from datetime import date
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.medical import items
from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile


def require_medical_user(
    user: Annotated[User, Depends(require_disclaimer_user)],
    db: Annotated[Session, Depends(get_db)],
    today: Annotated[date, Depends(get_today)],
) -> User:
    """医嘱接口的统一入口：已确认免责声明、能力清单开放了医嘱模块；每次请求前刷新到期状态。"""
    if not compute_capabilities(get_or_create_profile(db, user.id))["medical"]:
        raise AppError(403, "medical_not_available", "医嘱功能当前不可用")
    items.refresh_statuses(db, user.id, today)
    return user
```

`backend/app/medical/router.py`
```python
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.medical import items, orders
from app.medical.deps import require_medical_user
from app.medical.models import MedicalEvidence, MedicalItem, MedicalItemEvent, MedicalOrder
from app.medical.schemas import (
    Category,
    ConstraintOut,
    ConstraintsOut,
    ContinueBody,
    EventOut,
    EvidenceOut,
    IgnoredOut,
    ItemOut,
    ItemStatus,
    ItemUpdate,
    ManualItemCreate,
    OrderCreate,
    OrderOut,
    ProposalBody,
    ReasonBody,
)

router = APIRouter(prefix="/api/medical", tags=["medical"])

MedicalUser = Annotated[User, Depends(require_medical_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]


def _order_out(db: Session, user_id: uuid.UUID, order: MedicalOrder) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_date=order.order_date,
        source_text=order.source_text,
        extractor=order.extractor,
        created_at=order.created_at,
        ignored=[IgnoredOut(**ignored) for ignored in order.extraction_notes["ignored"]],
        notes=order.extraction_notes["notes"],
        items=[ItemOut.model_validate(item) for item in orders.list_order_items(db, user_id, order.id)],
        evidence=[EvidenceOut.model_validate(e) for e in orders.list_evidence(db, user_id, order.id)],
    )


@router.post("/orders", status_code=201, response_model=OrderOut)
def create_order(body: OrderCreate, user: MedicalUser, db: DbSession, today: Today) -> OrderOut:
    order = orders.create_order(db, user.id, body.text, body.order_date or today, today)
    return _order_out(db, user.id, order)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(user: MedicalUser, db: DbSession) -> list[OrderOut]:
    return [_order_out(db, user.id, order) for order in orders.list_orders(db, user.id)]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, user: MedicalUser, db: DbSession) -> OrderOut:
    return _order_out(db, user.id, orders.get_order(db, user.id, order_id))


@router.post("/orders/{order_id}/items", status_code=201, response_model=ItemOut)
def add_manual_item(order_id: uuid.UUID, body: ManualItemCreate, user: MedicalUser, db: DbSession) -> MedicalItem:
    return orders.add_manual_item(db, user.id, order_id, body.model_dump())


@router.post("/orders/{order_id}/evidence", status_code=201, response_model=EvidenceOut)
def upload_evidence(order_id: uuid.UUID, file: UploadFile, user: MedicalUser, db: DbSession) -> MedicalEvidence:
    content = file.file.read(orders.MAX_EVIDENCE_BYTES + 1)
    return orders.add_evidence(db, user.id, order_id, file.filename or "", content)


@router.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: uuid.UUID, user: MedicalUser, db: DbSession) -> Response:
    evidence = orders.get_evidence(db, user.id, evidence_id)
    extension = orders.EVIDENCE_EXTENSIONS[evidence.content_type]
    return Response(
        content=evidence.content,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="evidence-{evidence.id}{extension}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/items", response_model=list[ItemOut])
def list_items(
    user: MedicalUser, db: DbSession, status: ItemStatus | None = None, category: Category | None = None
) -> list[MedicalItem]:
    return items.list_items(db, user.id, status=status, category=category)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.get_item(db, user.id, item_id)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: uuid.UUID, body: ItemUpdate, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.update_item(db, user.id, item_id, body.model_dump(exclude_unset=True))


@router.post("/items/{item_id}/confirm", response_model=ItemOut)
def confirm_item(
    item_id: uuid.UUID, user: MedicalUser, db: DbSession, today: Today, body: ItemUpdate | None = None
) -> MedicalItem:
    changes = body.model_dump(exclude_unset=True) if body else {}
    return items.confirm_item(db, user.id, item_id, changes, today)


@router.post("/items/{item_id}/void", response_model=ItemOut)
def void_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession, body: ReasonBody | None = None) -> MedicalItem:
    return items.void_item(db, user.id, item_id, body.reason if body else None)


@router.post("/items/{item_id}/continue", response_model=ItemOut)
def continue_item(
    item_id: uuid.UUID, body: ContinueBody, user: MedicalUser, db: DbSession, today: Today
) -> MedicalItem:
    return items.continue_item(db, user.id, item_id, body.end_date, body.review_date, today)


@router.post("/items/{item_id}/propose-resolution", response_model=ItemOut)
def propose_resolution(item_id: uuid.UUID, body: ProposalBody, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.propose_resolution(db, user.id, item_id, body.reason, "user")


@router.post("/items/{item_id}/cancel-proposal", response_model=ItemOut)
def cancel_proposal(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> MedicalItem:
    return items.cancel_resolution_proposal(db, user.id, item_id)


@router.post("/items/{item_id}/resolve", response_model=ItemOut)
def resolve_item(item_id: uuid.UUID, user: MedicalUser, db: DbSession, body: ReasonBody | None = None) -> MedicalItem:
    return items.resolve_item(db, user.id, item_id, body.reason if body else None)


@router.get("/items/{item_id}/events", response_model=list[EventOut])
def list_events(item_id: uuid.UUID, user: MedicalUser, db: DbSession) -> list[MedicalItemEvent]:
    return items.list_events(db, user.id, item_id)


@router.get("/constraints", response_model=ConstraintsOut)
def get_constraints(
    user: MedicalUser, db: DbSession, today: Today, category: Category | None = None
) -> ConstraintsOut:
    constraints = items.get_current_constraints(db, user.id, today, category=category)
    return ConstraintsOut(
        constraints=[ConstraintOut.model_validate(c) for c in constraints], reminder=items.CONSTRAINT_REMINDER
    )


@router.get("/reviews", response_model=list[ItemOut])
def list_reviews(user: MedicalUser, db: DbSession, today: Today) -> list[MedicalItem]:
    return items.list_reviews(db, user.id, today)
```

`backend/app/main.py`：加 `from app.medical.router import router as medical_router` 与 `app.include_router(medical_router)`（放在 cycle_router 之后）。

- [ ] **Step 6: 运行确认通过**

Run: `uv run pytest tests/test_medical_api.py tests/test_route_guards.py -v`，然后 `uv run pytest -q -W error`
Expected: 全部通过、无警告。若上传接口报缺少 python-multipart，确认 Step 1 已执行。

- [ ] **Step 7: 提交**

```
git add backend/pyproject.toml backend/uv.lock backend/app backend/tests
git commit -m "feat(medical): add medical API with encrypted evidence files and access control"
```

---

### Task 5: 演示数据、交付文档与验收记录

**Files:**
- Create: `backend/app/medical/demo.py`
- Test: `backend/tests/test_medical_demo.py`, `backend/tests/test_medical_docs.py`
- Create: `docs/03-交付物/医嘱数据表与状态流转说明.md`、`提取规则说明.md`、`接口清单.md`、`样例与提取评测记录.md`、`验收记录.md`（**均不得出现代码、命令与代码块**）
- Modify: `README.md`（新增"医嘱模块演示"小节，可含命令；同步开头的完成情况与第 5 节表数量）、`docs/00-总览与串联.md`（步骤 03 状态改为"待验收"）

**Interfaces:**
- Consumes: `register_user`、`app.disclaimer.service.accept`、`DISCLAIMER_VERSION`、`orders.create_order`、`SAMPLE_ORDERS`、`get_sessionmaker`
- Produces: `app.medical.demo.DEMO_USERNAME = "demo_medical"`、`DEMO_PASSWORD = "demo-pass-123"`、`seed(db, today) -> bool`（新建返回 True，已存在返回 False）、`main()`（`uv run python -m app.medical.demo`）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_medical_demo.py`
```python
from datetime import date

from sqlalchemy import select

from app.auth.models import User
from app.db import get_sessionmaker
from app.medical import items, orders
from app.medical.demo import DEMO_USERNAME, seed

TODAY = date(2026, 9, 30)


def test_seed_creates_demo_user_with_three_pending_orders_once():
    db = get_sessionmaker()()
    try:
        assert seed(db, TODAY) is True
        assert seed(db, TODAY) is False
        user_id = db.scalar(select(User.id).where(User.username == DEMO_USERNAME))
        created = orders.list_orders(db, user_id)
        pending = items.list_items(db, user_id, status="pending_confirmation")
    finally:
        db.close()
    assert len(created) == 3
    assert len(pending) == 9
```

`backend/tests/test_medical_docs.py`
```python
from pathlib import Path

from app.medical.samples import SAMPLE_TITLES

DOCS = Path(__file__).resolve().parents[2] / "docs" / "03-交付物"


def test_evaluation_record_covers_every_sample():
    record = (DOCS / "样例与提取评测记录.md").read_text(encoding="utf-8")
    assert [title for title in SAMPLE_TITLES.values() if title not in record] == []


def test_delivery_docs_contain_no_code_blocks_or_inline_code():
    for doc in DOCS.glob("*.md"):
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_medical_demo.py tests/test_medical_docs.py -v`
Expected: FAIL（`No module named 'app.medical.demo'`；文档不存在）

- [ ] **Step 3: 实现演示数据**

`backend/app/medical/demo.py`
```python
"""演示数据：一个演示账号，录入三份样例医嘱，全部处于待确认状态，供体验确认、复核与解除流程。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import register_user
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.medical import orders
from app.medical.samples import SAMPLE_ORDERS

DEMO_USERNAME = "demo_medical"
DEMO_PASSWORD = "demo-pass-123"


def seed(db: Session, today: date) -> bool:
    if db.scalar(select(User).where(User.username == DEMO_USERNAME)) is not None:
        return False
    user = register_user(db, DEMO_USERNAME, DEMO_PASSWORD)
    disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
    for text in SAMPLE_ORDERS.values():
        orders.create_order(db, user.id, text, today, today)
    return True


def main() -> None:
    db = get_sessionmaker()()
    try:
        created = seed(db, date.today())
    finally:
        db.close()
    if created:
        print(f"已创建演示账号 {DEMO_USERNAME}（密码 {DEMO_PASSWORD}），录入了 3 份样例医嘱，条目均待确认。")
    else:
        print("演示账号已存在，未重复创建。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 写交付文档（全部中文，不含代码、命令与反引号）**

先阅读实际代码（`app/medical/` 全部文件、迁移 0007），文档必须描述代码实际行为。

1. `医嘱数据表与状态流转说明.md`：四张表逐表列出字段、含义、是否必填、是否加密、取值说明；说明哪些明文、哪些加密及原因；五种状态的中文名与含义；用自然语言与表格写出状态流转（每个动作的起始状态、结果状态、发起方、是否写审计）；说明硬约束的定义（生效中与待复核且生效日期不晚于今天）、到期判断（复查日当天起，或预计结束日期前 1 天起）、自动作废规则、每次请求前刷新状态。
2. `提取规则说明.md`：说明提取器是可替换接口、本步骤用规则提取器、步骤 07 替换为大模型；逐条写清切句、复查句、用药句、触发词与饮食方式词、类别判定顺序、时长与长期、把握程度三档的判定规则、缺失字段如何标记与处理、被忽略句子的四种原因；强调所有结果都要用户确认。
3. `接口清单.md`：全部 18 个接口：方法、路径、请求字段或查询参数、用途、主要错误码；本步骤新增错误码与中文含义；说明全部接口需要登录并确认免责声明、任何性别都可用；说明上传文件的类型与大小限制。
4. `样例与提取评测记录.md`：三份样例逐份列出（标题必须与样例标题完全一致）：医嘱原文、预期应提取的条目（人工判断）、提取器实际输出（与测试一致）、差异与错误。至少如实记录这些已知误差：慢病样例中"每日食盐不超过 5 克"这一限量没有单独提取，只保留在原文中；"每天快走 30 分钟"这一运动建议没有提取；"戒烟"被归入饮食禁忌；术后样例的"出院后""术后"起点被当作开具日期；两个复查时间取了较早的一个；短期样例的用药句与条件性复诊句被正确忽略。最后给出总体结论与对步骤 07 大模型提取的改进期望。
5. `验收记录.md`：把 `docs/03-医嘱模块.md` 的 8 条验收标准逐条列表：验收项、自动化测试（文件名与测试名）、手动核对方法（接口文档页面的操作）、结果、用户验收（留空）。

- [ ] **Step 5: README 与总览**

`README.md` 新增"医嘱模块演示"小节：说明医嘱功能对任何性别开放；给出 `uv run python -m app.medical.demo` 创建演示账号（用户名与密码）；给出在接口文档页面体验的顺序：登录、查看医嘱与待确认条目、修改并确认一条、查看当前约束、上传一张医嘱图片并下载核对、提出解除建议、确认解除、查看审计记录。同步更新 README 开头的完成情况与第 5 节"共几张表"的数量（本步骤新增 4 张，共 11 张）。

`docs/00-总览与串联.md`：步骤 03 状态从"未开始"改为"待验收"。

- [ ] **Step 6: 运行确认通过并试运行演示脚本**

Run: `uv run pytest -q -W error`，全部通过。
然后对开发库执行 `uv run alembic upgrade head` 与 `uv run python -m app.medical.demo`（两次，第二次应提示已存在）。

- [ ] **Step 7: 提交**

```
git add backend/app/medical/demo.py backend/tests/test_medical_demo.py backend/tests/test_medical_docs.py docs README.md
git commit -m "docs(medical): add demo data, step 03 delivery docs and acceptance record"
```
