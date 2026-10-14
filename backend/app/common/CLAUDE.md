# common 包说明书

## 职责
- 各业务包共用、又不属于任何一个业务的底座：
  - ownership.py：UserOwnedMixin（业务表统一的 user_id 外键，删用户级联删除）、owned_by（所有业务查询的起点）、get_owned_or_404；
  - clock.py：get_today 依赖，路由取“今天”都经它，测试里可以换成固定日期；
  - age.py：年龄按“当年减出生年份”算，MIN_AGE 14（不满不服务）、ADULT_AGE 18（未成年规则的分界）；
  - body_limit.py：医嘱证据与餐食照片上传的请求体上限中间件，在鉴权与 multipart 解析之前拦住过大的请求。
- 步骤 12 的请求日志（任务 2 的 request_log.py）也放在这里，加的任务同时更新本说明书。

## 边界
- 位于最底层（与 config、db、errors、security 同层），只能引用同层模块。
- 唯一的登记例外：body_limit.py 从 medical.orders 取 MAX_EVIDENCE_BYTES、从 photos.images 取 MAX_UPLOAD_BYTES，只取常量，让上限只有一处定义；不得再从业务包引用别的东西。
- 被几乎所有业务包引用；main 挂上 UploadBodyLimitMiddleware。

## 入口
- owned_by、get_owned_or_404、UserOwnedMixin、get_today、age_in_years、is_minor、MIN_AGE、UploadBodyLimitMiddleware。
- 测试：归属与 404 散在各模块的交叉用户测试（例如 tests/test_medical_api.py、tests/test_cycle_records.py）；年龄见 tests/test_minors.py；上传上限见 tests/test_medical_api.py 与 tests/test_photo_flow.py。

## 禁区
- 不放业务规则：某个规则只有一个模块用，就留在那个模块里。
- 别人的记录与不存在的记录必须同一个状态码与错误码（404 not_found），不能透露记录是否存在；不要在业务包里另写一套“先查再判断归属”。
- 年龄不另写算法：任何未成年或 14 周岁判断都用 age.py（档案只有出生年份，算出的年龄可能比实际大一岁，这是已接受的取舍）。
- 上传上限不要改成先解析再检查：FastAPI 会先把整个 multipart 读到临时文件，必须在最外层拦。
