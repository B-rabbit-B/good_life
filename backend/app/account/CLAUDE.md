# account 包说明书

## 职责
- 用户处置自己数据的接口。目前只有撤回单独同意：POST /api/account/consents/{kind}/withdraw，同一个事务里清除该模块的全部数据（clearing.py 的 clear_module_data）并记下撤回时间，提交后模块随即关闭（之后的请求是 403 consent_required），返回 204。
- 清除范围：经期删本人的经期记录、每日记录与经期状态；医嘱删本人的全部医嘱单，原件、条目与条目事件随外键级联删除。对话里已有的副本不在清除范围内（同意文案已如实说明）。

## 边界
- 处在最上层（第 10 层，与 main 同层）：依赖 auth、consents、cycle 与 medical 的模型、db、errors；不被任何业务包引用，main 挂载 router。
- 路由只要求登录（get_current_user），不经免责门槛：免责声明升版后、重新确认之前，用户也必须能撤回同意并清除数据；tests/test_route_guards.py 的放行名单里有 /api/account/ 并写明了原因。
- 没有有效同意时撤回是 404 not_found；撤回但保留数据、只停用模块属于明确不做，记入已知问题。

## 入口
- 路由：router.py；清除：clearing.clear_module_data（不提交）。
- 测试：tests/test_consents.py（撤回清除、只影响一个模块与本人、重新同意后模块为空、只要求登录）、tests/test_route_guards.py。

## 禁区
- 不在这里加免责门槛，也不把非本人数据的操作放进来；所有删除都按 user_id 限定在本人。
- 清除与撤回标记必须在同一个事务里提交，不能出现“已撤回但数据还在”或“数据已删但仍显示同意”。
- 新增带用户数据的经期或医嘱表时，同步改 clear_module_data 与测试，否则撤回会留下残余。
- 日志不记路径参数、请求内容与被删数据。
