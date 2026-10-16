# backend 目录说明书

## 职责
- FastAPI 后端：全部业务规则、数据与对外能力都在这里，前端只显示后端给的结论。入口 app/main.py 的 create_app 装配全部路由、错误处理、上传体积中间件与请求日志中间件（common/request_log.py），并在根路径提供打包好的前端（app/frontend_static.py：没有路由匹配的请求才走到它；文件、404 回退与 HEAD 一律带安全响应头；第一段的 /.well-known 放行，其余点开头的路径当作不存在）。
- app/models.py 汇总导入全部 ORM 模型（Alembic 与测试靠它拿到完整表结构，新增模型文件必须在这里登记）；app/errors.py 把业务错误统一成 {"error": {"code", "message"}}；app 根下的 phase1_demo、phase2_demo、phase2_acceptance、e2e_server、openapi_export 是演示、验收与工具入口，不是业务模块。

## 边界
- 分层（数字小的在底层，只能引用同层或更低层；由 tests/test_import_boundaries.py 守护，登记表 LAYERS 与例外表 ALLOWED 在那个文件里）：
  0 config、db、errors、security、common → 1 auth → 2 disclaimer、consents → 3 profile →
  4 cycle、medical、llm、agent_grants → 5 fitness → 6 nutrition → 7 photos、restaurants → 8 sdk → 9 agent →
  10 mcp_server、account、main 与 app 根下的入口模块。唯一的反向引用：common/body_limit.py 从 medical 与 photos 只取两个上传上限常量。
- 每个业务路由都要经免责声明门槛（或建在它上面的模块门槛），tests/test_route_guards.py 逐条检查；所有用户数据查询从 common/ownership 的 owned_by 开始，别人的记录与不存在的一样 404；健康相关的明文字段用 security/crypto 的加密列存。

## 入口
- 运行：在本目录用 uv run（例如 uv run uvicorn app.main:app --reload --port 8000）；迁移 uv run alembic upgrade head；测试 uv run pytest -q -W error，必须零失败零警告。
- 接口变化后在 frontend 运行 pnpm api:gen 并提交生成结果；SDK 能力的输入输出变化后运行 uv run python -m app.sdk.manifest。
- 说明书索引（包内子目录如 data、adapters、capabilities 没有单独说明书，以所在包的为准）：
  - 底层：app/security/CLAUDE.md（密码、令牌、字段加密）、app/common/CLAUDE.md（归属、日期、年龄、上传上限）
  - 账号与门槛：app/auth/CLAUDE.md、app/disclaimer/CLAUDE.md、app/consents/CLAUDE.md（经期与医嘱的单独同意）、app/profile/CLAUDE.md（模块开放）
  - 业务模块：app/cycle/CLAUDE.md、app/medical/CLAUDE.md、app/fitness/CLAUDE.md、app/nutrition/CLAUDE.md、app/llm/CLAUDE.md、app/photos/CLAUDE.md、app/restaurants/CLAUDE.md、app/agent_grants/CLAUDE.md
  - 上层：app/sdk/CLAUDE.md、app/mcp_server/CLAUDE.md、app/agent/CLAUDE.md、app/account/CLAUDE.md（撤回同意并清除模块数据、导出全部数据、删除账号）
  - tests/CLAUDE.md（测试、夹具与测试库）、migrations/CLAUDE.md（迁移）

## 禁区
- 不读、不改、不提交 .env 与 llm_keys.local.env；任何 *_live_result.md 与 photo_eval 目录不提交。
- 各包的 live_check、photos/eval_check、agent/redteam_check 是用户本人用真实密钥运行的实测脚本，自动化测试只用模拟服务驱动它们，Claude 不运行真实实测。
- 日志只记方法、路由模板、状态码、能力名、错误码与异常类名；不记请求或响应内容、路径参数、查询串、异常文字与堆栈。
  访问日志与未处理异常由 common/request_log.py 统一记（只记方法、路由模板、状态码与异常类名，uvicorn 自带的访问日志整条丢弃），只有唯一约束冲突（sqlstate 23505）在 errors.py 转成 409 且只记约束名，其余完整性错误（非空、外键、检查约束）是程序错误，按未处理的异常记类名回 500；不用 logger.exception，也不在日志里写 request.url。tests/test_log_canaries.py 起真实服务器、全部日志出口调到 DEBUG 守护这条规则。
- 不在路由函数里写业务规则：规则放在各包的 service、engine 一类模块里，SDK 与网页才能共用同一套。
- 不引入 import-linter 之类的新依赖做检查；依赖方向用自写的 ast 扫描测试。
- 后端 pytest（全量或单文件）与前端 Playwright 不同时运行（共用 goodlife_test，都会清表）。
