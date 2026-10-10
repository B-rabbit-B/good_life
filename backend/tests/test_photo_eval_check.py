"""照片评测脚本：用 MockTransport 驱动的模拟看图模型与内存里生成的图片跑完整个评测，
绝不访问真实网络，也不读取真实的密钥文件与评测照片。"""

import base64
import io
import json
import tempfile
from datetime import date
from inspect import signature
from pathlib import Path

import httpx2
from PIL import Image

from app.llm.adapters import make_adapter
from app.photos import eval_check
from app.photos.eval_check import Label, pick_vision_model, read_labels, suggest_threshold
from app.photos.images import prepare_image
from app.photos.matching import REVIEW_CONFIDENCE
from app.photos.recognition import parse_output
from app.photos.service import RECOGNITION_MAX_TOKENS, recognition_messages

BACKEND = Path(__file__).resolve().parents[1]
QWEN_KEY = "sk-qwen-0123456789abcdef"
ZHIPU_KEY = "zhipu-secret-0123456789"
TODAY = date(2026, 10, 10)
HEADER = "文件名,真实菜品,真实克数,是否食物"


def _png(size: tuple[int, int], color=(200, 120, 40)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return out.getvalue()


def _answer(*items: tuple[str, str, float, float], status: str = "ok") -> str:
    return json.dumps({"status": status, "note": "",
                       "items": [{"name": n, "portion": p, "grams": g, "confidence": c} for n, p, g, c in items]},
                      ensure_ascii=False)


class FakeVision:
    """按收到的图片尺寸回答的模拟看图模型（处理后的图片不会放大，尺寸可以用来区分照片）。
    同一尺寸可以排好几次回答（用来测格式重试）；状态码不是 200 时返回带密钥的错误信息。"""

    def __init__(self, script: dict[tuple[int, int], list[tuple[int, str]]]):
        self.script = {size: list(replies) for size, replies in script.items()}
        self.requests: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        [message] = body["messages"]
        prompt = "".join(part["text"] for part in message["content"] if part["type"] == "text")
        [url] = [part["image_url"]["url"] for part in message["content"] if part["type"] == "image_url"]
        image = base64.b64decode(url.split(",", 1)[1])
        size = Image.open(io.BytesIO(image)).size
        self.requests.append({"model": body["model"], "max_tokens": body.get("max_tokens"), "prompt": prompt,
                              "image": image, "size": size, "body": body})
        status, text = self.script[size].pop(0)
        if status != 200:
            key = request.headers["authorization"].removeprefix("Bearer ")
            return httpx2.Response(status, json={"error": {"message": f"boom {key}", "type": "server_error"}})
        return httpx2.Response(200, json={"model": body["model"], "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                          "choices": [{"message": {"role": "assistant", "content": text},
                                                       "finish_reason": "stop"}]})


def _factory(model: FakeVision):
    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(model))

    return factory


# 一组完整的评测：每张图一种尺寸，模拟模型按尺寸回答
SIZES = {name: (100 + 10 * index, 80) for index, name in enumerate(
    ("a.png", "b.png", "c.png", "d.png", "e.png", "f.png", "g.png", "h.png"))}
LABELS = "\n".join([
    "# 评测用的标注（注释行会被跳过）",
    HEADER,
    "a.png,番茄炒蛋、米饭,300、250,是",
    "b.png,麻婆豆腐,,是",
    "c.png,米饭、番茄炒蛋,,是",
    "d.png,,,否",
    "e.png,,,否",
    "f.png,西红柿炒鸡蛋,,是",
    "g.png,清蒸鱼,,是",
    "missing.png,米饭,,是",
    "h.png,米饭,,也许",
    "",
])
SCRIPT = {
    SIZES["a.png"]: [(200, _answer(("番茄炒蛋", "", 250, 0.9), ("米饭", "", 100, 0.5)))],
    SIZES["b.png"]: [(200, _answer(("红烧肉", "", 300, 0.65), ("外星菜", "", 80, 0.3)))],
    SIZES["c.png"]: [(200, _answer(status="unclear"))],
    SIZES["d.png"]: [(200, _answer(status="not_food"))],
    SIZES["e.png"]: [(200, _answer(("米饭", "一碗", 150, 0.6)))],
    SIZES["f.png"]: [(200, "这是一盘番茄炒蛋。"), (200, _answer(("番茄炒蛋", "", 200, 0.7)))],
    SIZES["g.png"]: [(500, "")],
}


def _write_set(directory: Path, labels: str = LABELS) -> None:
    eval_dir = directory / "photo_eval"
    eval_dir.mkdir()
    (eval_dir / "labels.csv").write_text(labels, encoding="utf-8")
    for name, size in SIZES.items():
        (eval_dir / name).write_bytes(_png(size))


def _keys(directory: Path, text: str | None = None) -> Path:
    path = directory / "llm_keys.local.env"
    path.write_text(text if text is not None else f"QWEN_API_KEY={QWEN_KEY}\nQWEN_VISION_MODEL=qwen-vl-max\n",
                    encoding="utf-8")
    return path


def _run(script=SCRIPT, labels: str = LABELS) -> tuple[int, str, FakeVision, list[str]]:
    model = FakeVision(script)
    printed: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _write_set(directory, labels)
        result = directory / "photo_eval_result.md"
        code = eval_check.main(_keys(directory), directory / "photo_eval", result, _factory(model),
                               today=TODAY, progress=printed.append)
        written = result.read_text(encoding="utf-8") if result.exists() else ""
    return code, written, model, printed


# ---------- 完整运行 ----------


def test_full_run_counts_every_metric():
    code, report, model, _printed = _run()
    assert code == 0
    assert "运行日期：2026-10-10" in report and "通义千问（qwen-vl-max）" in report
    # 菜品级：a 两道全中；b 认错一道、多识一道；c 看不清，两道漏识；f 名字不同但同一食物，算命中；g 调用出错不计入
    assert "菜品级召回率：50.0%（命中 3 道，真实菜品共 6 道）" in report
    assert "菜品级精确率：60.0%（命中 3 个，识别出的菜品共 5 个）" in report
    for row in ("| 漏识 | 2 |", "| 多识 | 1 |", "| 认错 | 1 |", "| 匹配不上 | 1 |", "| 克数偏差超过 50% | 1 |",
                "| 把握程度低但其实正确 | 1 |", "| 把握程度高但其实错误 | 1 |"):
        assert row in report, row
    assert "非食物图片 2 张：判为不是食物 1 张，判为看不清 0 张，误判为食物 1 张，两次格式都不对 0 张" in report
    assert "错误：非食物图片被误判为食物" in report
    assert "食物图片被判为不是食物、看不清或两次格式都不对：1 张" in report
    assert "用了格式重试：1 张；两次格式都不对：0 张" in report
    assert "不计入统计：2 张" in report and "标注有误、没有评测：1 行" in report
    # 按把握程度分段：0.9 对、0.5 对、0.65 错、0.3 错、0.7 对
    for row in ("| 0.8 至 1.0 | 1 | 1 | 100.0% |", "| 0.6 至 0.8 | 2 | 1 | 50.0% |",
                "| 0.4 至 0.6 | 1 | 1 | 100.0% |", "| 0.0 至 0.4 | 1 | 0 | 0.0% |"):
        assert row in report, row
    assert "建议阈值：0.8" in report and f"当前阈值：{REVIEW_CONFIDENCE}" in report
    # 识别错的 2 个都至少有一条提醒原因（低把握或待确认或估算克数），识别对的 3 个里有提醒的也要报出
    assert "识别错的 2 个菜品里，有 2 个会被现有规则提醒修正" in report
    # 逐张：只写菜名与克数
    assert "| a.png | 是 | 番茄炒蛋 300 克、米饭 250 克 | 识别出菜品 | 番茄炒蛋 250 克、米饭 100 克 |" in report
    assert "| f.png | 是 | 西红柿炒鸡蛋 | 识别出菜品 | 番茄炒蛋 200 克 |" in report
    assert "| g.png | 是 | 清蒸鱼 | 调用出错 |" in report
    assert "| missing.png | 是 | 米饭 | 未评测 |" in report and "找不到图片文件" in report
    assert "第 11 行" in report and "是否食物" in report  # h.png 的标注有误，列在标注问题里
    assert "少于二十张" in report  # 验收第 8 条至少要二十张
    assert len(model.requests) == 8  # 7 张图片，f 重试一次；missing 与标注有误的不调用


def test_report_and_progress_contain_no_key_and_no_image_bytes():
    script = {**SCRIPT, SIZES["b.png"]: [(200, _answer((QWEN_KEY, "", 300, 0.9)))]}
    code, report, model, printed = _run(script)
    assert code == 0
    output = report + "\n".join(printed)
    assert QWEN_KEY not in output and "****" in report
    for request in model.requests:
        assert base64.b64encode(request["image"]).decode() not in output
        assert request["image"][:64].hex() not in output
    assert "data:image" not in output and "base64" not in output.lower()


def test_each_call_uses_the_real_flows_prompt_image_and_token_cap():
    code, _report, model, _printed = _run()
    assert code == 0
    retry_first, retry_second = [r for r in model.requests if r["size"] == SIZES["f.png"]]
    for request in model.requests:
        assert request["model"] == "qwen-vl-max" and request["max_tokens"] == RECOGNITION_MAX_TOKENS
    first = recognition_messages(retry_first["image"])[0]
    second = recognition_messages(retry_second["image"], retry=True)[0]
    assert retry_first["prompt"] == first.text and retry_second["prompt"] == second.text
    assert retry_first["image"] == retry_second["image"]  # 重试用同一张图片
    image = Image.open(io.BytesIO(retry_first["image"]))
    assert image.format == "JPEG" and len(image.getexif()) == 0


def test_progress_has_one_line_per_image():
    _code, _report, _model, printed = _run()
    lines = [line for line in printed if line.strip().startswith("第 ")]
    assert len(lines) == 8 and "a.png" in lines[0] and "识别出 2 个菜品" in lines[0]


def test_two_bad_formats_count_as_a_rejected_food_image():
    script = {**SCRIPT, SIZES["f.png"]: [(200, "不是 JSON"), (200, '{"status": "maybe"}')]}
    _code, report, _model, _printed = _run(script)
    assert "用了格式重试：1 张；两次格式都不对：1 张" in report
    assert "| f.png | 是 | 西红柿炒鸡蛋 | 两次格式都不对 |" in report
    assert "菜品级召回率：33.3%（命中 2 道，真实菜品共 6 道）" in report


# ---------- 统计规则 ----------


def test_suggest_threshold_from_bands():
    bands = [(0.0, 0.4, 4, 1), (0.4, 0.6, 5, 3), (0.6, 0.8, 5, 4), (0.8, 1.0, 10, 9)]
    assert suggest_threshold(bands)[0] == 0.6
    assert suggest_threshold([(0.0, 0.4, 2, 2), (0.4, 0.6, 0, 0), (0.6, 0.8, 3, 3), (0.8, 1.0, 5, 5)])[0] == 0.0
    threshold, text = suggest_threshold([(0.0, 0.4, 1, 0), (0.4, 0.6, 1, 0), (0.6, 0.8, 1, 1), (0.8, 1.0, 4, 2)])
    assert threshold is None and "所有菜品" in text
    threshold, text = suggest_threshold([(0.0, 0.4, 0, 0), (0.4, 0.6, 0, 0), (0.6, 0.8, 0, 0), (0.8, 1.0, 0, 0)])
    assert threshold is None and "没有" in text


def test_judge_pairs_by_food_or_name_and_splits_wrong_into_misidentified_and_extra():
    label = Label("x.png", True, ("西红柿炒鸡蛋", "米饭", "外星菜"), None)
    items = [eval_check.build_item(name, "", grams, None, 0.9) for name, grams in
             (("番茄炒蛋", 200), ("红烧肉", 200), ("外星菜", 100), ("清蒸鱼", 150))]
    judged = eval_check.judge(label, items)
    assert judged.correct == [True, False, True, False]  # 同一食物编号或同名都算命中
    assert (judged.missed, judged.misidentified, judged.extra) == (0, 1, 1)


# ---------- 标注文件与模型选择 ----------


def test_read_labels_validates_rows():
    text = "\n".join([
        HEADER,
        "1.jpg, 番茄炒蛋 、米饭 ,250、150,是",
        "2.jpg,,,否",
        "3.jpg,米饭,abc,是",
        "4.jpg,米饭、番茄炒蛋,200,是",
        "5.jpg,,,是",
        "../6.jpg,米饭,,是",
        "7.jpg,米饭,0,是",
        ",米饭,,是",
        "1.jpg,米饭,,是",
    ])
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "labels.csv"
        path.write_text(text, encoding="utf-8-sig")
        labels, problems = read_labels(path)
    assert labels == [Label("1.jpg", True, ("番茄炒蛋", "米饭"), (250.0, 150.0)), Label("2.jpg", False, (), None)]
    assert len(problems) == 7
    assert all(problem.startswith("第 ") for problem in problems)
    assert any("第 4 行" in p and "克数" in p for p in problems)
    assert any("第 10 行" in p and "重复" in p for p in problems)


def test_nonfood_counts_add_up_and_unclear_counts_as_correct():
    labels = "\n".join([HEADER, "c.png,,,否", "d.png,,,否", "e.png,,,否", ""])
    script = {
        SIZES["c.png"]: [(200, _answer(status="unclear"))],
        SIZES["d.png"]: [(200, _answer(status="not_food"))],
        SIZES["e.png"]: [(200, "不是 JSON"), (200, "还是不是")],
    }
    code, report, _model, _printed = _run(script, labels)
    assert code == 0
    assert "非食物图片 3 张：判为不是食物 1 张，判为看不清 1 张，误判为食物 0 张，两次格式都不对 1 张" in report
    assert "正确（判为看不清，同样会拒绝）" in report
    assert "无法判断：两次格式都不对" in report


def test_read_labels_rejects_commas_between_dishes():
    text = "\n".join([HEADER, "1.jpg,番茄炒蛋，米饭,,是", '2.jpg,"番茄炒蛋,米饭",,是', "3.jpg,番茄炒蛋、米饭,,是"])
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "labels.csv"
        path.write_text(text, encoding="utf-8")
        labels, problems = read_labels(path)
    assert labels == [Label("3.jpg", True, ("番茄炒蛋", "米饭"), None)]
    assert len(problems) == 2
    assert all("顿号" in problem for problem in problems)
    assert problems[0].startswith("第 2 行") and problems[1].startswith("第 3 行")


def test_read_labels_needs_the_four_columns():
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "labels.csv"
        path.write_text("name,dishes\n1.jpg,米饭\n", encoding="utf-8")
        labels, problems = read_labels(path)
    assert labels == [] and "文件名" in problems[0] and "是否食物" in problems[0]


def test_pick_vision_model_takes_the_first_provider_with_a_vision_model():
    config = {"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "qwen-plus",
              "ZHIPU_API_KEY": ZHIPU_KEY, "ZHIPU_VISION_MODEL": "glm-4v-plus",
              "CUSTOM_API_KEY": "x", "CUSTOM_VISION_MODEL": "m"}  # CUSTOM 没填类型，配置有误
    choice = pick_vision_model(config)
    assert (choice.provider, choice.model_id, choice.kind) == ("智谱", "glm-4v-plus", "openai_compatible")
    assert ZHIPU_KEY not in repr(choice)
    assert pick_vision_model({"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "qwen-plus"}) is None
    assert pick_vision_model({"QWEN_VISION_MODEL": "qwen-vl-max"}) is None


# ---------- main 的各种出口 ----------


def test_main_without_a_keys_file_explains_how_to_start(capsys):
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _write_set(directory)
        result = directory / "photo_eval_result.md"
        code = eval_check.main(directory / "llm_keys.local.env", directory / "photo_eval", result,
                               _factory(FakeVision({})))
        assert code == 1 and not result.exists()
    assert "llm_keys.local.env.example" in capsys.readouterr().out


def test_main_without_a_vision_model_explains(capsys):
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _write_set(directory)
        result = directory / "photo_eval_result.md"
        keys = _keys(directory, f"QWEN_API_KEY={QWEN_KEY}\nQWEN_CHAT_MODEL=qwen-plus\n")
        assert eval_check.main(keys, directory / "photo_eval", result, _factory(FakeVision({}))) == 1
        assert not result.exists()
    out = capsys.readouterr().out
    assert "VISION_MODEL" in out and QWEN_KEY not in out


def test_main_without_labels_explains_how_to_prepare_them(capsys):
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        result = directory / "photo_eval_result.md"
        assert eval_check.main(_keys(directory), directory / "photo_eval", result, _factory(FakeVision({}))) == 1
        assert not result.exists()
    out = capsys.readouterr().out
    assert "photo_eval.labels.example.csv" in out and "labels.csv" in out


def test_main_explains_labels_that_are_not_utf8(capsys):
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _write_set(directory)
        (directory / "photo_eval" / "labels.csv").write_bytes(f"{HEADER}\na.png,米饭,,是\n".encode("gbk"))
        result = directory / "photo_eval_result.md"
        assert eval_check.main(_keys(directory), directory / "photo_eval", result, _factory(FakeVision({}))) == 1
    captured = capsys.readouterr()
    assert "UTF-8" in captured.out and "Traceback" not in captured.out + captured.err


def test_main_writes_partial_results_when_interrupted():
    calls = {"count": 0}
    model = FakeVision(SCRIPT)

    def factory(kind, base_url, api_key):
        calls["count"] += 1
        if calls["count"] == 3:
            raise KeyboardInterrupt
        return _factory(model)(kind, base_url, api_key)

    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _write_set(directory)
        result = directory / "photo_eval_result.md"
        code = eval_check.main(_keys(directory), directory / "photo_eval", result, factory, today=TODAY,
                               progress=lambda _line: None)
        written = result.read_text(encoding="utf-8")
    assert code == 130
    assert "中途被中断" in written and "| a.png |" in written and "| c.png |" not in written
    assert QWEN_KEY not in written


def test_live_adapter_is_the_default_and_paths_point_into_backend():
    assert signature(eval_check.main).parameters["factory"].default is eval_check.live_adapter
    assert eval_check.EVAL_DIR == BACKEND / "photo_eval"
    assert eval_check.LABELS_NAME == "labels.csv"
    assert eval_check.RESULT_FILE == BACKEND / "photo_eval_result.md"


def test_the_script_builds_messages_with_the_real_flows_function():
    assert eval_check.recognition_messages is recognition_messages
    assert eval_check.parse_output is parse_output and eval_check.prepare_image is prepare_image


# ---------- 模板与忽略规则 ----------


def test_example_labels_file_has_the_header_and_three_rows():
    path = BACKEND / "photo_eval.labels.example.csv"
    text = path.read_text(encoding="utf-8")
    assert "photo_eval/labels.csv" in text
    labels, problems = read_labels(path)
    assert problems == [] and len(labels) == 3
    assert any(not label.is_food for label in labels) and any(label.grams for label in labels)


def test_eval_photos_and_result_are_git_ignored():
    entries = (BACKEND / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "photo_eval/" in entries and "photo_eval_result.md" in entries

