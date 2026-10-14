# backend/tests 目录说明书

## 职责
- 后端全部自动化测试（pytest）：单元、接口、交叉用户（越权矩阵、金丝雀扫描与缺口补测：test_isolation_*.py）、提示词注入（test_injection_bounds.py 让 ScriptedModel 扮演完全听从注入的模型，只断言硬边界；test_preference_injection.py 是偏好过滤与持久化注入链）、迁移、文档核对（各步骤的 *_docs.py 核对交付文档与代码一致）、前端契约（test_frontend_contract.py 逐字核对 frontend/src/lib/contract.ts）、接口快照（test_openapi_snapshot.py）与目录说明书（test_directory_manuals.py）。
- 夹具与助手：
  - conftest.py：导入 app 之前把数据库固定成测试库 goodlife_test、换上固定的测试密钥并放开模型服务的内网地址；会话开始迁移到最新；每个测试结束清空全部表并清零登录与密码复核的失败计数（reset_login_limits，计数在进程内）；client 夹具是全新的 TestClient。
  - helpers.py：register_and_login、accept_disclaimer、grant_consents、ready_user（注册、登录、确认免责，默认同时给出经期与医嘱两项单独同意，可选写档案）；需要未同意状态时显式传 consents=False，之后可用 grant_consents 只给出其中一项。
  - agent_fake.py：基于 MockTransport 的脚本化模拟模型（say、call、echo、fail），scripted 夹具替换适配器工厂，connect 为用户配好对话模型。
  - amap_fake.py：模拟高德（FakeAmap，固定的一组店）与 fake 夹具；不经 client 夹具时直接用 FakeAmap 加 use_transport。
  - db_inspect.py：直接查 pg_catalog（不读模型定义）：user_tables（全部带 user_id 的表）、cascade_problems（user_id 没有级联指向 users(id) 的表）、row_counts（某用户在每张表与 users 的行数）、user_fingerprint（某用户全部行的摘要，判断“数据未变”）；都可传入一个之后回滚的连接。
  - full_user.py：fill_every_table 经真实接口把一个用户的全部业务表都填上至少一行（每处文字带 marker，医嘱原件与照片都大于 1 MB），返回以路径参数名为键的编号，外加 grant_token；新增带 user_id 的表时要在这里补一步，否则 test_cascade_guard.py 失败。
  - isolation_registry.py：越权测试的登记表。路径参数名必须登记为资源参数（RESOURCE_PARAMS，键与 fill_every_table 的返回值同名）或非资源参数（NON_RESOURCE_PARAMS，写明原因）；别人的资源回的错误码（NOT_FOUND_CODE，动作编号沿用 exercise_not_found）；带资源参数的写接口各一个合法请求体（SAMPLE_BODIES，上传接口在 SAMPLE_UPLOADS）；不扫描的公共 GET 接口（PUBLIC_GET_ROUTES，写明原因）；path_params 从接口描述现算参数分布。
  - live_server.py：LiveServer 在线程里起真实的 uvicorn 服务器，把全部日志出口调到 DEBUG 并抓取格式化文本（含堆栈）；request 用标准库 urllib 发请求（它不写日志），prepare_user 注册、登录、确认免责并给出两项单独同意。

## 边界
- 测试只连 127.0.0.1:5433 的 goodlife_test（由 deploy/db-init 的建库脚本在数据库容器首次启动时建立）；与 Playwright 的端到端服务器共用这个库（它启动时清空全部表），所以后端全量 pytest 与 Playwright 绝不同时运行。
- 单文件运行也会连库并清表（conftest 的 autouse 夹具 clean_tables 在每个测试后 TRUNCATE 全部表），所以单文件也不得与全量 pytest、别的 pytest 或 Playwright 并行。
- 模型、高德一律用 MockTransport 或本机模拟服务；不联网、不读 backend/.env、不碰真实密钥。
- 需要临时目录用 tempfile，不用 pytest 的 tmp_path；需要固定日期用 get_today 依赖覆盖或显式传参，不靠真实时间碰运气。

## 入口
- 在 backend 目录：uv run pytest -q -W error 全量（必须零失败零警告，工具调用超时设到上限）；单文件 uv run pytest tests/文件名.py -q -W error。
- 新加接口：test_isolation_matrix.py 从接口描述取出全部路径参数，新参数名没登记就失败；资源参数自动进矩阵（B 的令牌带 A 的编号，必须与随机编号一样 404，A 的数据指纹不变），写接口还要在 SAMPLE_BODIES 给请求体；没有资源参数的新 GET 接口要加进 test_isolation_canary.py 的扫描计划或登记为公共接口；新的带编号 SDK 能力要加进 test_isolation_gaps.py 的 _ID_CAPABILITIES。
- 加交叉用户测试：用 ready_user 建两个用户（例如 alice 与 bella），alice 建数据，bella 对同一编号逐个调用读、改、删与状态动作，断言全部是 404 not_found（与不存在时完全相同），列表与汇总里看不到 alice 的数据，最后确认 alice 的数据没被改动；范例见 test_medical_api.py 的 test_other_users_cannot_touch_items。
- 新加业务路由时同步看 test_route_guards.py：每个业务路由都要经免责与模块门槛。
- 新加智能体写入工具（write 级别能力）：test_injection_bounds.py 的 WRITE_TOOLS 与 AUDIT_NAMES 要一起改，那条测试先核对智能体恰好有这些写入工具，再断言每个都有审计。
- 新增带用户数据的表必须带 user_id 列（UserOwnedMixin，级联指向 users）：级联守护、导出比对、删除与数据指纹都只认带 user_id 的表，只靠外键挂在别的表下面的用户数据会被这些守护漏掉。
- 新加带 user_id 的表：test_cascade_guard.py 会检查级联与 fill_every_table 的覆盖；同时给 account 的导出加上它（test_account_export.py 逐项比对）。
- 磁盘残留类测试：用 tempfile.mkdtemp 建专用目录，把 tempfile.tempdir 与 TEMP、TMP、TMPDIR 指向它，只扫它与 app、migrations（不扫系统临时目录），结束时删除；范例见 test_account_delete.py。
- 新加记日志的代码或新的第三方依赖：跑 test_log_canaries.py（四种路径的金丝雀值都不能出现在日志里）。

## 禁区
- 测试名用英文蛇形命名；断言要真的检查行为，不写恒真断言，不用固定 sleep 等待。
- 不把 -W error 下出现的警告压掉了事；先找出警告的来源。
- 文档核对测试引用的测试名要与文件里逐字一致；移动或改名测试时同步改交付文档里的引用。
- 每个测试文件不超过 800 行；现有的 test_agent_loop.py 与 test_nutrition_engine.py 超出，由步骤 12 任务 10 拆分，拆之前不要再往里加测试。
