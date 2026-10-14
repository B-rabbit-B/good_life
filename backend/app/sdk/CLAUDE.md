# sdk 包说明书

## 职责
- 进程内 SDK（版本 1.2）：把各业务模块的能力封装成“能力名 module.action + 级别 + 输入模型 + 输出类型 + 处理函数”，供站内智能体与 MCP 服务调用。网页接口不经 SDK，SDK 也不挂 HTTP 路由。
- GoodLife.call 的顺序固定：认证凭证 → 查能力 → 级别检查 → 免责门槛 → 模块准入（复用各模块的 require_*_user）→ 校验参数 → 执行 → 按声明类型序列化 → 写审计。用户身份只来自凭证，能力不接受用户编号。
- 三种凭证（credentials.py）：智能体授权令牌（AgentGrantToken，按授权给只读或读写）、站内智能体的服务端凭证（AgentCredential，只能在服务端代码里构造）、用户本人的登录令牌（UserAccessToken，唯一能调用 user_confirmed 级别的凭证）。
- 错误统一成稳定的类别（errors.py 的 ERROR_KINDS）加原业务错误码，并附给智能体的提示。

## 边界
- 依赖：agent_grants、auth、cycle、db、disclaimer、errors、fitness、medical、nutrition、profile、restaurants、security。不引用 agent、mcp_server、llm。
- 被引用：agent（经 tooling.agent_registry 与 AgentCredential 调用）、mcp_server（只做协议转换）、phase 演示与验收脚本。
- tooling.py 是协议无关的工具描述，exposed_capabilities 与 agent_registry 永远去掉 user_confirmed 能力；MCP 与站内智能体共用它。
- MODULES 只有 profile、cycle、medical、nutrition、fitness；附近餐厅挂在 nutrition 下。

## 入口
- 能力定义：capabilities/ 下按模块一个文件，capabilities/__init__.py 的 ALL 汇总；registry.py 校验命名、模块与级别。
- 新增 write 级别的能力（会成为智能体的写入工具）时，必须在 frontend/src/lib/contract.ts 的 WRITE_TOOL_DOMAINS 登记它的工具名与数据域，否则一轮对话后前端不知道让哪些页面刷新；tests/test_frontend_contract.py 的 test_every_write_tool_has_a_frontend_domain 守护。
- 能力清单快照：manifest.json，能力的输入输出有变化时在 backend 目录运行 uv run python -m app.sdk.manifest 并提交，版本号保持 1.2。
- 测试：tests/test_sdk_core.py、test_sdk_capabilities.py、test_sdk_agent_credential.py、test_sdk_docs.py。

## 禁区
- 不新增让模型能确认、修改、作废、继续或解除医嘱的能力；这类能力只能是 user_confirmed 级别，且不出现在 tooling 的任何暴露列表里。
- 不让能力接受用户编号或从参数里取身份；不跳过免责门槛与模块准入。
- 审计不记参数、返回内容与令牌；写审计失败不改变调用结果。
- 不在能力处理函数里另写业务规则：处理函数只调用模块的服务层，与网页接口共用同一套规则。
