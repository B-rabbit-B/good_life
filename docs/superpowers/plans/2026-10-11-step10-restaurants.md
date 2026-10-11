# 步骤 10 附近餐厅推荐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按用户授权的定位、手动输入的地点或已保存的粗略区域，用高德官方接口检索附近餐饮场所，按“餐厅类型 → 代表菜 → 步骤 04 引擎评价”判断哪些类型适合、哪些要避开并说明原因，给出“到店可点、适量、应避开”的一般性建议与导航链接；同时作为 SDK 能力接入步骤 08 的聊天智能体。满足 `docs/10-附近餐厅推荐.md` 的 7 条验收标准（第 1、2 条的真实检索由用户运行实测脚本补做）。

**Architecture:** 新增 `app/restaurants` 包：`amap.py`（高德客户端）、`coords.py`（WGS-84 转 GCJ-02）、`data/restaurant_types.json` 与 `data/needs.json`、`types.py`（类型判断与整类结论）、`needs.py`（需求解析）、`ranking.py`（过滤排序）、`models.py`、`service.py`、`schemas.py`、`router.py`、`live_check.py`。SDK 新增能力 `nutrition.nearby_restaurants`，智能体经 SDK 调用。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、PostgreSQL 16、Alembic、httpx2、pytest。不新增依赖。

**Spec:** `docs/superpowers/specs/2026-10-11-step10-restaurants-design.md`（执行者必须先读）；步骤文档 `docs/10-附近餐厅推荐.md`。

## Global Constraints

- 运行平台是 Windows 11，终端是 PowerShell 5.1（不支持 `&&`）；也可以用 Bash 工具。
- 所有后端命令都在 `E:\workspace\good-life\backend` 目录下执行，统一用 `uv run ...`；完整测试用 `uv run pytest -q -W error`，必须零失败、零警告；不要用 pytest 的 tmp_path（需要临时目录时用 tempfile）。
- 数据库地址用 `127.0.0.1:5433`，测试库 `goodlife_test`；Docker 未启动时先启动 Docker Desktop（`C:\Users\Administrator\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`），再在仓库根目录执行 `docker compose up -d --wait db`。
- 不新增依赖；HTTP 调用用项目已有的 `httpx2`。
- 自动化测试绝不访问真实网络：高德一律用 `httpx2.MockTransport` 模拟；模型一律用 `tests/agent_fake.py` 的做法模拟。
- 统一错误格式 `{"error": {"code", "message"}}`，业务错误抛 `AppError`；本模块错误码以 `restaurant_` 开头，说明是中文并给出下一步建议。
- 每张业务表都有 `user_id`；查询从 `owned_by` 开始；请求模型 `extra="forbid"`；任何接口都不接受客户端传入的 user_id。
- 所有 `/api/restaurants/*` 接口依赖 `require_nutrition_user`。
- 隐私：精确坐标、手动地点原文、检索内容都不入库、不写日志与审计；粗略区域用 `EncryptedJSON` 保存，坐标取整到小数点后两位；检索结果不回传精确中心坐标。
- 高德密钥只来自服务端配置 `AMAP_KEY`，不出现在日志、错误、响应、审计与实测结果里；Claude 与子代理不得读取真实的 `backend/.env` 里的密钥值。
- 分工：过滤与排序只由规则决定；适合程度与原因只来自步骤 04 的引擎；模型只能从需求词表里挑词，词表外的词丢弃。
- 高德与模型的网络调用期间不持有数据库事务：读完设置后先 `db.commit()` 结束读事务，再发网络请求，之后再读引擎上下文。
- 新迁移 `0016_restaurants` 接在 `0015_photos` 之后；表总数变为 28 张。
- 提交信息以如下一行结尾：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；不得提交 `backend/.env`、`.superpowers/`、`backend/llm_keys.local.env`、`backend/*_live_result.md`、`backend/photo_eval/`、`backend/photo_eval_result.md`、`backend/restaurant_live_result.md`。
- 交付文档（`docs/10-交付物/` 下）不得出现代码、命令、反引号或代码块。

## 与设计文档的一处调整

SDK 能力名必须是“模块.动作”，且模块只能是 profile、cycle、medical、nutrition、fitness 之一（见 `app/sdk/registry.py`）。所以设计文档里的 `restaurants_recommend` 实际命名为 `nutrition.nearby_restaurants`（MCP 与智能体工具名按 `tool_name()` 生成），随饮食模块的开放而开放。其余与设计文档一致。

## 文件结构

```
backend/app/restaurants/
├── __init__.py
├── coords.py、amap.py                      # 任务 1
├── data/restaurant_types.json、data/needs.json
├── types.py、needs.py、ranking.py          # 任务 2
├── models.py、service.py、schemas.py、router.py   # 任务 3
└── live_check.py                           # 任务 5
backend/app/config.py、backend/.env.example # 任务 1
backend/app/sdk/capabilities/nutrition.py、app/sdk/tooling.py、app/sdk/client.py、app/sdk/manifest.json、app/agent/assembly.py   # 任务 4
backend/migrations/versions/0016_restaurants.py
backend/tests/test_restaurant_amap.py、test_restaurant_rules.py、test_restaurant_flow.py、test_restaurant_agent.py、test_restaurant_live_check.py、test_restaurant_docs.py
docs/10-交付物/
```

---

### Task 1: 配置、坐标换算与高德客户端

**Files:**
- Create: `backend/app/restaurants/__init__.py`, `coords.py`, `amap.py`
- Modify: `backend/app/config.py`, `backend/.env.example`, `backend/tests/test_config.py`（如需要）
- Test: `backend/tests/test_restaurant_amap.py`

**Interfaces:**
- Produces:
  - `Settings` 新增 `amap_key: str | None = None`（空字符串视为 None）、`amap_base_url: str = "https://restapi.amap.com"`、`amap_timeout_seconds: float = 8.0`；`.env.example` 加三行占位与中文说明（AMAP_KEY 留空即关闭附近餐厅功能，需要的是高德开放平台的“Web 服务”类型密钥）。
  - `app.restaurants.coords`：`wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]`（标准公开算法；中国境外的点原样返回）；`coarse(lng, lat) -> tuple[float, float]`（四舍五入到两位小数）。
  - `app.restaurants.amap`：
    - `Poi(id: str, name: str, lng: float, lat: float, typecode: str, type_text: str, address: str, distance_m: int | None, rating: float | None)`（frozen dataclass）
    - `Place(name: str, lng: float, lat: float, district: str, adcode: str)`（frozen dataclass）
    - `class AmapClient`：`__init__(self, key: str, base_url: str, timeout: float, transport: httpx2.BaseTransport | None = None)`；`around(lng, lat, *, keywords: str | None, radius: int) -> list[Poi]`（GET `/v5/place/around`，参数 location=“经度,纬度”（6 位小数）、types=050000、radius、sortrule=distance、page_size=25、page_num=1、show_fields=business，有 keywords 时带上；distance 与 business.rating 解析为数字，缺失或不是数字为 None）；`geocode(address: str, city: str | None) -> Place | None`（GET `/v3/geocode/geo`，取第一个结果；没有结果返回 None）；`regeo(lng, lat) -> Place`（GET `/v3/geocode/regeo`，取 addressComponent 的 district 与 adcode）
    - 错误映射（高德 status 为 "0" 时看 infocode）：10003、10004、10014、10019、10020、10021、10044、10045 → `restaurant_service_busy`(503，提示稍后再试)；10001、10009、10010、10012 → `restaurant_service_failed`(502，提示服务端的高德密钥无效或类型不对，需要 Web 服务类型)；其他 infocode、非 200、超时、网络错误、返回不是 JSON → `restaurant_service_failed`(502)。错误说明与异常信息里不得出现密钥（参照 `app.llm` 的脱敏做法）。
    - `_transport_override: httpx2.BaseTransport | None = None`；`use_transport(transport)`：上下文管理器，测试期间替换传输层；`get_amap_client() -> AmapClient`：未配置 `amap_key` 时抛 `restaurant_not_configured`(503，说明附近餐厅功能未开启，需要在服务端配置高德密钥)；否则按配置与 `_transport_override` 构造。路由用它做依赖，SDK 能力直接调用它。
    - `navigation_url(poi: Poi) -> str`：`https://uri.amap.com/navigation?to=<经度>,<纬度>,<URL 编码的店名>&mode=walk&src=good-life&coordinate=gaode&callnative=1`。

- [ ] **Step 1: 写失败测试** `test_restaurant_amap.py`：
  - 坐标：北京一个点换算后偏移在 100 至 800 米之间、结果确定；境外点（例如东京、纽约）原样返回；`coarse` 取两位小数。
  - `around`：用 MockTransport 校验请求路径与参数（key、location、types=050000、radius、sortrule、show_fields、有无 keywords），解析出店铺编号、名称、坐标、类别编码、地址、距离、评分；评分缺失或为空数组时为 None。
  - `geocode` 有结果与无结果；`regeo` 取区县与编码。
  - 错误映射：各类 infocode、HTTP 500、超时、非 JSON；所有错误的说明与 `repr` 里都不含测试用密钥。
  - `get_amap_client`：未配置时 503 `restaurant_not_configured`；`use_transport` 生效。
  - `navigation_url`：店名里的空格与中文被正确编码。
- [ ] **Step 2: 运行确认失败**，然后实现。
- [ ] **Step 3: 运行确认通过**（目标测试与全量测试）并提交：`git commit -m "feat(restaurants): add AMap client, coordinate conversion and settings"`

---

### Task 2: 餐厅类型表、需求词表、整类结论与排序

**Files:**
- Create: `backend/app/restaurants/data/restaurant_types.json`, `data/needs.json`, `types.py`, `needs.py`, `ranking.py`
- Test: `backend/tests/test_restaurant_rules.py`

**Interfaces:**
- Consumes: `Poi`（任务 1）；`app.nutrition.engine.evaluate_food(food, grams, context, catalog) -> Evaluation`；`Evaluation.conclusion`（suitable、caution、not_recommended）与 `Evaluation.reasons`（`Reason(source, effect, code, message, ref)`）；`load_catalog()`、`Food.default_grams`、`DISCLAIMER` 等引擎常量。
- Produces:
  - `restaurant_types.json`：列表，每项 `{"key", "name", "typecodes": [...], "name_keywords": [...], "dishes": ["<营养库食物编号>", ...]}`；约 18 类，至少包含：家常菜、川菜、湘菜、粤菜（含茶餐厅、潮汕）、火锅、烧烤、麻辣烫与串串、粥铺、轻食沙拉、面馆（含米线米粉）、饺子馄饨包子、素食、清真与西北菜、海鲜、西餐、日料、快餐炸鸡汉堡、甜品饮品。每类 3 至 5 道代表菜，只能用营养库里已有的编号（先查 `app/nutrition/data/dishes.json` 与营养库）；类别编码以高德官方 POI 分类编码表为准，无法核实的编码不要写，改靠店名关键词。
  - `needs.json`：列表，每项 `{"key", "name", "description", "synonyms": [...], "keywords": [...最多 3 个], "prefer_types": [...类型键]}`；约 12 个，至少包含：清淡、粥、汤、轻食、高蛋白、素食、面食、不辣、少油、饺子包子、清真、甜品。同义说法覆盖常见口语（例如“胃不舒服”“想吃软的”归入清淡与粥，“健身”“增肌”归入高蛋白，“减脂”归入轻食）。
  - `app.restaurants.types`：`RestaurantType`（frozen dataclass，字段同 JSON）；`load_types() -> tuple[RestaurantType, ...]`（缓存）；`GENERIC_TYPECODES = frozenset({"050000", "050100"})`；`classify(poi) -> RestaurantType | None`（顺序：店名关键词（较长的关键词优先）→ 具体类别编码 → 笼统编码不判断，返回 None）；`TypeAdvice(type_key, type_name, conclusion, order: tuple[str, ...], moderate: tuple[str, ...], avoid: tuple[str, ...], reasons: tuple[Reason, ...])`；`advise(rtype, context, catalog) -> TypeAdvice`：用每道代表菜的默认克数调用 `evaluate_food`；一半以上（含一半）为不建议 → not_recommended；否则有任何不建议或需注意 → caution；否则 suitable；适合进 order、需注意进 moderate、不建议进 avoid（用营养库里的中文名）；reasons 取不建议与需注意菜品里效果为负面的原因，按 code 与 ref 去重，保持引擎顺序。
  - `app.restaurants.needs`：`Need`（frozen dataclass）；`load_needs()`；`match_rules(text: str) -> tuple[str, ...]`（同义说法或名称出现在文本里即命中，最多 3 个，按词表顺序）；`MODEL_PROMPT`（列出词表的键与名称，要求只输出 `{"needs": [...]}`，最多 3 个）；`parse_model_needs(text) -> tuple[str, ...]`（从正文里取第一个 JSON 对象，只保留词表里的键，格式不对返回空）；`resolve(text: str | None, keys: list[str]) -> tuple[tuple[str, ...], str]`：直接给的键（未知键抛 `restaurant_unknown_need` 422）与规则结果合并去重，来源为 rules 或 none；模型挑词由任务 3 的服务层在规则未命中时调用。
  - `app.restaurants.ranking`：`MAX_RESULTS = 20`；`CONCLUSION_RANK = {"suitable": 0, "caution": 1, "unchecked": 2}`；`Ranked(poi, rtype: RestaurantType | None, conclusion)`；`rank(pois, advice_by_type: dict[str, TypeAdvice], prefer_types: set[str]) -> tuple[list[Ranked], dict[str, list[Poi]]]`：返回推荐列表与按类型键分组的被避开店铺；排序键依次为结论、是否属于偏向类型（属于在前）、距离（None 在后）、评分（高在前，None 在后）、店铺编号（保证确定）；截取前 20 家。

- [ ] **Step 1: 写失败测试** `test_restaurant_rules.py`：
  - 数据校验：类型键与需求键唯一；每类 3 至 5 道代表菜且编号都在营养库里；每个需求的 prefer_types 都是已有类型键、keywords 不超过 3 个；类别编码都是 6 位数字。
  - 分类：店名“老成都川菜馆”（编码 050100）→ 川菜；“张记麻辣烫”→ 麻辣烫；“XX 粥铺”→ 粥铺；编码为川菜、店名无关键词 → 川菜；只有 050000 与无关店名 → None。
  - 整类结论（用内存里构造的 `EvaluationContext`，参照 `tests/test_nutrition_engine.py` 的构造方法）：
    - 忌辛辣医嘱 → 川菜与麻辣烫为 not_recommended，reasons 来源为医嘱，avoid 里有麻婆豆腐等；
    - 粥铺为 suitable 或 caution 且不是 not_recommended；
    - 没有任何约束的用户 → 没有 not_recommended。
  - 需求：“胃不舒服想吃点软的”命中清淡与粥；“健身后想吃肉”命中高蛋白；无关文字不命中；直接给的键与规则结果合并去重并截到 3 个；未知键 422；`parse_model_needs` 只保留词表内的键、处理围栏与说明文字、格式不对返回空。
  - 排序：结论优先于距离；同结论时偏向类型在前；距离 None 在后；评分为次要键；被避开的店不进列表、按类型分组返回；超过 20 家截断；结果确定。
- [ ] **Step 2: 运行确认失败**，然后实现（先查营养库与菜品表的实际编号再写数据文件）。
- [ ] **Step 3: 运行确认通过**并提交：`git commit -m "feat(restaurants): add restaurant types, need vocabulary, type advice and ranking"`

---

### Task 3: 设置表、检索流程与接口

**Files:**
- Create: `backend/app/restaurants/models.py`, `service.py`, `schemas.py`, `router.py`
- Create: `backend/migrations/versions/0016_restaurants.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`, `backend/tests/test_route_guards.py`
- Test: `backend/tests/test_restaurant_flow.py`

**Interfaces:**
- Consumes: 任务 1、2 的全部接口；`build_context(db, user_id, today)`；`resolve_target(user_id, "chat")` 与 `complete(...)`（`app.llm.service`）；`AdapterFactory` 与 `get_adapter_factory`。
- Produces:
  - ORM `RestaurantSettings`（restaurant_settings）：id、user_id（唯一）、location_consent（String(16)，not_asked、granted、denied，默认 not_asked）、consent_updated_at（可空）、area（EncryptedJSON，可空，`{"name", "adcode", "lng", "lat"}`）、area_saved_at（可空）、created_at、updated_at。
  - `app.restaurants.service`：
    - `NOTICE = "到店可点与应避开是基于餐厅类别的一般性建议，不代表该店真实菜单，也不保证该店有这些菜。"`；`UNCHECKED_TIP = "无法判断这家店的类别，请到店自行留意。"`；`GPS_CENTER_NAME = "你的当前位置"`；`RATE_LIMIT = 30`（每用户每小时检索次数，进程内滑动窗口）；`reset_rate_limit()`（测试用）
    - `get_settings(db, user_id) -> RestaurantSettings`（没有则建一行 not_asked）；`set_consent(db, user_id, consent)`；`clear_area(db, user_id)`
    - `search(db, user_id, request: SearchIn, today, *, client: AmapClient, factory: AdapterFactory | None) -> dict`：
      1. 频率限制，超出抛 `restaurant_rate_limited`(429)。
      2. 读设置并确定中心：坐标 → 要求 granted，否则 `restaurant_location_not_granted`(409，说明“没有定位授权，可以直接输入地点”）；gps 坐标系先换算；手动地点 → `geocode`，没有结果 `restaurant_place_not_found`(422，提示换个说法或加上城市)；已保存区域 → 没有则 `restaurant_no_location`(422)。
      3. `db.commit()` 结束读事务。
      4. 需求：`needs.resolve`；规则未命中、`need` 文字不为空且 factory 不为 None 时，尝试 `resolve_target(user_id, "chat")` 并调用模型挑词（未配置模型或调用失败都静默跳过，来源记 none）；模型挑出的词来源记 model。
      5. 检索：有需求时按需求词的 keywords 合并去重后取前 3 个，每个调用一次 `around`；没有需求时不带 keywords 调用一次；按店铺编号去重。
      6. 若 `remember_area`：手动地点用 geocode 结果的区县；坐标调用 `regeo`；保存 `{"name", "adcode", 取整后的坐标}` 与时间。
      7. `build_context` 后按出现的类型调用 `advise`，`rank` 排序，组装结果。
    - 结果字典字段与设计文档“检索结果”一节一致：`center {name, source}`、`needs {keys, names, source}`、`restaurants [...]`（每家 `id, name, type_key, type_name, distance_m, rating, address, conclusion, nav_url`；未知类型 type_key 与 type_name 为 None、conclusion 为 unchecked 并附 `tip`）、`type_advice [...]`、`avoided_types [{type_key, type_name, reasons, restaurants: [店名]}]`、`notice`、`disclaimer`。
  - `app.restaurants.schemas`：`Coordinate(lng: -180..180, lat: -90..90, coord_type: "gps" | "gcj02" = "gps")`；`SearchIn(location: Coordinate | None, place: str 1..50 | None, city: str 1..20 | None, use_saved_area: bool = False, need: str ..100 | None, needs: list[str] 最多 3 个 = [], radius: int 500..5000 = 2000, remember_area: bool = False)`，三种地点给了不止一种时 422，一种都没给时由服务抛 `restaurant_no_location`；`city` 只能和 `place` 一起用；`SettingsOut(location_consent, should_ask_location, area: {name, saved_at} | None)`；`ConsentIn(consent: "granted" | "denied")`；`NeedOut(key, name, description)`；`SearchOut`（与结果字典一致，原因用 `app.nutrition.schemas.ReasonOut`）。
  - 接口（前缀 `/api/restaurants`，依赖 `require_nutrition_user`）：GET `/settings`、PUT `/settings/consent`、DELETE `/settings/area`（204）、GET `/needs`、POST `/search`（依赖 `get_amap_client` 与 `get_adapter_factory`）。

- [ ] **Step 1: 写失败测试** `test_restaurant_flow.py`（模拟高德返回一组固定的店：川菜馆、粥铺、轻食店、火锅店、麻辣烫、面馆、一家判断不出类别的“某某餐厅”；模拟模型用 `tests/agent_fake.py` 的做法）：
  - 验收第 1 条：同意授权后用 gps 坐标检索 → 返回店铺、距离、类型与结论；高德收到的是换算后的坐标；
  - 验收第 2 条：不授权、用手动地点“国贸”加城市检索 → 正常返回；地点找不到 → 422；
  - 验收第 3 条：有忌辛辣医嘱的用户 → 川菜馆、火锅、麻辣烫不在推荐列表里，出现在 avoided_types，原因来源为医嘱并指向该条目；普通用户同样的数据 → 不避开川菜；
  - 验收第 4 条：每次结果都带固定 notice；type_advice 的 order、moderate、avoid 都是营养库里的菜名；
  - 验收第 5 条：每家店都有导航链接，指向该店坐标与名称；
  - 验收第 6 条：坐标检索后数据库里查不到坐标与地点原文（直接查表的原始内容）；remember_area 后 area 为密文、坐标两位小数；清除后为空；use_saved_area 在清除后返回 422；
  - 验收第 7 条：拒绝后 should_ask_location 为假且之后一直为假；坐标检索返回 409，说明建议直接输入地点，不包含“请授权”“开启定位”之类的再次索要措辞；手动地点检索照常可用；只有用户自己改回 granted 才能用坐标；
  - 需求：一句话需求命中规则时高德收到对应关键词；规则不命中时模拟模型挑词（含词表外的词被丢弃），来源 model；没有配置对话模型时静默跳过；
  - 错误：未配置密钥 503；高德额度 503；高德失败 502；频率超限 429；
  - 事务：高德与模型调用期间没有打开的数据库事务（参照 `tests/test_photo_flow.py` 的检查方式）；
  - 归属与准入：设置只影响自己；所有 `/api/restaurants/` 路由依赖 `require_nutrition_user`（更新 `test_route_guards.py`）。
- [ ] **Step 2: 运行确认失败**，然后实现（迁移 `0016_restaurants`，down_revision `0015_photos`）。
- [ ] **Step 3: 运行确认通过**；`uv run alembic upgrade head`；提交：`git commit -m "feat(restaurants): add location settings, search flow and the restaurants API"`

---

### Task 4: SDK 能力、MCP 工具与智能体接入

**Files:**
- Modify: `backend/app/sdk/capabilities/nutrition.py`, `backend/app/sdk/tooling.py`（TOOL_USAGE）、`backend/app/sdk/client.py`（SDK_VERSION "1.2"）、`backend/app/sdk/manifest.json`（重新生成快照）、`backend/app/agent/assembly.py`
- Modify: 守护能力数量与工具数量的既有测试与文档（`tests/test_mcp_server.py`、`tests/test_sdk_*.py`、`tests/test_agent_*.py`、README 中 SDK、MCP、智能体工具数量的描述）
- Test: `backend/tests/test_restaurant_agent.py`

**Interfaces:**
- Consumes: `service.search`、`get_amap_client`、`load_needs`。
- Produces:
  - `NearbyParams(place: str 1..50 | None, city: str 1..20 | None, needs: list[<需求键枚举>] 最多 3 个 = [], radius: int 500..5000 = 2000)`，`extra="forbid"`；需求键枚举由 `needs.json` 生成，使 JSON Schema 里出现可选值。
  - 能力 `nutrition.nearby_restaurants`（read）：没有 place 时用已保存的粗略区域，都没有时抛 `restaurant_no_location`（错误说明：请问用户现在在哪里，给出地名或地标）；调用 `service.search(..., client=get_amap_client(), factory=None)`；输出 `NearbyOut`：`center_name`、`restaurants`（前 8 家：`name, type_name, distance_m, conclusion, order`）、`avoided_type_names`、`notice`。不包含应避开的菜名与原因原文。
  - TOOL_USAGE 新增条目：什么时候用（用户不想做饭、想出去吃、问附近吃什么，并给出了地点或已有保存区域）；什么时候不要用（问菜谱、要点外卖或下单、问某家店真实菜单）。
  - 智能体：`select_tools` 在服务端没有配置 `amap_key` 时跳过该能力；系统指令增加一句：“附近餐厅推荐只是按餐厅类别给出的一般性建议，不代表该店真实菜单；不要向用户索要定位授权，需要地点时请用户说出地名或地标。”
  - SDK 共 34 项能力（23 项只读）、MCP 工具 28 个、SDK 版本 1.2；智能体一轮最多提供的工具数随之加一。步骤 06、08 与第一阶段验收记录里的历史数字不改动，只在当时的记录后加一行说明（参照步骤 08 的做法）。

- [ ] **Step 1: 写失败测试** `test_restaurant_agent.py`：
  - SDK 直接调用：有 place 时返回结果；没有 place 但有保存区域时用区域；都没有时得到 `restaurant_no_location` 的 SDK 错误；未配置高德时 SDK 错误码为 `restaurant_not_configured`；输出里没有 avoid 菜名；
  - MCP：工具清单 28 个、包含新工具；
  - 智能体：配置了高德时工具清单里有它、没配置时没有；系统指令里有上面那句；用模拟模型调用该工具并回答，回答经过输出检查（忌辛辣用户的模拟模型如果在回答里写出“麻辣烫”会被拦截改写）；
  - manifest 快照与 `build_manifest` 一致；SDK_VERSION 为 1.2。
- [ ] **Step 2: 运行确认失败**，然后实现并更新守护数量的既有测试与文档。
- [ ] **Step 3: 运行确认通过**（全量）并提交：`git commit -m "feat(restaurants): expose nearby restaurants to the SDK, MCP and the agent"`

---

### Task 5: 实测脚本、交付文档与验收记录

**Files:**
- Create: `backend/app/restaurants/live_check.py`
- Modify: `backend/.gitignore`（加入 `restaurant_live_result.md`）
- Create: `docs/10-交付物/位置授权与数据处理说明.md`、`需求到检索关键词的映射说明.md`、`约束过滤与排序规则说明.md`、`接口清单.md`、`验证场景记录.md`、`验收记录.md`
- Create: `backend/tests/test_restaurant_live_check.py`, `backend/tests/test_restaurant_docs.py`
- Modify: `README.md`（新增“附近餐厅推荐”一节；开头完成情况；表数量二十八张；SDK 与 MCP 数量），`docs/00-总览与串联.md`（步骤 10 改为“待验收”）

**Interfaces:**
- `app.restaurants.live_check`：读取 `.env` 里的高德配置（不打印密钥）；没有密钥时给出中文说明并退出；建临时用户（普通、忌辛辣医嘱已确认、减脂目标），在北京国贸、上海人民广场、成都春熙路三个地点各跑一次手动地点检索，另跑一次 GPS 坐标检索（用公开地标的坐标）与一次带一句话需求的检索；输出 `backend/restaurant_live_result.md`：每个场景的中心、需求、前 10 家（名称、类型、距离、结论）、避开的类型与原因、耗时；全文按密钥脱敏；结束或中断时删除临时用户；运行方式 `uv run python -m app.restaurants.live_check`。
- 测试：用 MockTransport 驱动脚本，断言场景齐全、输出不含密钥、临时用户被删除、失败时仍清理；文档测试检查 6 份文档存在且不含反引号与代码块、验收记录 7 行且“用户验收”列为空、第 1、2 条注明真实检索依赖用户运行实测脚本、映射说明列出全部需求词、过滤说明列出全部餐厅类型、接口清单覆盖全部接口与错误码（含导航跳转）、表数量二十八张按模型实际数出来。
- 文档按实际代码写；验证场景记录里“结果”一栏写“待用户运行实测脚本后填写”。

- [ ] **Step 1: 写测试**，**Step 2: 实现与写文档**，**Step 3: README 与总览、全量测试、`uv run alembic upgrade head`**，**Step 4: 提交** `git commit -m "docs(restaurants): add live check script, step 10 delivery docs and acceptance record"`
