# frontend/e2e 目录说明书

## 职责
- Playwright 端到端测试，连真实后端与测试库：
  - acceptance/：验收流程，被验收的动作只经界面操作（前置数据可经 support/api.ts 的真实接口准备，新用户流程从注册起全程走界面），在两种设备上各跑一遍（项目 iphone-13 是 WebKit 模拟 iPhone 13，pixel-7 是 Chromium 模拟 Pixel 7）；
  - pages/：页面级检查（项目 layout-390 与 layout-360，手机宽度的 Chromium），数据经 support/api.ts 用后端真实接口准备；
  - visual/：与设计稿 docs/superpowers/design/step11/index.html 并排截图到 test-results/visual，供人比对，不做像素断言；
  - support/：test.ts（统一的 test 与 expect，自动装外网拦截）、net.ts（拦截与死代理）、api.ts（经接口准备数据）、flows.ts（验收共用的界面步骤）、a11y.ts（自写的版式、触控尺寸与敏感区断言）、pixels.ts、visual.ts。

## 边界
- 服务器：playwright.config.ts 的 webServer 运行 scripts/e2e-server.mjs，先构建 dist-e2e（带 VITE_GALLERY=1），再在后端目录启动 app.e2e_server（127.0.0.1:8765）。它启动时把 goodlife_test 迁移到最新并清空全部表，模型、看图模型与高德都是本机模拟服务，密钥是演示用假密钥。
- workers 固定为 1、不并行：全部测试共用一个测试库。后端全量 pytest 与 Playwright 绝不同时运行。
- 外网请求：Chromium 上用路由拦截，除 127.0.0.1 与本地 file 外一律 abort 并记录，非本机 WebSocket 直接关闭；WebKit 例外，改用死代理（127.0.0.1 上没有服务的 9 号端口，外网请求连接被拒），因为 WebKit 里拦截后转发的 multipart 上传会丢掉文件内容。死代理端口上若有服务在听，测试直接报错停下。
- 敏感区核对用 support/a11y.ts 的 expectSensitiveAreas，名字表直接引入 src/app/sensitiveAreas.ts。

## 入口
- 在 frontend 下：pnpm e2e（验收，两种设备）、pnpm e2e:pages（页面级）、pnpm visual（截图）；首次需安装 chromium 与 webkit 浏览器。
- 测试数据图片由 e2e_server 启动时写到 e2e/.fixtures（不提交）。
- 测试标题规则与 Vitest 相同（小写英文、单引号），交付文档按标题逐字引用。

## 禁区
- 不直接从 @playwright/test 引入 test（eslint 禁止），一律从 support/test 引入，否则外网拦截不会装上。
- 不访问 127.0.0.1 以外的地址，不用真实密钥，不读 backend/.env。
- 不直接写数据库，数据准备一律经后端真实接口；验收流程里被验收的那一步不能用接口代替界面操作。
- 不提交 test-results、playwright-report、blob-report、.fixtures 与截图；不用固定等待，用 expect 的自动重试或 expect.poll。
