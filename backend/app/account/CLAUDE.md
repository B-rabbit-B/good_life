# account 包说明书

## 职责
- 用户处置自己数据的接口：撤回单独同意并清除模块数据、导出全部数据、删除账号。
- 撤回：POST /api/account/consents/{kind}/withdraw，同一个事务里清除该模块的全部数据（clearing.py 的 clear_module_data）并记下撤回时间，提交后模块随即关闭（之后的请求是 403 consent_required），返回 204。清除范围：经期删本人的经期记录、每日记录与经期状态；医嘱删本人的全部医嘱单，原件、条目与条目事件随外键级联删除。对话里已有的副本与开场问候不在清除范围内（同意文案已如实说明，可用智能体的“清空全部对话”一并清掉）。
- 导出：POST /api/account/export，重新输入密码后在内存里生成压缩包（export.py 的 build_export）：每个模块一份 JSON、evidence 文件夹放医嘱原件、photos 文件夹放保留的照片、一份中文说明.txt。各模块内容用对应读取接口的同名响应模型与同一个组装函数序列化（所以直接引用了各模块 router 里的 _order_out、_meal_out、_workouts_out 等），与界面逐项一致；接口有条数上限的部分这里导出全部，另加对话的工具调用与结果、开场记录。响应禁止缓存，成功后记一行审计 account.export（凭证类型 user_session、客户端名 app）。
- 删除账号：POST /api/account/delete，重新输入密码并勾选确认后，deletion.py 锁住用户行、执行一条 DELETE FROM users，全部数据随外键级联在同一事务里删除，返回 204；不做冻结期与软删除，不可恢复。登录令牌因用户行不存在而失效，智能体授权与审计随账号一起删除。
- 密码复核用 auth.service.verify_user_password：错了是 403 password_incorrect（不是 401，401 会让前端清令牌）。

## 边界
- 处在最上层（第 10 层，与 main 同层）：依赖 auth、consents、各业务模块的模型、服务与 router 里的组装函数、sdk.audit、db、errors；不被任何业务包引用，main 挂载 router。
- 路由只要求登录（get_current_user），不经免责门槛：免责声明升版后、重新确认之前，用户也必须能撤回同意、导出与删除自己的数据；tests/test_route_guards.py 的放行名单里有 /api/account/ 并写明了原因。
- 没有有效同意时撤回是 404 not_found；撤回但保留数据、只停用模块属于明确不做，记入已知问题。
- 删除不在这里逐表删：依靠每张带 user_id 的表对 users 的 ON DELETE CASCADE；tests/test_cascade_guard.py 从数据库实际结构（pg_catalog）检查，新增带 user_id 的表没有级联就失败。

## 入口
- 路由：router.py；清除：clearing.clear_module_data（不提交）；导出：export.build_export、EXPORT_FILES、README_NAME；删除：deletion.delete_account（提交）。
- 测试：tests/test_consents.py（撤回清除、只影响一个模块与本人、重新同意后模块为空、只要求登录）、tests/test_account_export.py（与各读取接口逐项一致、原件与照片、不含哈希令牌密钥与他人数据、不缓存与审计）、tests/test_account_delete.py（双用户逐表、密码与勾选、令牌与授权失效、磁盘无残留、日志不带内容）、tests/test_cascade_guard.py、tests/test_route_guards.py。

## 禁区
- 不在这里加免责门槛，也不把非本人数据的操作放进来；所有查询与删除都按 user_id 限定在本人。
- 导出不得含 password_hash、token_version、授权的 token_hash、模型服务的 api_key 原文，也不得含别人的数据；原始文件名只写在 medical.json，压缩包条目名只由编号与扩展名组成。
- 导出与删除全程在内存与数据库里完成，不写临时文件；不改成先落盘再打包。
- 某个模块的读取接口改了响应模型或组装方式，导出跟着用同一个函数，不在这里另写一份；新增带用户数据的模块要同时加进导出与说明.txt。
- 清除与撤回标记必须在同一个事务里提交，不能出现“已撤回但数据还在”或“数据已删但仍显示同意”；新增带用户数据的经期或医嘱表时，同步改 clear_module_data 与测试。
- 日志只记“账号导出完成”“账号已删除”与请求日志的方法、路由模板、状态码；不记用户名、路径参数、请求内容与被删或被导出的数据。
