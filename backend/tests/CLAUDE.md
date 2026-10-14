# backend/tests 目录说明书

## 职责
- 后端全部自动化测试（pytest）：单元、接口、交叉用户、迁移、文档核对（各步骤的 *_docs.py 核对交付文档与代码一致）、前端契约（test_frontend_contract.py 逐字核对 frontend/src/lib/contract.ts）、接口快照（test_openapi_snapshot.py）与目录说明书（test_directory_manuals.py）。
- 夹具与助手：
  - conftest.py：导入 app 之前把数据库固定成测试库 goodlife_test、换上固定的测试密钥并放开模型服务的内网地址；会话开始迁移到最新；每个测试结束清空全部表；client 夹具是全新的 TestClient。
  - helpers.py：register_and_login、accept_disclaimer、ready_user（注册、登录、确认免责，可选写档案）；任务 3a 起 ready_user 默认同时给出经期与医嘱两项单独同意，需要未同意状态时显式传 consents=False。
  - agent_fake.py：基于 MockTransport 的脚本化模拟模型（say、call、echo、fail），scripted 夹具替换适配器工厂，connect 为用户配好对话模型。

## 边界
- 测试只连 127.0.0.1:5433 的 goodlife_test；与 Playwright 的端到端服务器共用这个库（它启动时清空全部表），所以后端全量 pytest 与 Playwright 绝不同时运行。
- 模型、高德一律用 MockTransport 或本机模拟服务；不联网、不读 backend/.env、不碰真实密钥。
- 需要临时目录用 tempfile，不用 pytest 的 tmp_path；需要固定日期用 get_today 依赖覆盖或显式传参，不靠真实时间碰运气。

## 入口
- 在 backend 目录：uv run pytest -q -W error 全量（必须零失败零警告，工具调用超时设到上限）；单文件 uv run pytest tests/文件名.py -q -W error。
- 加交叉用户测试：用 ready_user 建两个用户（例如 alice 与 bella），alice 建数据，bella 对同一编号逐个调用读、改、删与状态动作，断言全部是 404 not_found（与不存在时完全相同），列表与汇总里看不到 alice 的数据，最后确认 alice 的数据没被改动；范例见 test_medical_api.py 的 test_other_users_cannot_touch_items。
- 新加业务路由时同步看 test_route_guards.py：每个业务路由都要经免责与模块门槛。

## 禁区
- 测试名用英文蛇形命名；断言要真的检查行为，不写恒真断言，不用固定 sleep 等待。
- 不把 -W error 下出现的警告压掉了事；先找出警告的来源。
- 文档核对测试引用的测试名要与文件里逐字一致；移动或改名测试时同步改交付文档里的引用。
- 每个测试文件不超过 800 行；现有的 test_agent_loop.py 与 test_nutrition_engine.py 超出，由步骤 12 任务 10 拆分，拆之前不要再往里加测试。
