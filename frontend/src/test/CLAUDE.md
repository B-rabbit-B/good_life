# frontend/src/test 目录说明书

## 职责
- Vitest 单元与组件测试的支撑，加几条守护整个前端的测试：
  - setup.ts：MSW 服务器以 onUnhandledRequest error 启动（没写处理器的请求直接让测试失败），每个测试后清理、重置处理器与 localStorage，并补上 jsdom 没有的 matchMedia、IntersectionObserver、ResizeObserver、scrollTo；
  - render.tsx：renderWithProviders、renderRouter、renderRoute，用与 App.tsx 同序的全套 Provider 和不重试的查询客户端；
  - msw/handlers/：按模块模拟后端，按后端的规则回错误码（例如未确认免责时档案与能力清单回 403 disclaimer_not_accepted）；fixtures/：各模块的测试数据，core 默认是档案填满、已确认免责、开放全部模块的女性用户；
  - chat.ts（对话页的公共准备）、frames.ts（requestAnimationFrame 替身）；
  - boundaries.test.ts（源码分层）、deps.test.ts（依赖许可证与禁用动画库）、lint.test.ts（证明 eslint 的禁令确实会报错）。

## 边界
- 只被测试文件引用；boundaries.test.ts 扫描源码时跳过本目录。可以引用 src 下任何层。
- 处理器模拟的是后端的契约，不是界面想要的样子：后端的错误码、说明与状态码变了，这里跟着改，并以后端为准。

## 入口
- 运行：在 frontend 下 pnpm test（全部）或 pnpm exec vitest run 路径（部分）；lint、typecheck、test 三项都要零错误。
- 新模块：在 msw/handlers 加一个文件并在 handlers/index.ts 汇总，测试数据放 fixtures；页面测试用 renderRoute 走真实路由。
- 测试标题只用小写英文字母、数字、空格、逗号、撇号、下划线与连字符，用单引号包住（交付文档按标题逐字引用）。

## 禁区
- 不访问网络，不放宽 onUnhandledRequest；缺处理器就补处理器。
- 不用固定 sleep 等待，用 findBy、waitFor 或 frames.ts 推进；不写恒真的断言。
- 改 boundaries.test.ts 的 ALLOWED 或 COMPONENTS_MAY_USE 必须写明原因，不用它掩盖不该有的依赖。
- 不在测试支撑里复制业务规则（例如自己算能不能吃）；需要结论就在夹具里写死后端会返回的样子。
