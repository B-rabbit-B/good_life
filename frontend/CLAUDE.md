# frontend 目录说明书

## 职责
- 手机浏览器用的 H5 前端（React、React Router、TanStack Query、React Aria），只做展示与流程：结论、说明与错误码一律原样显示后端返回的内容，界面不做业务规则判断。
- 构建产物 dist 由后端在根路径提供；开发时 vite 把 /api 代理到 127.0.0.1:8000（lan 模式开 https，供真机调试）。
- 设计依据是 docs/superpowers/design/step11/DESIGN.md（组件、无障碍、敏感区、字体与磨砂规则），改界面前先读相关章节。

## 边界
- 源码分层与各目录见 src/CLAUDE.md；端到端测试见 e2e/CLAUDE.md；构建、生成与字体脚本见 scripts/CLAUDE.md。
- 与后端只靠生成的类型对接：src/api/openapi.json 与 schema.d.ts 由 pnpm api:gen 从后端导出生成并提交（src/api/schema.test.ts 与后端 tests/test_openapi_snapshot.py 守护）。
- 首屏预算（对话路由，gzip）：脚本 150 KB、样式 22 KB、预加载字体 45 KiB、脚本块最多 8 个，pnpm build:check 检查；当前脚本已接近上限，对话路由新增的东西必须很小或按需加载。vite.config.ts 的 common 分组决定哪些共用小模块进同一块，动它前先跑 build:check。
- 动画只用 CSS 与自写的小工具，不引入动画库（eslint 与 src/test/deps.test.ts 禁止）；新增依赖先核对许可证并登记到 deps.test.ts。

## 入口
- 安装与开发：pnpm install、pnpm dev（或 pnpm dev:lan）。
- 每次改前端都跑：pnpm lint、pnpm typecheck、pnpm test 三项零错误，再跑 pnpm build:check。
- 端到端：pnpm e2e（iPhone 13 与 Pixel 7 两种设备的验收流程）、pnpm e2e:pages（390 与 360 宽的页面级检查）、pnpm visual（与设计稿并排截图）。
- 接口变了：pnpm api:gen 并提交两份生成文件；改了固定标题：pnpm fonts 重新生成字体子集（本步骤不新增标题，见 src/lib/CLAUDE.md）。

## 禁区
- 不提交 node_modules、dist、dist-e2e、test-results、playwright-report、blob-report、.font-cache、e2e/.fixtures 与截图。
- 不手改 src/api/schema.d.ts 与 openapi.json；不在前端复制后端规则或常量，确需的副本只放 src/lib/contract.ts。
- Playwright 只访问 127.0.0.1，外网请求一律拦下；不与后端全量 pytest 同时运行（共用测试库）。
- 只用 pnpm 安装依赖，pnpm-lock.yaml 进仓库；依赖版本写确切版本。
