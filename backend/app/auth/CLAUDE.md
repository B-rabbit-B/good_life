# auth 包说明书

## 职责
- 账号：注册、登录、退出、取当前用户。User 表只有用户名、密码哈希与令牌版本号，健康数据一律放在各业务包。
- get_current_user 是全后端唯一认登录令牌的地方：解出令牌后比对 token_version，退出时版本号加一，所以一次退出让该用户所有已签发的令牌同时失效。
- 注册要求 age_confirmed 为真（确认已年满 14 周岁）；这个字段只做校验、不入库，真正的年龄判断在档案的出生年份上（见 profile 与 common/age.py）。

## 边界
- 依赖：只引用 db、errors、security（密码哈希与令牌）。不引用任何业务包。
- 被引用：几乎所有包都引用 auth.models.User 与 auth.deps.get_current_user；业务路由不直接用 get_current_user，而是用 disclaimer 的 require_disclaimer_user（它建在 get_current_user 之上）。
- 用户名统一转小写后存储与比较；登录失败不区分“用户不存在”和“密码错误”，都回 401 invalid_credentials。
- 限速（limiter.py）：同一个键 15 分钟内失败 5 次后再尝试一律 429 too_many_attempts（即使密码正确）。每次尝试先用 acquire 在同一把锁里判断上限并计数（并发请求不能一起越过上限），成功后 reset 清零；不要拆回“先查、校验后再记失败”的两步。登录的键是“name:用户名”（不存在的用户名同样计数，不能借限速判断账号是否存在），密码复核的键是“user:用户编号”，两者分开。用户不存在时对模块导入时生成的固定假哈希做一次密码校验，消除时间差。
- 计数在进程内（与 restaurants 的检索频率限制同一写法）：多进程或多机部署时各算各的、重启清零，属于已知限制；tests/conftest.py 的 reset_login_limits 在每个测试后清零。

## 入口
- 路由：/api/auth/register、/api/auth/login、/api/auth/logout、/api/auth/me（router.py），只要求登录，不要求免责声明（tests/test_route_guards.py 的放行前缀）。
- 依赖：deps.get_current_user；服务：service.register_user、login、logout、verify_user_password（导出与删除账号前复核本人密码，错了是 403 password_incorrect，由 account 调用，同样限速）；限速：limiter.acquire、reset、reset_all。
- 测试：tests/test_auth.py、tests/test_minors.py（注册的年龄确认）、tests/test_route_guards.py、tests/test_hardening.py（限速与假密码校验）。

## 禁区
- 不在这里加业务门槛（免责、模块开放、单独同意）：那些在 disclaimer、profile 与各模块的 deps 里。
- 不把密码、令牌或令牌哈希写进日志、错误说明或响应；错误说明不透露账号是否存在。
- 不另造第二套令牌校验：SDK 的用户令牌也走 security.tokens 加 token_version 比对，保持与这里一致。
- 限速的拒绝不另写日志（请求日志已记方法、路由模板与 429）；不要把用户名或用户编号写进日志。
- 401 只用于“没登录或登录失效”（前端据此清令牌回登录页）；密码复核错误之类的情形不要用 401。
