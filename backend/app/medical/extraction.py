"""医嘱提取。

提取器只产出"候选条目"，全部是待确认状态，必须由用户逐条确认后才生效。
步骤 03 使用基于关键词与日期规则的提取器；步骤 07 接入大模型后，
实现同一个 Extractor 接口的模型提取器，并在 get_extractor() 中切换即可。

几条容易出错的规则（都是为了不让提取器给出"看起来很确定"的错误约束）：
- 含复查词的句子按逗号拆开：含复查词的分句只用来取复查日期，其余分句当作独立句子照常提取，
  避免"避免提重物，一周后复查"里的限制被悄悄丢掉。
- 分句以"如、若、如果、一旦"开头或含"必要时"，是条件性提醒，不取日期；
  任何句子（不只是含复查词的）第一个分句是条件时，整句记为条件性提醒。
  条件分句出现在后面时，只忽略它自己，不影响前面的分句。
- 持续时间只在含忌口触发词、饮食方式词或运动词的分句里找，不读"患病10年""一日三餐"这类时间。
- 剂量、次数（以数字开头，或"数字加次、片、粒、袋、支、克"）不算涉及对象，"薯片""巧克力"这类食物名照常保留；
  用药句没有涉及对象时整句忽略。
- 句首标签只认固定的几种（诊断、医嘱等），"忌口：辛辣"里的"忌口"不是标签。
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
DURATION_RE = re.compile(
    _NUM + r"\s*(个月|个星期|星期|周|天|日|月|年)"
    r"(?!\s*" + _NUM + r"?\s*[次餐顿片粒])"  # "一日三餐""每天2次"里的"一日""每天"不是持续时间
)
EXPLICIT_DATE_RE = re.compile(
    r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*[日号]?"
    r"|(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
)
SENTENCE_SPLIT_RE = re.compile(r"[。；;！!？?\n]+|(?<![\d.])\d{1,2}[.、．](?!\d)|[（(]\d{1,2}[)）]")
LABEL_RE = re.compile(r"^(?:出院诊断|出院医嘱|饮食建议|注意事项|诊断|医嘱|建议|处理|嘱咐|饮食)[：:]")
PART_SPLIT_RE = re.compile(r"以及|[、和及与或/]")
CLAUSE_END_RE = re.compile(r"[，,]")
DOSAGE_SUBJECT_RE = re.compile(r"^\d|(?:\d|[一二两三四五六七八九十半]+)\s*(?:次|片|粒|袋|支|毫克|克)")
_CONDITION_STARTS = tuple(word for word in CONDITIONAL_WORDS if word != "必要时")
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
    return part.strip(" 　：:的等内")


def _avoid_subjects(sentence: str) -> list[str]:
    subjects: list[str] = []
    matches = list(_TRIGGER_RE.finditer(sentence))
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(sentence)
        segment = CLAUSE_END_RE.split(sentence[match.end():stop])[0]
        for part in PART_SPLIT_RE.split(segment):
            cleaned = _clean_subject(part)
            if cleaned and not DOSAGE_SUBJECT_RE.search(cleaned) and cleaned not in subjects:
                subjects.append(cleaned)
    return subjects


def _clauses(sentence: str) -> list[str]:
    return [clause.strip() for clause in CLAUSE_END_RE.split(sentence) if clause.strip()]


def _is_conditional(clause: str) -> bool:
    """条件性提醒：分句以"如、若、如果、一旦"开头，或含"必要时"。"""
    if "必要时" in clause:
        return True
    return clause.startswith(_CONDITION_STARTS) and not clause.startswith("如期")


def _requirement_duration(sentence: str) -> tuple[int, str] | None:
    """只在含忌口触发词、饮食方式词或运动词的分句里找持续时间，取句中第一个。"""
    for clause in _clauses(sentence):
        if _TRIGGER_RE.search(clause) or _STYLE_RE.search(clause) or any(w in clause for w in EXERCISE_WORDS):
            duration = _first_duration(EXPLICIT_DATE_RE.sub(" ", clause))
            if duration:
                return duration
    return None


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
            clauses = _clauses(sentence)
            if clauses and _is_conditional(clauses[0]):
                ignored.append(IgnoredSentence(sentence, REASON_CONDITIONAL))
                continue
            if not any(word in sentence for word in REVIEW_WORDS):
                self._add_sentence(sentence, order_date, items, ignored)
                continue
            for clause in clauses:
                if not any(word in clause for word in REVIEW_WORDS):
                    self._add_sentence(clause, order_date, items, ignored)
                elif _is_conditional(clause):
                    ignored.append(IgnoredSentence(clause, REASON_CONDITIONAL))
                else:
                    found = self._review_dates(clause, order_date)
                    if found:
                        reviews.extend(found)
                    else:
                        ignored.append(IgnoredSentence(clause, REASON_REVIEW_WITHOUT_DATE))

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

    def _add_sentence(
        self, sentence: str, order_date: date, items: list[ExtractedItem], ignored: list[IgnoredSentence]
    ) -> None:
        new_items, skipped = self._sentence_items(sentence, order_date)
        items.extend(new_items)
        if skipped is not None:
            ignored.append(skipped)

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
            subjects = _avoid_subjects(sentence) or _styles(sentence)
            if not subjects:
                return [], IgnoredSentence(sentence, REASON_MEDICATION)
            candidates.append(("medication_diet", subjects, [NOTE_MEDICATION]))
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
        duration = _requirement_duration(sentence)
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
