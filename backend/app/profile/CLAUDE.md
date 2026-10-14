# profile 包说明书

## 职责
- 个人档案（性别、出生年份、身高体重、活动水平、目标、饮食偏好与忌口、健康状况、备注、是否关闭经期记录）与档案修改记录。每次修改把新旧值写进 ProfileChange（加密），便于追溯。
- capabilities.py 的 compute_capabilities 是“哪些模块向该用户开放”的唯一来源：经期只对女性且未关闭经期记录的用户开放，医嘱、饮食、健身对所有人开放。
- 出生年份不得使算出的年龄小于 14 周岁（422，UNDER_AGE_MESSAGE）；已有的未满 14 周岁的旧档案仍可修改其他字段。

## 边界
- 依赖：auth、common、db、disclaimer、security。
- 被引用：cycle、medical、nutrition、fitness 的模块门槛（deps.py）都调用 compute_capabilities；nutrition 的上下文、agent 的装配与 restaurants 读档案；sdk 的 profile 能力。
- 档案里的忌口与饮食偏好是用户自填的口味取舍，属于软约束；医嘱约束只从 medical 读，二者不能互相替代。

## 入口
- 路由：GET 与 PATCH /api/profile、GET /api/profile/changes、GET /api/me/capabilities，都经 require_disclaimer_user。
- 服务：service.get_or_create_profile（并发首次请求安全）、update_profile、list_profile_changes。
- 测试：tests/test_profile.py、tests/test_minors.py；SDK 侧见 tests/test_sdk_capabilities.py。

## 禁区
- 不在别处重复写模块开放规则：前端、SDK、智能体都以 compute_capabilities 的结果为准，改规则只改这一处。
- 不用档案的忌口冒充医嘱：任何“绝不能吃”的结论只能来自已确认的医嘱条目。
- 健康状况、身高体重、备注与修改记录必须保持加密列；不要为了查询方便改成明文。
- 未成年判断不另写算法，用 common/age.py。
