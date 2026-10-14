"""越权测试的登记表：接口描述里每个路径参数名都必须在这里登记，新接口才不会漏掉交叉用户测试。

- RESOURCE_PARAMS：路径参数名 → tests/full_user.py 的 fill_every_table 返回值里的键（两者同名），即“创建这种资源的那一步”；
  接口矩阵用 A 的这个编号、以 B 的令牌请求每个带它的接口与方法。
- NON_RESOURCE_PARAMS：不指向某个用户记录的路径参数，值是原因；
- NOT_FOUND_CODE：别人的资源与不存在的资源一样回的错误码；
- SAMPLE_BODIES、SAMPLE_UPLOADS：带资源参数且要请求体的接口各给一个合法的请求体，保证 B 的请求不会先因为请求体不合法得到 422；
- PUBLIC_GET_ROUTES：没有资源路径参数、内容与用户无关的 GET 接口，金丝雀扫描不扫它们，值是原因；
- path_params：从接口描述现算每个路径参数名出现在哪些路径。
"""

from datetime import date, timedelta

TODAY = date.today()

RESOURCE_PARAMS: dict[str, str] = {
    name: name
    for name in (
        "conversation_id", "entry_id", "evidence_id", "exercise_id", "grant_id", "item_id", "model_pk",
        "opening_id", "order_id", "period_id", "preference_id", "provider_id", "rec_id", "workout_id",
    )
}

NON_RESOURCE_PARAMS: dict[str, str] = {
    "food_id": "营养库的公共食物编号，所有用户看到的都一样，不属于任何用户",
    "log_date": "本人每日记录的日期键，查询一律加上当前用户；别人记过的日期由 test_day_logs_of_another_user_cannot_be_read_or_deleted 专门测",
    "purpose": "模型用途的枚举（对话、看图），分配记录一律按当前用户查；请求体里的模型编号由 test_body_ids_of_another_user_are_refused 测",
    "kind": "单独同意的类别枚举（经期、医嘱），同意记录一律按当前用户查；由 test_consent_and_account_routes_only_touch_the_caller 测",
}

# exercise_id 沿用 exercise_not_found：内置动作与自定义动作共用一个编号空间（ex: 与 custom: 前缀），
# 动作不存在一直回 exercise_not_found；别人的自定义动作必须与不存在的动作完全一致，才不暴露它是否存在。
NOT_FOUND_CODE: dict[str, str] = {name: "not_found" for name in RESOURCE_PARAMS} | {
    "exercise_id": "exercise_not_found",
}

_DAY = TODAY.isoformat()
_LATER = (TODAY + timedelta(days=30)).isoformat()

SAMPLE_BODIES: dict[tuple[str, str], dict | None] = {
    ("PATCH", "/api/cycle/periods/{period_id}"): {"end_date": _DAY},
    ("POST", "/api/medical/orders/{order_id}/items"): {"category": "diet_avoid", "content": "少油", "subjects": ["油"]},
    ("PATCH", "/api/medical/items/{item_id}"): {"content": "少油"},
    ("POST", "/api/medical/items/{item_id}/confirm"): None,
    ("POST", "/api/medical/items/{item_id}/void"): None,
    ("POST", "/api/medical/items/{item_id}/continue"): {"review_date": _LATER},
    ("POST", "/api/medical/items/{item_id}/propose-resolution"): {"reason": "医生复查后允许恢复"},
    ("POST", "/api/medical/items/{item_id}/resolve"): None,
    ("PATCH", "/api/nutrition/meals/{entry_id}"): {"note": "改个备注"},
    ("PUT", "/api/fitness/workouts/{workout_id}"): {
        "performed_on": _DAY, "cardio": [{"exercise_id": "ex:running", "duration_minutes": 10}]},
    ("PATCH", "/api/llm/providers/{provider_id}"): {"name": "改名的服务"},
    ("POST", "/api/llm/providers/{provider_id}/models"): {"model_id": "another-model"},
    ("PATCH", "/api/llm/models/{model_pk}"): {"vision": True},
    ("POST", "/api/llm/providers/{provider_id}/test"): {},
    ("POST", "/api/agent/conversations/{conversation_id}/messages"): {"text": "你好", "stream": False},
    ("PUT", "/api/photos/recognitions/{rec_id}/items"): {"items": [{"name": "米饭", "grams": 100}]},
    ("POST", "/api/photos/recognitions/{rec_id}/confirm"): {"eaten_on": _DAY, "meal_type": "lunch"},
}

# 上传接口（multipart）另行处理：给 httpx 的 files 参数。
SAMPLE_UPLOADS: dict[tuple[str, str], dict] = {
    ("POST", "/api/medical/orders/{order_id}/evidence"): {
        "file": ("evidence.pdf", b"%PDF-1.4\n" + b"0" * 64, "application/pdf")},
}

PUBLIC_GET_ROUTES: dict[str, str] = {
    "/api/health": "健康检查，固定内容",
    "/api/disclaimer": "免责声明正文与版本，人人相同（确认状态在 /api/disclaimer/status，会被扫描）",
    "/api/llm/presets": "模型服务预设，来自代码里的常量",
    "/api/restaurants/needs": "餐厅需求选项，来自词表文件",
    "/api/nutrition/tags": "食物标签，来自营养库",
}


def path_params(app) -> dict[str, set[str]]:
    """从 create_app(serve_frontend=False).openapi() 取出每个路径参数名出现在哪些路径。"""
    found: dict[str, set[str]] = {}
    for path, operations in app.openapi()["paths"].items():
        for operation in operations.values():
            for parameter in operation.get("parameters", []):
                if parameter["in"] == "path":
                    found.setdefault(parameter["name"], set()).add(path)
    return found
