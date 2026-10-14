# disclaimer 包说明书

## 职责
- 免责声明的文案与版本（content.py 的 DISCLAIMER_TEXT、DISCLAIMER_VERSION）、用户的确认记录，以及全后端业务接口的总门槛 require_disclaimer_user：已登录且已确认当前版本，否则 403 disclaimer_not_accepted。
- 文案升级时改版本号，所有用户都要重新确认；确认请求带的版本不是当前版本时回 409 disclaimer_outdated。

## 边界
- 依赖：auth（取当前用户）、common、db、errors。
- 被引用：profile、cycle、medical、nutrition、fitness、llm、agent_grants、agent 的路由都经它（或经建在它上面的模块门槛）；sdk 的每次调用也先过它（client.py 里 require_disclaimer_user）；演示脚本用 service 直接写确认记录。
- 单独同意（consents 包）与本包同层，是另一回事：同意记录的是经期与医嘱两类敏感数据的处理授权，不复用这里的表；consents 的路由建在本包的门槛上。

## 入口
- 路由：GET /api/disclaimer（文案与版本，不要求登录）、GET /api/disclaimer/status、POST /api/disclaimer/accept（只要求登录）。
- 门槛：deps.require_disclaimer_user；服务：service.get_current_acceptance、accept。
- 测试：tests/test_disclaimer.py、tests/test_route_guards.py（每个业务路由都要经过这个门槛）。

## 禁区
- 新增业务路由不能绕过 require_disclaimer_user；只有 /api/auth/、/api/disclaimer、/api/health 与 /api/account/（用户处置自己数据，免责升版后也要能撤回同意并清除数据）在放行名单里，扩大放行名单要有书面理由并改 test_route_guards.py。
- 不把文案拆散到前端：前端显示的是接口返回的原文与版本。
- 改 DISCLAIMER_TEXT 必须同时改 DISCLAIMER_VERSION，并检查交付文档里逐字引用文案的地方。
