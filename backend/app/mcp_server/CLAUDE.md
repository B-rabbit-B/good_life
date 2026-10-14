# mcp_server 包说明书

## 职责
- 本地 stdio MCP 服务：把 SDK 暴露的能力换成 MCP 工具（能力名里的点换成下划线），让任何支持 MCP 的客户端代表一位用户调用。
- 这里只做协议转换：认证、级别、模块准入、参数校验与审计全部交给 sdk.GoodLife.call；结果与错误都按 SDK 的信封原样返回（错误时 is_error 为真）。
- INSTRUCTIONS 告诉客户端模型：工具只代表令牌对应的用户；给建议前先读医嘱约束；医嘱的确认与解除只能由用户本人在应用里完成；只有用户明确要求时才写入。

## 边界
- 依赖：只引用 sdk（GoodLife、AgentGrantToken、SdkError、tooling）。不引用任何业务包。
- 不被 main 挂载，是单独的进程：凭证只来自环境变量 GOODLIFE_AGENT_TOKEN（用户在设置里创建的智能体授权令牌），客户端名来自 GOODLIFE_CLIENT_NAME，进审计。
- 工具列表来自 sdk.tooling.exposed_capabilities，永远不含 user_confirmed 能力；查不到的工具名也交给 SDK，由它回 unknown_capability 并记审计，任何工具名都到不了需本人确认的能力。

## 入口
- 启动：在 backend 目录运行 uv run python -m app.mcp_server（__main__.py → server.main）；build_server 供测试注入 SDK 与凭证。
- 测试：tests/test_mcp_server.py；工具清单的交付文档由 tests/test_sdk_docs.py 核对。

## 禁区
- 不在这里加认证、权限或业务逻辑，也不直接访问数据库；需要的规则加在 sdk 或业务模块。
- 不接受用户编号或其他身份参数；不接受登录令牌（用户本人的令牌不交给外部客户端）。
- 日志只写到标准错误，标准输出是协议通道，不能打印任何东西；日志里不带参数与返回内容，只按全项目日志规则记工具名与异常类名。
