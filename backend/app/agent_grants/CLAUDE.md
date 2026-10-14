# agent_grants 包说明书

## 职责
- 用户签发给外部智能体的授权（只读或读写、有效期、吊销）与全部 SDK 调用的审计表 SdkCallAudit。
- 令牌以 gl_ 开头，只存 SHA-256 哈希，明文只在创建时返回一次（TOKEN_NOTICE）；遗失只能吊销重建。每个用户同时有效的授权有上限（MAX_ACTIVE_GRANTS）。
- 审计每次 SDK 调用（含被拒绝的）一行：用户、授权、凭证类型、客户端名、能力名、结果、错误码、耗时；绝不记参数、返回内容、令牌或医嘱正文。审计行由 sdk/audit.py 用独立会话写入，业务回滚不影响审计。

## 边界
- 依赖：auth、common、db、disclaimer、errors。不引用 sdk（方向是 sdk 引用本包：sdk/credentials.py 用 authenticate_grant 认令牌）。
- 审计表的 user_id 可空（未认证的调用没有用户），所以不用 UserOwnedMixin，但查询仍从 owned_by 开始。
- 授权只决定读写级别；需本人确认的医嘱能力不论读写授权都调不到（sdk 只认用户本人的登录令牌）。

## 入口
- 路由：POST 与 GET /api/agent-grants、GET /api/agent-grants/audit、DELETE /api/agent-grants/{id}（router.py），都经 require_disclaimer_user。
- 服务：service.create_grant、list_grants、revoke_grant、authenticate_grant、list_audits、grant_status。
- 测试：tests/test_agent_grants.py、tests/test_sdk_core.py（认证与审计）、tests/test_mcp_server.py。

## 禁区
- 不存、不记、不再次返回令牌明文；日志与错误说明里也不出现令牌或哈希。
- 不往审计表加内容类的列（参数、回答、医嘱文字）；审计只回答“谁、什么时候、调了什么、结果如何”。
- 不放宽：过期或吊销的授权一律当作无效（unauthenticated），不给“快过期还能用”的宽限。
