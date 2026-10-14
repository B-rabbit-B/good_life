# auth 包说明书

## 职责
- 账号：注册、登录、退出、取当前用户。User 表只有用户名、密码哈希与令牌版本号，健康数据一律放在各业务包。
- get_current_user 是全后端唯一认登录令牌的地方：解出令牌后比对 token_version，退出时版本号加一，所以一次退出让该用户所有已签发的令牌同时失效。
- 注册要求 age_confirmed 为真（确认已年满 14 周岁）；这个字段只做校验、不入库，真正的年龄判断在档案的出生年份上（见 profile 与 common/age.py）。

## 边界
- 依赖：只引用 db、errors、security（密码哈希与令牌）。不引用任何业务包。
- 被引用：几乎所有包都引用 auth.models.User 与 auth.deps.get_current_user；业务路由不直接用 get_current_user，而是用 disclaimer 的 require_disclaimer_user（它建在 get_current_user 之上）。
- 用户名统一转小写后存储与比较；登录失败不区分“用户不存在”和“密码错误”，都回 401 invalid_credentials。
- 步骤 12 计划在这里加登录限速（任务 8 的 limiter.py）；加的任务同时更新本说明书。

## 入口
- 路由：/api/auth/register、/api/auth/login、/api/auth/logout、/api/auth/me（router.py），只要求登录，不要求免责声明（tests/test_route_guards.py 的放行前缀）。
- 依赖：deps.get_current_user；服务：service.register_user、login、logout、verify_user_password（导出与删除账号前复核本人密码，错了是 403 password_incorrect，由 account 调用；任务 8 再加限速）。
- 测试：tests/test_auth.py、tests/test_minors.py（注册的年龄确认）、tests/test_route_guards.py。

## 禁区
- 不在这里加业务门槛（免责、模块开放、单独同意）：那些在 disclaimer、profile 与各模块的 deps 里。
- 不把密码、令牌或令牌哈希写进日志、错误说明或响应；错误说明不透露账号是否存在。
- 不另造第二套令牌校验：SDK 的用户令牌也走 security.tokens 加 token_version 比对，保持与这里一致。
- 401 只用于“没登录或登录失效”（前端据此清令牌回登录页）；密码复核错误之类的情形不要用 401。
