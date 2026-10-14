# common 包说明书

## 职责
- 各业务包共用、又不属于任何一个业务的底座：
  - ownership.py：UserOwnedMixin（业务表统一的 user_id 外键，删用户级联删除）、owned_by（所有业务查询的起点）、get_owned_or_404；
  - clock.py：get_today 依赖，路由取“今天”都经它，测试里可以换成固定日期；
  - age.py：年龄按“当年减出生年份”算，MIN_AGE 14（不满不服务）、ADULT_AGE 18（未成年规则的分界）；
  - body_limit.py：请求体上限中间件，在鉴权与请求体解析之前拦住过大的请求：POST、PUT、PATCH 先按方法与路径匹配医嘱证据、餐食照片与模型对话（32 MiB，覆盖常见用法，极端的合法请求可能超过而得到 413）三条专门规则，其余一律 1 MiB（413 request_too_large）；
  - request_log.py：请求日志中间件（访问日志只记“方法 路由模板 状态码”；兜住未处理的异常，回统一的 500，只记类名、方法与路由模板，不再抛给服务器）、route_template（按方法与路径查路由模板）与 install_log_hygiene（丢弃 uvicorn.access、把 sqlalchemy 的引擎与连接池记录器钉在 WARNING）。

## 边界
- 位于最底层（与 config、db、errors、security 同层），只能引用同层模块。
- 唯一的登记例外：body_limit.py 从 medical.orders 取 MAX_EVIDENCE_BYTES、从 photos.images 取 MAX_UPLOAD_BYTES，只取常量，让上限只有一处定义；不得再从业务包引用别的东西。
- 被几乎所有业务包引用；main 挂上 UploadBodyLimitMiddleware，再在它外层挂 RequestLogMiddleware（413 也有访问日志）并调用 install_log_hygiene；errors.py 的唯一约束冲突处理用 route_template 记路由模板。

## 入口
- 新建业务表：混入 UserOwnedMixin，删除用户时自动级联。
- 查当前用户的数据：一律从 owned_by 起写查询；按编号取一条并要求属于当前用户：用 get_owned_or_404，不要先按编号查再判断归属。
- 路由要“今天”：注入 get_today，测试才能固定日期；判断是否未成年或是否满 14 周岁：用 age.py，不另写算法。
- 新增上传接口或请求体可能超过 1 MiB 的接口：在 body_limit.py 的默认规则之前加一条专门规则（方法、路径与上限），上传上限常量仍定义在业务包里。
- 测试：归属与 404 散在各模块的交叉用户测试（例如 tests/test_medical_api.py、tests/test_cycle_records.py）；年龄见 tests/test_minors.py；上传上限见 tests/test_medical_api.py 与 tests/test_photo_flow.py，请求体统一上限见 tests/test_hardening.py；请求日志见 tests/test_log_hygiene.py 与 tests/test_log_canaries.py。

## 禁区
- 不放业务规则：某个规则只有一个模块用，就留在那个模块里。
- 别人的记录与不存在的记录必须同一个状态码与错误码（404 not_found），不能透露记录是否存在；不要在业务包里另写一套“先查再判断归属”。
- 年龄不另写算法：任何未成年或 14 周岁判断都用 age.py（档案只有出生年份，算出的年龄可能比实际大一岁，这是已接受的取舍）。
- 上传上限不要改成先解析再检查：FastAPI 会先把整个 multipart 读到临时文件，必须在最外层拦。默认规则必须留在规则表最后，否则会盖住专门规则。
- 请求日志不记 scope 里的 path、query_string、请求或响应内容，只记路由模板；不要再给应用加 Exception 处理器（那样异常会被再抛给服务器，uvicorn 会再记一遍完整堆栈）。
