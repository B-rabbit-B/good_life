"""照片评测脚本：用户在本机用自选的真实餐食照片与真实的看图模型跑一遍识别，统计正确率与常见错误，
据此确定“哪些情况需要提醒用户修正”（验收第 8 条）。结果写到 photo_eval_result.md。

运行方式（在 backend 目录）：uv run python -m app.photos.eval_check
密钥只从步骤 07 的同一份 llm_keys.local.env 读取（见 app.llm.live_check），按服务的顺序用第一家填了
<名>_VISION_MODEL 的服务。照片与标注放在 photo_eval 目录（labels.csv 的格式见 photo_eval.labels.example.csv）。
每张照片走与正式流程相同的步骤：prepare_image 处理图片 → 同一套提示词与格式重试（recognition_messages）→
parse_output → build_item 匹配营养库与换算克数；不连数据库，不保存任何记录。
结果只写菜名与克数，不写图片；整份文本输出前去掉全部密钥。照片目录与结果文件都不提交。
自动化测试用模拟模型与内存里生成的图片驱动本模块，绝不访问真实网络。
"""

import csv
import io
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.errors import AppError
from app.llm.adapters.base import LlmError
from app.llm.live_check import (
    DISPLAY_NAMES,
    KEYS_FILE,
    PROVIDERS,
    Factory,
    live_adapter,
    parse_env,
    resolve_provider,
    scrub,
)
from app.nutrition.catalog import EXACT_MATCH_TYPES, Catalog, load_catalog
from app.photos.images import prepare_image
from app.photos.matching import REVIEW_CONFIDENCE, build_item
from app.photos.recognition import RecognitionFormatError, parse_output
from app.photos.service import RECOGNITION_MAX_TOKENS, recognition_messages

BACKEND_DIR = Path(__file__).resolve().parents[2]
EVAL_DIR = BACKEND_DIR / "photo_eval"
LABELS_NAME = "labels.csv"
EXAMPLE_NAME = "photo_eval.labels.example.csv"
RESULT_FILE = BACKEND_DIR / "photo_eval_result.md"

COLUMNS = ("文件名", "真实菜品", "真实克数", "是否食物")
SEPARATOR = "、"
MIN_PHOTOS = 20  # 验收第 8 条：至少二十张
GRAMS_TOLERANCE = 0.5  # 克数与真实克数相差超过 50% 算偏差大
BANDS = ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))  # 最后一段包含 1.0
TARGET_ACCURACY = 0.8  # 建议阈值：从这个把握程度起，每一段的正确率都不低于 80%

STATUS_NAMES = {
    "ok": "识别出菜品",
    "not_food": "判为不是食物",
    "unclear": "判为看不清",
    "format_failed": "两次格式都不对",
    "skipped": "未评测",
    "error": "调用出错",
}
COUNTED = ("ok", "not_food", "unclear", "format_failed")  # 计入统计的状态；未评测与调用出错不计入
NONFOOD_JUDGEMENTS = {  # 非食物图片的逐张判断
    "not_food": "正确",
    "unclear": "正确（判为看不清，同样会拒绝）",
    "ok": "错误：非食物图片被误判为食物",
    "format_failed": "无法判断：两次格式都不对",
}

Progress = Callable[[str], None]


# ---------- 标注与模型 ----------


@dataclass(frozen=True)
class Label:
    file_name: str
    is_food: bool
    dishes: tuple[str, ...]
    grams: tuple[float, ...] | None  # 与 dishes 一一对应；没填为 None


@dataclass(frozen=True)
class VisionChoice:
    provider: str  # 服务的显示名
    kind: str
    base_url: str
    api_key: str = field(repr=False)
    model_id: str

    @property
    def label(self) -> str:
        return f"{self.provider}（{self.model_id}）"


def pick_vision_model(config: dict[str, str]) -> VisionChoice | None:
    """按服务的顺序，取第一家密钥、配置都没问题且填了 <名>_VISION_MODEL 的服务。"""
    for name in PROVIDERS:
        api_key = config.get(f"{name}_API_KEY", "").strip()
        model_id = config.get(f"{name}_VISION_MODEL", "").strip()
        if not api_key or not model_id:
            continue
        resolved = resolve_provider(name, config)
        if isinstance(resolved, str):  # 配置有误的服务不用，步骤 07 的实测会指出原因
            continue
        return VisionChoice(DISPLAY_NAMES[name], resolved[0], resolved[1], api_key, model_id)
    return None


def _split(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split(SEPARATOR) if part.strip()]


def _grams(parts: list[str]) -> tuple[float, ...] | None:
    try:
        values = tuple(float(part) for part in parts)
    except ValueError:
        return None
    return values if all(0 < value < float("inf") for value in values) else None


def read_labels(path: Path) -> tuple[list[Label], list[str]]:
    """读取标注文件（UTF-8，可带 BOM；# 开头的行是注释）。返回（有效的标注，每条问题一句中文说明）。"""
    reader = csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    labels: list[Label] = []
    problems: list[str] = []
    header: dict[str, int] | None = None
    seen: set[str] = set()
    for row in reader:
        line = reader.line_num
        if not row or not "".join(row).strip() or row[0].strip().startswith("#"):
            continue
        cells = [cell.strip() for cell in row]
        if header is None:
            header = {name: index for index, name in enumerate(cells)}
            missing = [name for name in COLUMNS if name not in header]
            if missing:
                return [], [f"第 {line} 行的表头缺少：{'、'.join(missing)}。表头应为：{'、'.join(COLUMNS)}"]
            continue

        def cell(name: str) -> str:
            index = header[name]
            return cells[index] if index < len(cells) else ""

        name, kind = cell("文件名"), cell("是否食物")
        dishes, grams_parts = _split(cell("真实菜品")), _split(cell("真实克数"))
        problem = None
        if not name:
            problem = "没有文件名"
        elif Path(name).name != name or name in (".", ".."):
            problem = f"文件名“{name}”不能带目录，照片要直接放在 photo_eval 目录里"
        elif name in seen:
            problem = f"文件名“{name}”重复了"
        elif kind not in ("是", "否"):
            problem = f"是否食物只能填“是”或“否”，现在是“{kind}”"
        elif kind == "是" and not dishes:
            problem = "是食物的照片要填真实菜品（多个菜品用顿号分隔）"
        elif any("，" in dish or "," in dish for dish in dishes):
            problem = "真实菜品里有逗号；多个菜品要用顿号（、）分隔，例如 番茄炒蛋、米饭"
        elif kind == "是" and grams_parts and (len(grams_parts) != len(dishes) or _grams(grams_parts) is None):
            problem = "真实克数要与菜品一一对应、用顿号分隔，每个都是大于 0 的数字；不知道克数就整格留空"
        if problem:
            problems.append(f"第 {line} 行：{problem}")
            continue
        seen.add(name)
        if kind == "是":
            labels.append(Label(name, True, tuple(dishes), _grams(grams_parts) if grams_parts else None))
        else:
            labels.append(Label(name, False, (), None))
    if header is None:
        problems.append(f"标注文件是空的。表头应为：{'、'.join(COLUMNS)}")
    return labels, problems


# ---------- 识别与判定 ----------


@dataclass
class ImageResult:
    label: Label
    status: str  # STATUS_NAMES 的键
    items: list[dict[str, Any]] = field(default_factory=list)  # build_item 的结果
    retried: bool = False
    seconds: float | None = None
    note: str = ""  # 未评测或出错的原因（已去掉密钥）


def recognize_image(adapter, model_id: str, content: bytes, catalog: Catalog) -> tuple[str, list[dict], bool]:
    """与正式流程相同：处理图片，同一套提示词，格式不对用同一张图片重试一次。返回（状态，识别项，是否重试过）。
    适配器错误（LlmError）与图片错误（AppError）原样抛出，由调用方记录。"""
    jpeg = prepare_image(content).data
    output, retried = None, False
    for retry in (False, True):
        retried = retry
        result = adapter.chat(model_id, recognition_messages(jpeg, retry=retry), max_tokens=RECOGNITION_MAX_TOKENS)
        try:
            output = parse_output(result.text)
            break
        except RecognitionFormatError:
            continue
    if output is None:
        return "format_failed", [], retried
    if output.status == "not_food":
        return "not_food", [], retried
    if output.status == "unclear" or not output.items:
        return "unclear", [], retried
    items = [build_item(item.name, item.portion_text, None, None, item.confidence,
                        catalog=catalog, grams_estimate=item.grams_estimate) for item in output.items]
    return "ok", items, retried


@dataclass
class Judgement:
    correct: list[bool]  # 与识别项一一对应
    hits: list[tuple[int, int]]  # （识别项序号，真实菜品序号）
    missed: int
    misidentified: int
    extra: int


def _truth_food_id(name: str, catalog: Catalog) -> str | None:
    hits = catalog.search(name)
    return hits[0].food.id if hits and hits[0].match in EXACT_MATCH_TYPES else None


def judge(label: Label, items: list[dict[str, Any]], catalog: Catalog | None = None) -> Judgement:
    """按真实菜品的顺序，为每道菜找第一个还没配上的识别项：同一食物编号或同名（菜名或匹配到的食物名）即算命中。
    没配上的真实菜品与没配上的识别项两两相抵算“认错”，余下的真实菜品算“漏识”，余下的识别项算“多识”。"""
    catalog = catalog or load_catalog()
    used: set[int] = set()
    hits: list[tuple[int, int]] = []
    for truth_index, truth in enumerate(label.dishes):
        food_id = _truth_food_id(truth, catalog)
        for item_index, item in enumerate(items):
            if item_index in used:
                continue
            same_food = food_id is not None and item["food_id"] == food_id
            if same_food or truth in (item["name"], item["food_name"]):
                used.add(item_index)
                hits.append((item_index, truth_index))
                break
    unmatched_truth = len(label.dishes) - len(hits)
    unmatched_items = len(items) - len(hits)
    misidentified = min(unmatched_truth, unmatched_items)
    return Judgement(
        correct=[index in used for index in range(len(items))],
        hits=hits,
        missed=unmatched_truth - misidentified,
        misidentified=misidentified,
        extra=unmatched_items - misidentified,
    )


# ---------- 统计 ----------


@dataclass
class Summary:
    images: int = 0
    excluded: int = 0
    food_images: int = 0
    food_rejected: int = 0
    nonfood_images: int = 0
    nonfood_correct: int = 0
    nonfood_unclear: int = 0
    nonfood_as_food: int = 0
    nonfood_format_failed: int = 0
    retried: int = 0
    format_failed: int = 0
    truth_dishes: int = 0
    recognized: int = 0
    hits: int = 0
    missed: int = 0
    misidentified: int = 0
    extra: int = 0
    unmatched: int = 0
    grams_compared: int = 0
    grams_off: int = 0
    low_conf_correct: int = 0
    high_conf_wrong: int = 0
    wrong_flagged: int = 0
    correct_flagged: int = 0
    bands: list[tuple[float, float, int, int]] = field(default_factory=list)  # （下限，上限，菜品数，正确数）


def _band_index(confidence: float) -> int:
    for index, (low, high) in enumerate(BANDS):
        if low <= confidence < high:
            return index
    return len(BANDS) - 1


def summarize(results: list[ImageResult], catalog: Catalog | None = None) -> Summary:
    catalog = catalog or load_catalog()
    s = Summary(images=len(results))
    band_counts = [[0, 0] for _ in BANDS]
    for result in results:
        if result.status not in COUNTED:
            s.excluded += 1
            continue
        s.retried += result.retried
        s.format_failed += result.status == "format_failed"
        if not result.label.is_food:
            s.nonfood_images += 1
            s.nonfood_correct += result.status == "not_food"
            s.nonfood_unclear += result.status == "unclear"
            s.nonfood_as_food += result.status == "ok"
            s.nonfood_format_failed += result.status == "format_failed"
            continue
        s.food_images += 1
        s.food_rejected += result.status != "ok"
        judged = judge(result.label, result.items, catalog)
        s.truth_dishes += len(result.label.dishes)
        s.recognized += len(result.items)
        s.hits += len(judged.hits)
        s.missed += judged.missed
        s.misidentified += judged.misidentified
        s.extra += judged.extra
        for item, correct in zip(result.items, judged.correct, strict=True):
            s.unmatched += item["status"] != "matched"
            low = item["confidence"] < REVIEW_CONFIDENCE
            s.low_conf_correct += low and correct
            s.high_conf_wrong += not low and not correct
            flagged = bool(item["review_reasons"])
            s.wrong_flagged += flagged and not correct
            s.correct_flagged += flagged and correct
            band = band_counts[_band_index(item["confidence"])]
            band[0] += 1
            band[1] += correct
        if result.label.grams is not None:
            for item_index, truth_index in judged.hits:
                truth = result.label.grams[truth_index]
                s.grams_compared += 1
                s.grams_off += abs(result.items[item_index]["grams"] - truth) / truth > GRAMS_TOLERANCE
    s.bands = [(low, high, total, correct) for (low, high), (total, correct) in zip(BANDS, band_counts, strict=True)]
    return s


def _num(value: float) -> str:
    return f"{value:g}"


def suggest_threshold(bands: list[tuple[float, float, int, int]]) -> tuple[float | None, str]:
    """从把握程度最高的一段往下看（没有样本的段跳过），只要这一段的正确率不低于 80% 就继续往下；
    建议阈值是最后一个达标段的下限：低于它的识别项建议提醒修正。"""
    threshold = None
    for low, _high, total, correct in reversed(bands):
        if total == 0:
            continue
        if correct / total < TARGET_ACCURACY:
            break
        threshold = low
    if all(total == 0 for *_rest, total, _correct in bands):
        return None, "没有识别出的菜品，无法给出建议。"
    goal = f"{TARGET_ACCURACY:.0%}"
    if threshold is None:
        return None, (f"把握程度最高的一段正确率也没有达到 {goal}，把握程度不能用来区分对错："
                      "建议对所有菜品都提醒修正，或换一个看图模型再评测一次。")
    if threshold == 0.0:
        return 0.0, (f"每一段的正确率都达到了 {goal}，把握程度低的也大多是对的："
                     f"可以保留当前阈值 {_num(REVIEW_CONFIDENCE)}，或适当调低。")
    return threshold, (f"把握程度不低于 {_num(threshold)} 的各段正确率都达到了 {goal}，更低的一段没有达到："
                       f"建议把“把握程度低”的提醒阈值设为 {_num(threshold)}。")


# ---------- 运行 ----------


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, LlmError):
        text = exc.message.rstrip("。")
        return f"{exc.code}：{text}（原始信息：{exc.detail}）" if exc.detail else f"{exc.code}：{text}"
    if isinstance(exc, AppError):
        return f"{exc.code}：{exc.message}"
    return f"脚本内部出错：{type(exc).__name__}"  # 只记类名，不带异常文字，避免带出密钥


def run_eval(labels: list[Label], eval_dir: Path, choice: VisionChoice, factory: Factory, *,
             progress: Progress, results: list[ImageResult], secrets: list[str]) -> list[ImageResult]:
    """逐张评测；每完成一张就追加到 results（中途被打断时，已完成的仍在里面），并报一行进度。"""
    catalog = load_catalog()
    total = len(labels)
    for number, label in enumerate(labels, start=1):
        path = eval_dir / label.file_name
        if not path.is_file():
            result = ImageResult(label, "skipped", note="找不到图片文件")
        else:
            start = time.perf_counter()
            try:
                adapter = factory(choice.kind, choice.base_url, choice.api_key)
                status, items, retried = recognize_image(adapter, choice.model_id, path.read_bytes(), catalog)
                result = ImageResult(label, status, items, retried, time.perf_counter() - start)
            except AppError as exc:  # 图片本身的问题（格式、大小、损坏）
                result = ImageResult(label, "skipped", note=scrub(_describe_error(exc), secrets))
            except Exception as exc:  # 调用出错不能中断整个评测
                result = ImageResult(label, "error", seconds=time.perf_counter() - start,
                                     note=scrub(_describe_error(exc), secrets))
        results.append(result)
        count = f"，识别出 {len(result.items)} 个菜品" if result.status == "ok" else ""
        seconds = "" if result.seconds is None else f"，{result.seconds:.1f} 秒"
        progress(scrub(f"  第 {number}/{total} 张 {label.file_name}：{STATUS_NAMES[result.status]}{count}{seconds}",
                       secrets))
    return results


# ---------- 输出 ----------


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "｜")


def _percent(part: int, whole: int) -> str:
    return "无" if whole == 0 else f"{part / whole:.1%}"


def _truth_text(label: Label) -> str:
    if not label.is_food:
        return ""
    if label.grams is None:
        return SEPARATOR.join(label.dishes)
    return SEPARATOR.join(f"{dish} {_num(grams)} 克" for dish, grams in zip(label.dishes, label.grams, strict=True))


def _items_text(items: list[dict[str, Any]]) -> str:
    return SEPARATOR.join(f"{item['name']} {_num(item['grams'])} 克" for item in items)


def _judgement_text(result: ImageResult, catalog: Catalog) -> str:
    if result.status not in COUNTED:
        return result.note
    if not result.label.is_food:
        return NONFOOD_JUDGEMENTS[result.status]
    judged = judge(result.label, result.items, catalog)
    return f"命中 {len(judged.hits)}，认错 {judged.misidentified}，多识 {judged.extra}，漏识 {judged.missed}"


def render_markdown(results: list[ImageResult], problems: list[str], choice: VisionChoice, today: date,
                    secrets: list[str], *, interrupted: bool = False) -> str:
    """生成评测结果；只写菜名与克数，不写图片。整份文本输出前按全部密钥去掉原文。"""
    catalog = load_catalog()
    s = summarize(results, catalog)
    lines = ["# 照片评测结果", "", f"运行日期：{today.isoformat()}", "", f"看图模型：{choice.label}", "",
             "本文件不含任何密钥，也不含图片内容，只有菜名与克数。", ""]
    if interrupted:
        lines += ["注意：本次运行中途被中断，下面只有中断之前已经完成的照片，请重新完整运行一次。", ""]
    if s.images - s.excluded < MIN_PHOTOS:
        lines += [f"注意：计入统计的照片少于二十张（本次 {s.images - s.excluded} 张），验收第 8 条要求至少二十张。", ""]

    lines += ["## 总体", "",
              f"- 照片 {s.images} 张：食物 {s.food_images} 张，非食物 {s.nonfood_images} 张；"
              f"不计入统计：{s.excluded} 张（未评测或调用出错，原因见逐张结果）",
              f"- 标注有误、没有评测：{len(problems)} 行",
              f"- 菜品级召回率：{_percent(s.hits, s.truth_dishes)}（命中 {s.hits} 道，真实菜品共 {s.truth_dishes} 道）",
              f"- 菜品级精确率：{_percent(s.hits, s.recognized)}（命中 {s.hits} 个，识别出的菜品共 {s.recognized} 个）",
              f"- 非食物图片 {s.nonfood_images} 张：判为不是食物 {s.nonfood_correct} 张，"
              f"判为看不清 {s.nonfood_unclear} 张，误判为食物 {s.nonfood_as_food} 张，"
              f"两次格式都不对 {s.nonfood_format_failed} 张",
              f"- 食物图片被判为不是食物、看不清或两次格式都不对：{s.food_rejected} 张",
              f"- 用了格式重试：{s.retried} 张；两次格式都不对：{s.format_failed} 张",
              "",
              "命中的含义：识别项与某道真实菜品是营养库里的同一个食物，或菜名（或匹配到的食物名）与真实菜品同名。"
              "召回率是命中数除以真实菜品数，精确率是命中数除以识别出的菜品数，都只算食物照片。", ""]

    lines += ["## 错误类型", "", "| 错误类型 | 数量 | 含义 |", "|---|---|---|",
              f"| 漏识 | {s.missed} | 真实有、没有识别出来的菜品（含整张被判为不是食物或看不清的） |",
              f"| 多识 | {s.extra} | 识别出来、但图里没有的菜品 |",
              f"| 认错 | {s.misidentified} | 识别出了一道菜、但认成了别的菜（没命中的真实菜品与没命中的识别项两两相抵） |",
              f"| 匹配不上 | {s.unmatched} | 识别出的菜名在营养库里找不到对应食物，标为待确认 |",
              f"| 克数偏差超过 50% | {s.grams_off} | 命中且填了真实克数的菜品里，换算出的克数与真实克数相差超过一半"
              f"（共比较 {s.grams_compared} 个） |",
              f"| 把握程度低但其实正确 | {s.low_conf_correct} | 把握程度低于 {_num(REVIEW_CONFIDENCE)}、但命中了 |",
              f"| 把握程度高但其实错误 | {s.high_conf_wrong} | 把握程度不低于 {_num(REVIEW_CONFIDENCE)}、但没有命中 |",
              ""]

    lines += ["## 按把握程度分段的正确率", "", "| 把握程度 | 识别出的菜品 | 正确 | 正确率 |", "|---|---|---|---|"]
    for low, high, total, correct in reversed(s.bands):
        lines.append(f"| {low:.1f} 至 {high:.1f} | {total} | {correct} | {_percent(correct, total)} |")
    lines += ["", "每段包含下限、不包含上限，最高一段包含 1.0。只算食物照片里识别出的菜品。", ""]

    threshold, advice = suggest_threshold(s.bands)
    wrong = s.recognized - s.hits
    lines += ["## 提醒修正的建议", "",
              f"- 当前阈值：{_num(REVIEW_CONFIDENCE)}（把握程度低于它就提醒修正）",
              f"- 建议阈值：{'无' if threshold is None else _num(threshold)}。{advice}",
              f"- 识别错的 {wrong} 个菜品里，有 {s.wrong_flagged} 个会被现有规则提醒修正"
              "（把握程度低、待确认、克数超出范围、克数只来自估算，任一条即提醒）；"
              f"识别对的 {s.hits} 个菜品里，有 {s.correct_flagged} 个也被提醒了。",
              "",
              "分段样本很少时（例如一段不到 5 个）建议仅供参考，多拍几张再评。", ""]

    lines += ["## 逐张结果", "", "| 图片 | 是否食物 | 真实菜品 | 识别状态 | 识别结果 | 判定 |", "|---|---|---|---|---|---|"]
    for result in results:
        label = result.label
        items = _items_text(result.items)
        lines.append(f"| {_cell(label.file_name)} | {'是' if label.is_food else '否'} | {_cell(_truth_text(label))} | "
                     f"{STATUS_NAMES[result.status]} | {_cell(items)} | {_cell(_judgement_text(result, catalog))} |")
    lines.append("")

    if problems:
        lines += ["## 标注问题", "", "下面这些行没有评测，请改好标注文件后重新运行：", ""]
        lines += [f"- {problem}" for problem in problems]
        lines.append("")
    return scrub("\n".join(lines), secrets)


def main(env_path: Path = KEYS_FILE, eval_dir: Path = EVAL_DIR, result_path: Path = RESULT_FILE,
         factory: Factory = live_adapter, today: date | None = None, progress: Progress = print) -> int:
    if not env_path.exists():
        print(f"没有找到 {env_path.name}。请先按步骤 07 的做法准备好它（复制 llm_keys.local.env.example，"
              "填入你自己的密钥和看图模型名），再运行本脚本（这个文件不要提交，也不要发给任何人）。")
        return 1
    try:
        text = env_path.read_text(encoding="utf-8-sig")  # 记事本另存的 UTF-8 文件开头可能带 BOM
    except UnicodeDecodeError:
        print(f"{env_path.name} 不是 UTF-8 编码，无法读取。请用文本编辑器打开它，另存为 UTF-8 编码后再运行。")
        return 1
    config = parse_env(text)
    secrets = [value for name, value in config.items() if name.endswith("_API_KEY") and value]
    choice = pick_vision_model(config)
    if choice is None:
        print(f"{env_path.name} 里没有哪一家服务同时填了密钥和看图模型名（<名>_VISION_MODEL，例如 QWEN_VISION_MODEL），"
              "无法评测。填好一家再运行。")
        return 1
    labels_path = eval_dir / LABELS_NAME
    if not labels_path.exists():
        print(f"没有找到 {eval_dir.name}/{LABELS_NAME}。请在 backend 目录里建一个 {eval_dir.name} 目录，把自选的照片放进去，"
              f"再把 {EXAMPLE_NAME} 复制到 {eval_dir.name}/{LABELS_NAME}，按里面的格式为每张照片写一行标注后再运行。")
        return 1
    try:
        labels, problems = read_labels(labels_path)
    except UnicodeDecodeError:
        print(f"{LABELS_NAME} 不是 UTF-8 编码，无法读取。用表格软件编辑时，请另存为“CSV UTF-8”格式后再运行。")
        return 1
    if not labels:
        print("标注文件里没有可以评测的行：")
        for problem in problems:
            print(f"  {problem}")
        return 1

    today = today or date.today()
    progress(f"开始评测：{len(labels)} 张照片，看图模型 {choice.label}")
    results: list[ImageResult] = []
    code, finished = 0, False
    try:
        run_eval(labels, eval_dir, choice, factory, progress=progress, results=results, secrets=secrets)
        finished = True
    except KeyboardInterrupt:
        print("已中断：中断之前已经完成的照片会写入结果文件。")
        code = 130
    finally:
        # 不论正常结束还是中途被打断，都把已完成的照片写下来；整份文本在输出前会再去掉一遍全部密钥
        report = render_markdown(results, problems, choice, today, secrets, interrupted=not finished)
        result_path.write_text(report, encoding="utf-8")
        if finished:
            print(report)
        print(f"结果已写入 {result_path.name}（不含密钥与图片，但也请先看一遍再决定是否分享）。")
    return code


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # 终端编码不认识某个字符时不要中断
    sys.exit(main())
