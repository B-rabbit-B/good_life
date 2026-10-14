# good-life 仓库说明书

好生活（good-life）：个人档案驱动的健康生活智能体，只给生活方式建议，不做医疗诊断、不替代医生。后端 FastAPI 加 PostgreSQL，前端是手机浏览器用的 H5，打包后由后端在根路径一并提供。

## 职责
- 本文件写全项目工程规则与顶层说明书索引；说明书分层索引，下一层的索引在各自的上级说明书里。子目录没有单独说明书时，以最近的上级说明书为准。
- 进入任何目录改代码前，先读该目录与上一级目录的 CLAUDE.md；改动改变了某目录的职责、边界、入口或禁区，就在同一个提交里更新那份说明书；新建有说明书的目录时，在最近的上级说明书里加索引，并加进 backend/tests/test_directory_manuals.py 的清单。
- 每份说明书四节固定：职责、边界、入口、禁区；只写代码里看不出来的东西（为什么这样分、不能做什么、从哪里进），不写函数清单，不写时间估计。

## 边界
- 每个文件不超过 800 行（生成的 schema.d.ts、openapi.json、manifest.json 与数据文件除外）；快到上限就按职责拆。
- 依赖只能从上层指向下层：后端分层表见 backend/CLAUDE.md（任务 10 起由 test_import_boundaries.py 守护），前端由 frontend/src/test/boundaries.test.ts 守护；只有登记过原因的例外可以反向。
- 前后端只靠生成的类型对接；前端写死的只有标签映射、流程文案和集中在 frontend/src/lib/contract.ts 的后端文案副本（后端测试逐字核对）。
- “绝不能出错”的规则不只写在代码里：同时写进交付文档并有测试守护（医嘱确认只能本人、风险话题固定回复、密钥只存密文、别人的数据与不存在一样 404）。
- 模型输出要有第二来源或人工兜底，并留审核入口：医嘱提取只产出待确认条目；看图只认菜名与克数，热量营养由营养库算；智能体回答经输出检查，依据只来自营养引擎；SDK 每次调用记审计。
- 医嘱的确认、修改、作废、继续执行与解除只能由用户本人在界面里完成；智能体与 MCP 最多提出解除建议。
- 日志只记方法、路由模板、状态码、能力名、错误码与异常类名，绝不记请求或响应内容、路径参数、查询串、异常文字与堆栈。

## 入口
- backend/CLAUDE.md：后端总览、分层表与各包说明书索引
- backend/tests/CLAUDE.md：后端测试、夹具与测试库
- backend/migrations/CLAUDE.md：数据库迁移
- frontend/CLAUDE.md：前端总览、命令与首屏预算
- frontend/src/CLAUDE.md：前端源码分层与各子目录说明书索引
- frontend/e2e/CLAUDE.md：端到端测试
- frontend/scripts/CLAUDE.md：构建、生成与字体脚本
- docs/CLAUDE.md：文档目录约定
- deploy/ 没有单独说明书：只有 docker-compose 挂载的建库脚本（db-init 建测试库 goodlife_test），改它要同步 README 与 backend/tests/CLAUDE.md。

## 禁区
- 测试不联网、不读 backend/.env、不处理真实密钥；真实服务实测脚本只由用户本人在本机运行。
- 后端 pytest（全量或单文件）与 Playwright 共用测试库 goodlife_test，绝不同时运行。
- 不提交 .env、llm_keys.local.env、任何 *_live_result.md、photo_eval、node_modules、dist、dist-e2e、test-results、.superpowers、.claude 与截图。
- 提交作者用仓库已配置的 B-rabbit-B，不改 git 配置；提交信息最后一段是 Co-Authored-By 行，写执行模型自己的名字。
- 交付文档（docs 下各 NN-交付物）不含代码、命令与反引号，命令只写在 README；计划与步骤文档不写时间估计。
- 先划清模块边界，不拆微服务；新增依赖先核对许可证。
