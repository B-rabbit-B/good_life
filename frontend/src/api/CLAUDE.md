# frontend/src/api 目录说明书

## 职责
- 前端与后端之间的唯一通道：请求、错误、令牌、查询键、缓存失效与各模块的 TanStack Query 钩子。
- client.ts：每个请求带令牌，把后端的 {"error": {"code", "message", "details"}} 解析成 ApiError；401 且错误码是 not_authenticated 或 invalid_token 时清令牌并通知外壳回登录页、清缓存（登录接口的 invalid_credentials 不在此列）。
- sse.ts 用 fetch 读对话的事件流；upload.ts 用 XMLHttpRequest 上传照片（为了上传进度）；两者都套用 client.ts 的同一套错误与 401 规则。
- keys.ts 是按模块分层的查询键；invalidation.ts 是“写了哪个数据域、哪些查询跟着失效”的唯一表，页面的写操作与智能体的写入工具都按它失效。
- openapi.json 与 schema.d.ts 是生成文件，types.ts 只给它们起别名；itemContext/ 是对话页与医嘱页共用的条目上下文（到期原因、提出人）。

## 边界
- 依赖：只引用 lib 与自己；不引用 app、components、features（test/boundaries.test.ts 守护）。
- 被引用：app、components（只取 ApiError 类型等）、features、test。
- hooks/ 按模块分文件；只有医嘱页用的钩子放 hooks/medicalPage.ts，对话页也用的放 hooks/medical.ts，免得医嘱页的代码进对话页首屏（vite.config.ts 的 common 分组也按这个分）。

## 入口
- api()、ApiError、networkError、isSessionEnded、onUnauthorized（client.ts）；qk（keys.ts）；invalidateDomain（invalidation.ts）；hooks/ 下的 useXxx。
- 生成：在 frontend 运行 pnpm api:gen，提交 openapi.json 与 schema.d.ts；schema.test.ts 检查生成结果是最新的。
- 测试：client.test.ts、errors.test.ts、sse.test.ts、upload.test.ts、keys.test.ts、invalidation.test.ts、hooks/hooks.test.tsx、hooks/domainInvalidation.test.tsx、itemContext/dueReason.test.ts。

## 禁区
- 不手改 schema.d.ts、openapi.json；类型一律取自生成文件，不手写接口类型。
- 不在钩子里加业务判断或改写后端的 message；错误原样交给界面显示。
- 写操作不要自己挑查询键失效，改 invalidation.ts 的表并补测试（漏一处别的页面就显示旧数据）。
- 不用 EventSource；令牌只经 token.ts 读写，不放进地址或日志。
