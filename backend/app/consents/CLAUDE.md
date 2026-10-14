# consents 包说明书

## 职责
- 经期与医嘱两类敏感个人信息的单独同意（参照个人信息保护法第二十九、三十条，不做正式合规）：文案与版本（content.py）、每用户每类一行的同意记录（sensitive_consents 表）、同意与撤回标记（service.py），以及模块门槛的最后一步 require_consent（deps.py，403 consent_required）。
- 与免责声明分开：免责声明说明建议的性质，这里说明处理的必要性、对个人权益的影响与撤回后果；两者不共用表，正文也不能有相同的句子（tests/test_consents.py 守护）。
- 同意记录时间与文案版本；请求带的版本不是当前版本时 409 consent_outdated。重复同意幂等；撤回过的行重新同意时改写时间与版本、清空撤回时间，不新增行。

## 边界
- 与 disclaimer 同层（第 2 层）：依赖 auth、common、db、disclaimer（路由经 require_disclaimer_user）、errors；不引用任何业务模块。
- 被引用：cycle 与 medical 的 require_*_user 在能力检查之后调用 require_consent，SDK、MCP 与站内智能体都经这两个门槛，所以同一处生效；account 撤回时调用 has_consent 与 mark_withdrawn；演示与实测脚本建用户后调用 grant。
- 撤回不在这里：撤回要同时清除模块数据，放在上层的 account 包；mark_withdrawn 不提交，由调用方与清除放在同一个事务里。
- 已同意的用户不因文案升版失效（has_consent 只看是否撤回）；若将来要求升版后重新同意，要同时改门槛、前端流程与测试。

## 入口
- 路由：GET /api/consents（固定两项，顺序同 CONSENT_KINDS）、POST /api/consents/{kind}（请求体只有 version）。
- 门槛：deps.require_consent；服务：service.get_consent、has_consent、grant、mark_withdrawn、list_statuses。
- 测试：tests/test_consents.py；前端副本 CONSENT_REQUIRED 由 tests/test_frontend_contract.py 按源码原文核对；SDK 归类见 sdk/errors.py 的 CONSENT_HINT。

## 禁区
- 不把单独同意并进免责声明或注册流程，也不默认勾选；改 CONSENT_TEXTS 必须同时改 CONSENT_VERSION。
- 新增需要单独同意的模块时，同时改 CONSENT_KINDS、ConsentKind、门槛、account 的清除与测试，不只改其中一处。
- 并发首次同意靠唯一约束加 IntegrityError 回读，不依赖全局的 409 处理。
- 日志不记同意内容与用户编号。
