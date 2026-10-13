# 步骤 11 前端 H5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仓库根目录新建 `frontend/`，用 Vite + React + TypeScript 做一个以聊天为中心的手机浏览器 H5 应用，让用户只靠界面完成注册、确认免责、建档、聊天、拍照识别入库、饮食与训练记录、经期、医嘱核对与解除、附近餐厅、模型配置与隐私设置；视觉按“影青”设计稿实现；后端随本步骤补四处小改动并在根路径提供打包后的前端。满足 `docs/11-前端H5.md` 的 9 条验收标准（第 6 条真机部分由用户补测，本步骤预计有条件通过）。

**Architecture:** 单页应用，React Router 按路由拆包，TanStack Query 管接口数据，接口类型由 openapi-typescript 从后端接口描述的快照生成。行为与无障碍来自 react-aria-components，样式全部自写，类名与令牌沿用设计稿 `index.html`。材质分四层（瓷胎、静玻璃、活玻璃、厚玻璃），默认实色、支持时升级为玻璃，由 `GlassModeProvider` 统一降级。外壳（导航、对话底座、操作坞、面板）挂在 `#shell-root`，内容在唯一的滚动容器里。开发时 Vite 把 `/api` 转发给本机后端；上线时后端在根路径提供 `frontend/dist` 并对前端路由回退到首页。端到端测试由 `app.e2e_server` 启动测试库上的真实后端与本地模拟的模型、看图模型、高德。

**Tech Stack:** Node 22、pnpm 12、Vite、React 19、TypeScript（strict）、React Router 7、TanStack Query 5、react-aria-components 与 @internationalized/date、Vitest、React Testing Library、MSW 2、ESLint 9 与 typescript-eslint、openapi-typescript 7、Playwright；后端 Python 3.12、FastAPI、pytest。字体用 pyftsubset（fonttools，经 uvx 临时运行，不进项目依赖）生成子集。

**Spec:** `docs/superpowers/specs/2026-10-12-step11-frontend-design.md`（需求的最终依据）与 `docs/superpowers/design/step11/DESIGN.md`、`docs/superpowers/design/step11/index.html`（视觉、令牌、组件、动效、字体与无障碍的最终依据；`*-paper-ink.*` 是已归档的旧稿，不看）。步骤文档 `docs/11-前端H5.md`。执行者开工前必须读完这三份，每个界面任务还要在浏览器里打开 `index.html` 看对应的画面。

## Global Constraints

- 只在当前分支 `step11-frontend` 上工作；不建分支、不合并。
- 平台是 Windows 11，终端 PowerShell 5.1（不支持 `&&`，用 `;` 或分两次执行）；也可以用 Bash 工具。
- 后端命令在 `E:\workspace\good-life\backend` 下统一用 `uv run ...`；后端全量测试 `uv run pytest -q -W error` 必须零失败、零警告，耗时约 10 分钟，工具调用超时设 600000 毫秒；不要用 pytest 的 tmp_path，需要临时目录用 `tempfile`。
- 数据库 `127.0.0.1:5433`，测试库 `goodlife_test`；Docker 未启动时先启动 `C:\Users\Administrator\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`，再在仓库根目录执行 `docker compose up -d --wait db`。
- 端到端测试同样使用 `goodlife_test` 并在启动时清空全部表，所以 Playwright 与后端 pytest 不得同时运行。
- 前端命令在 `E:\workspace\good-life\frontend` 下用 pnpm（Node 22、pnpm 12 已安装）；只用 pnpm 安装依赖，`pnpm-lock.yaml` 进仓库。
- 前端测试标题（`it`、`test` 的第一个参数）只用小写英文字母、数字、空格、逗号、撇号、下划线与连字符，用单引号包住，便于验收记录逐字引用。
- TypeScript 用 `strict: true` 与 `noUncheckedIndexedAccess: true`；`pnpm lint`（ESLint，`--max-warnings 0`）、`pnpm typecheck`（`tsc --noEmit`）、`pnpm test`（`vitest run`）三项都必须零错误；每个任务提交前跑这三项，后端有改动的任务再跑后端全量。
- 测试绝不访问真实网络：Vitest 用 MSW，`onUnhandledRequest: "error"`；Playwright 只访问 `127.0.0.1`，其他地址一律拦下并记录（Chromium 用 `route.abort()`；WebKit 因 Playwright 路由会丢掉上传表单的文件内容，改为把代理指向本机未监听端口，使外网请求连接失败，并在 afterEach 断言没有发往本机以外的请求）；模型、看图模型、高德只用 `app.e2e_server` 启动的本地模拟服务（复用 `app/phase2_acceptance.py` 的 `_AcceptanceModel`、`_MockAmap` 与 `app/phase2_demo.py` 的 `_Handler`）。
- 新依赖只允许 MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause，由 `src/test/deps.test.ts` 读 `node_modules` 里的许可证字段检查；全部写进 `docs/01-交付物/依赖许可证.md` 新增的“五、前端依赖（步骤 11）”一节（版本、用途、许可证、能否商用）。
- 字体 Noto Serif SC 与 Source Serif 4（OFL-1.1）是 DESIGN.md 第八节允许的资源例外，列在同一节的“字体资源”表；不用 axe-core 及其包装（MPL-2.0），无障碍检查用本计划里的自写断言。
- 不引入任何动画库（framer-motion、motion、gsap、react-spring、@react-spring/*、animejs、react-bits）；动效只用 CSS 与 Web Animations API，只动 transform 与 opacity，模糊半径永不做动画。
- 不拷贝 React Bits 的任何代码（MIT 加 Commons Clause）；实现者不得打开其源码；CountUp、StatusMark、ThoughtLine 与刻度尺拖动只按 DESIGN.md 第五、六、八节的行为描述自写（净室）。
- 需要用户许可的下载：Playwright 浏览器（`pnpm exec playwright install chromium webkit`）与两个字体源文件；实现者先向控制者报告文件名、来源与大小，用户同意后才下载。经 pnpm 与 uvx 从官方注册表安装软件包不在此列。
- 界面文字全部是中文；界面不做业务规则判断：结论、依据、提示、说明与错误码一律原样显示后端返回的内容。
- 前端写死的只有标签映射（枚举到中文）、流程文案与后端固定文案的副本；副本集中在 `src/lib/contract.ts`，由后端测试 `tests/test_frontend_contract.py` 守护。
- 令牌存 localStorage 键 `goodlife.token`，每个请求带 `Authorization: Bearer <token>`；收到 401 且错误码为 `not_authenticated` 或 `invalid_token` 时清令牌、清查询缓存并跳到 `/login`（显示“登录已过期”）；登录接口的 401 `invalid_credentials` 只在表单里提示。
- 密钥只显示后端返回的 `key_hint`；前端从不把密钥写进 localStorage、sessionStorage、查询缓存、URL 或日志；保存成功或离开表单时清空密钥输入框。
- 聊天流式读取用 `fetch` 加 `ReadableStream` 自写 SSE 解析；禁用 `EventSource`（ESLint `no-restricted-globals`）；非 200 的 `text/event-stream` 错误响应也要读出 `error` 事件。
- 令牌与数值以设计稿为准：`index.html` 顶部 `:root` 的全部变量原样搬进 `src/styles/tokens.css`；圆角只用 `--r-1` 6、`--r-2` 10、`--r-3` 16、`--r-4` 22、`--r-5` 28、`--r-pill` 999；间距只用 4、8、12、16、20、24、32、48；页边 20，面板外边 12、内边 16。
- 类名沿用设计稿（`.plate`、`.rnav`、`.slab`、`.stick`、`.sheet`、`.btn`、`.btn-pri`、`.ref`、`.vd`、`.sens` 等），新组件的样式写在 `src/styles/components/*.css`，由对应组件文件 import。
- 玻璃预算：同屏模糊层平时 2 层、上限 3 层；外壳模糊 16、面板 24、饱和度不超过 1.4；模糊总面积不超过视口 40%；滚动内容不用 backdrop-filter；玻璃里不再放玻璃；轻提示与面板互斥。
- 外壳（导航、对话底座、操作坞、面板、轻提示）一律渲染进 `#shell-root`（`index.html` 里与 `#root` 同级），不得放进任何 `overflow: hidden` 的容器。
- 降级：默认写实色；只有在 `@supports ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px)))` 内且根节点 `data-glass="on"` 时才升级为玻璃，两个属性同时写。
- `data-glass="off"` 的来源：系统 `prefers-reduced-transparency: reduce`、“减少透明”设置、低端机判定；用户的“减少透明”设置（跟随系统、开、关）永远优先于自动判定；面板打开时根节点设 `data-sheet-open`，遮罩下的外壳关模糊。
- 强制颜色：`@media (forced-colors: active)` 按 DESIGN.md 第八节第 4 条与 `index.html` 第 803 至 851 行的规则实现（真边框、导航当前项用描边、就医提示 3 像素边框、图形标记 `forced-color-adjust: none` 后用系统色重画）。
- 全站最小字号 12 像素（用 rem）；所有触控目标宽高不小于 44（36 高的小按钮与胶囊用伪元素把点按区补到 44，并带 `data-hit44` 属性供检查）。
- 焦点环 2 像素钴蓝、外移 2 像素；活玻璃上最浅只用 `--ink-2`；`--ink-4` 只画刻度；直接写在背景场上的文字用 `--ink-2` 或更深，钴蓝文字按钮落在背景场上时加 `.on-field` 底。
- 最低引擎：iOS Safari 16、Chromium 107；Vite `build.target` 为 `['safari16', 'chrome107']`；`inert` 不可用时回退为子树里的可聚焦元素临时设 `tabindex=-1`，取消时恢复原值。
- 遮盖：`Sensitive` 用不透明斜纹（`#EEF3FA` 底、`#C2CFE2` 1.5 像素斜纹），绝不用 `backdrop-filter` 或 `filter: blur`；遮盖时同时设 `aria-hidden="true"` 与 `inert` 并播报“已遮盖”；应用切到后台再回来时默认遮盖；斜纹层级 4，外壳层级 8。
- 减弱动效：CSS 在 `prefers-reduced-motion: reduce` 下把动画与过渡时长压到 1 毫秒；脚本驱动的计数与流式在开始前读 `matchMedia` 并监听变化。
- 字体只用两个自托管子集：思源宋体 700（只用于写死的标题，子集上限 40 KB）与 Source Serif 4 500（16 号以上的数字）；文件放 `public/fonts/`，同源提供，`font-display: swap` 并 preload；运行时不请求任何外部字体服务；正文用 DESIGN.md 的系统黑体栈。
- 首屏预算（对话路由，gzip 后）：脚本 150 KB、样式 22 KB、预加载字体 45 KiB（46,080 字节，控制者在任务 2 中裁定：固定标题实测 218 字，宋体子集 40,864 字节）；累计布局偏移不超过 0.05；由 `pnpm build:check` 检查。
- 交付文档（`docs/11-交付物/` 下）不含代码、命令、反引号或代码块。
- 每个任务结束提交一次；提交信息最后一段是 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（Opus 5.5 实现者；其他模型写自己的名字）；作者已配置为 `B-rabbit-B <B-rabbit-B@users.noreply.github.com>`，不改 git 配置。
- 不得提交：`backend/.env`、`.superpowers/`、`*.local.env`、`*_live_result.md`、`photo_eval/`、`frontend/node_modules/`、`frontend/dist/`、`frontend/dist-e2e/`、`frontend/test-results/`、`frontend/playwright-report/`、`frontend/blob-report/`、`frontend/.font-cache/`、`frontend/e2e/.fixtures/`、任何截图，以及 `docs/superpowers/design/step11/` 下未跟踪的截图目录。
- 不读 `backend/.env` 里的真实密钥；前端测试与端到端测试只用模拟服务认的假密钥（`app.phase2_demo.DEMO_MODEL_KEY`、`app.phase2_acceptance.DEMO_AMAP_KEY`）。

## 已定的取舍（规格与设计稿没写死、或与后端现状冲突的地方）

| 问题 | 决定 | 理由 |
|---|---|---|
| “档案未填完”如何判断 | `isProfileComplete(profile)`：`gender`、`birth_year`、`height_cm`、`weight_kg`、`activity_level`、`goal` 都不为 null（第三步可跳过） | 后端没有“建档完成”字段；这六项正是建档前两步收集的内容，是流程判断，不是业务规则 |
| 待复核的到期原因 | 取该条目最近一条 `action == "review_due"` 事件的 `detail.reason`（`GET /api/medical/items/{id}/events`）原样显示；面板里“触发复核的一项”按 `contract.ts` 的 `DUE_REASONS` 把这四句原文映射到复查日期或预计结束 | `ItemOut` 没有到期原因；不在前端重算到期规则 |
| 解除建议由谁提出 | 取最近一条 `resolution_proposed` 事件的 `source`（agent 为“助手”，user 为“你”） | `ItemOut` 只有建议时间与理由 |
| 助手正文里的医嘱提醒与免责句 | 后端把回答、医嘱提醒（以“按你当前生效的医嘱，以下食物不建议：”开头）与 `HEALTH_DISCLAIMER` 用空行拼在 `text` 里；前端用 `splitAssistantText` 按这两段固定文案切开，提醒画成系统附注便笺，免责句画在“仅供参考”旁 | 不改后端接口；固定文案由 `test_frontend_contract.py` 守护 |
| 重试会重复保存用户消息 | 后端在跑一轮之前就保存用户消息，没有删除接口；重试即重发同一句话；显示时 `collapseRetriedUserMessages` 把“紧接着重复的同一句用户消息”只显示一次；`MessageOut.id` 用作列表键并把流式气泡换成持久化的消息 | 不新增接口 |
| 开场卡片对应哪条医嘱 | `review_due` 开场对应 `GET /api/medical/reviews` 的第一条（与后端 `_review_due` 取 `reviews[0]` 一致）；该条是待复核时给“继续遵守、去医嘱页处理、稍后”，是带建议的生效条目时只给“去医嘱页处理、稍后” | `OpeningOut` 不带条目编号；后端的开场可能被只带建议的条目触发，见文末“需要关注” |
| 经期“数据不足”的进度 | 原样显示 `prediction.notes`，再写“已记录 N 个完整周期”（`stats.cycle_count`）；不画“1 / 2”的进度条 | 分母是后端规则常量，前端不复制 |
| 营养表“医嘱上限” | 钠一行写“上限”（`needs.sodium_mg_max`），`remaining.sodium_mg <= 0` 时整行转赭色；“还差”只显示后端给了 `remaining` 的三项，其余写“—” | 后端的需求估算不读医嘱，不能写“医嘱上限”，也不在前端定“接近”的阈值 |
| 训练汇总的时间窗 | 用“本周”（周一到周日，`GET /api/fitness/summary/week` 不带 start）；七根柱按 `GET /api/fitness/workouts?start=<本周一>&end=<本周日>` 汇总每天的时长 | 周汇总接口要求开始日是星期一 |
| 动作检索时的冲突提示 | 检索结果不提示冲突；保存后的训练行显示 `WorkoutOut.conflicts` 的说明原文 | 后端只在训练记录上判断冲突 |
| 录入医嘱的“不提取，手动填写一条” | 录入页改为说明“提取后可以逐条修改，也可以在待核对里手动补充一条”；手动补充放在待核对每组来源下（`POST /api/medical/orders/{id}/items`） | 手动条目必须挂在一份医嘱上，单独建一份会再跑一次提取、产生重复条目 |
| 外部授权 | 隐私页只列出授权并可吊销，不在界面上创建授权 | 创建会显示一次令牌明文，与“密钥只显示掩码”冲突；创建方式仍按 README 第 14 节 |
| 导出与删除数据 | 本步骤不做入口 | 后端没有接口，属于步骤 12 |
| 拍照“识别完成后会出现在对话里” | 04a 的说明改为“可以离开这一页，识别完成后可在拍照页的‘未处理的草稿’里继续” | 识别结果不会进对话 |
| 已连通标记 | 模型服务列表不保存连通状态；每个服务给一个“测试连通”文字按钮，本次测试的结果用结论标记显示 | `ProviderOut` 没有连通状态 |
| 免责声明“关键句加粗” | 原样分行显示后端正文，不加粗 | 后端正文没有标记，前端不自行挑句子 |
| 生效中且无建议的条目 | 行内给“修改”与“确认解除”两个小按钮（07a 第三条未画按钮） | 解除面板的“取消”分支需要一个入口 |
| 识别项的“推荐”字样 | 结论标记统一用“适合、注意、不建议、未核对” | 全站一个说法 |

## 文件结构

```
backend/app/
├── frontend_static.py          # 任务 1：mount_frontend，SPA 回退
├── openapi_export.py           # 任务 2：导出接口描述
├── e2e_server.py               # 任务 2：端到端测试用的后端与模拟服务
├── agent/schemas.py、agent/router.py              # 任务 1：MessageOut.id
├── agent_grants/router.py、agent_grants/service.py # 任务 1：client_name 筛选
├── medical/schemas.py、medical/router.py、medical/items.py  # 任务 1：GET /api/medical/events
├── config.py、main.py          # 任务 1
backend/tests/
├── test_step11_backend.py、test_frontend_static.py         # 任务 1
├── test_openapi_snapshot.py、test_e2e_server.py           # 任务 2
├── test_frontend_contract.py                               # 任务 4
├── test_frontend_docs.py                                   # 任务 12
frontend/
├── package.json、pnpm-lock.yaml、index.html、vite.config.ts、tsconfig.json、tsconfig.node.json
├── eslint.config.js、playwright.config.ts、.env.e2e、.gitignore
├── scripts/  gen-api.mjs、gen-api-lib.mjs、gen-api-lib.d.mts、subset-fonts.mjs、font_metrics.py、check-budget.mjs、e2e-server.mjs
├── public/fonts/  gl-serif-700.woff2、gl-num-500.woff2
├── src/
│   ├── main.tsx
│   ├── api/       client.ts、token.ts、sse.ts、upload.ts、keys.ts、types.ts、openapi.json、schema.d.ts、hooks/*.ts
│   ├── app/       App.tsx、paths.ts、routes.tsx、guards.tsx、AppShell.tsx、nav.ts、queryClient.ts、profile.ts、BootSplash.tsx、PagePlaceholder.tsx
│   ├── components/ 设计系统（任务 3），见任务 3 的清单
│   ├── features/  auth、onboarding、chat、photos、meals、health、cycle、medical、fitness、restaurants、settings、me
│   ├── lib/       contract.ts、labels.ts、dates.ts、format.ts、motion.ts、titles.json、titles.ts、photoHandoff.ts
│   ├── styles/    tokens.css、base.css、materials.css、fonts.css、fonts-manifest.json、components/*.css
│   ├── dev/       GalleryPage.tsx
│   └── test/      setup.ts、render.tsx、msw/server.ts、msw/handlers/*.ts、fixtures/*.ts、deps.test.ts
└── e2e/
    ├── support/   api.ts、net.ts、a11y.ts、visual.ts
    ├── pages/     *.spec.ts（每个界面任务的版式与无障碍检查，360 与 390 两种宽度）
    ├── visual/    frames.ts、frames.spec.ts（设计稿画面与应用的成对截图）
    └── acceptance/ *.spec.ts（任务 11：验收流程，iPhone 13 与 Pixel 7）
docs/11-交付物/  页面清单与信息结构说明.md、关键流程交互说明.md、状态与异常界面清单.md、手机端适配说明与测试设备清单.md、验收记录.md
```

## 设计稿画面与任务对照

| 画面 | 任务 | 画面 | 任务 |
|---|---|---|---|
| 01 登录与注册、01b 免责、02 建档基本信息、13a 我的、13b 修改档案 | 5 | 04a 识别中、04b 识别结果、04c 没认出食物、05 饮食记录 | 7 |
| 03a 开场、03b 流式回答、03c 就医提示、03d 继续遵守面板、03e 待处理条展开、03f 玻璃下滚过 | 6 | 07a 生效中、07b 待核对、07c 确认生效、07d 确认解除、07e 历史与审计、07f 录入医嘱 | 8 |
| 06 经期、08 训练 | 9 | 09 附近餐厅、10a 选择用途、10b 填写密钥失败 | 10 |
| 状态面板 12 块、设计系统一节 | 3（组件与样张）并在各页落地 | DESIGN.md 第十三节的线框页 | 5（建档第 2、3 步）、9（经期表单、训练表单）、10（隐私与数据、免责声明） |

## 验收标准与测试对照

| 条 | 自动化 |
|---|---|
| 1 | 任务 11 `e2e/acceptance/new-user.spec.ts`；任务 5、6、7 的组件测试 |
| 2 | 任务 11 `e2e/acceptance/cycle-entry.spec.ts`；任务 4 `nav.test.ts`、`guards.test.tsx` |
| 3 | 任务 11 `e2e/acceptance/medical-confirm.spec.ts`；任务 6 `ChatPage.test.tsx` 的“聊天里没有确认与解除”；任务 8 `ResolveSheet.test.tsx`、`ConfirmEffectSheet.test.tsx` |
| 4 | 任务 11 `e2e/acceptance/review-on-open.spec.ts`；任务 6 `OpeningCard.test.tsx`、`PendingStrip.test.tsx`、`ContinueSheet.test.tsx` |
| 5 | 任务 11 `e2e/acceptance/model-settings.spec.ts`；任务 10 `ProviderFlow.test.tsx` |
| 6 | 任务 11 两种模拟设备跑全部验收流程（含拍照与相册的文件输入）；真机由用户按清单补测 |
| 7 | 任务 11 `e2e/acceptance/states.spec.ts`；任务 3 `states.test.tsx`；各页的状态测试 |
| 8 | 任务 11 `e2e/acceptance/reference-tags.spec.ts`；各页测试里的“仅供参考”断言 |
| 9 | 任务 11 `e2e/acceptance/key-mask.spec.ts`；任务 10 `ProviderFlow.test.tsx` 的掩码断言 |

---

### Task 1: 后端小改动（消息编号、审计筛选、医嘱事件列表、前端静态文件）

**Files:**
- Modify: `backend/app/agent/schemas.py`（`MessageOut` 加 `id`）、`backend/app/agent/router.py`（`_visible_messages` 填 `id=message.id`）
- Modify: `backend/app/agent_grants/router.py`、`backend/app/agent_grants/service.py`
- Modify: `backend/app/medical/schemas.py`、`backend/app/medical/router.py`、`backend/app/medical/items.py`
- Create: `backend/app/frontend_static.py`
- Modify: `backend/app/config.py`、`backend/app/main.py`
- Modify: `backend/tests/test_agent_store.py`（第 509 行的字段集合加上 `"id"`）
- Create: `backend/tests/test_step11_backend.py`、`backend/tests/test_frontend_static.py`
- Modify: `docs/08-交付物/接口清单.md`（第 28 行消息字段加 id）、`docs/06-交付物/调用审计说明.md`（加 client_name 参数）、`docs/03-交付物/接口清单.md`（加 GET /api/medical/events）

**Interfaces:**
- Produces:
  - `MessageOut` 字段：`id: uuid.UUID`、`role`、`text`、`evidence`、`flags`、`created_at`。流式 `done` 事件里的 `message_id` 等于随后 `GET /api/agent/conversations/{id}` 里那条助手消息的 `id`。
  - `GET /api/agent-grants/audit?limit=50&client_name=agent`：`client_name: Annotated[str | None, Query(min_length=1, max_length=64)] = None`，按客户端名精确匹配；`service.list_audits(db, user_id, limit, client_name=None)`。
  - `app.medical.schemas.MedicalEventOut(EventOut)`：在 `EventOut` 的 `id, seq, occurred_at, action, from_status, to_status, source, detail` 之外加 `item_id: uuid.UUID`、`item_category: Category`、`item_content: str`（完整内容，不截断，因为含数值的文字不得用省略号截断）。
  - `app.medical.items.list_user_events(db, user_id, limit) -> list[tuple[MedicalItemEvent, MedicalItem]]`：从 `owned_by(MedicalItemEvent, user_id)` 开始，连接本人条目，按 `occurred_at` 倒序、`seq` 倒序，取前 `limit` 条。
  - `GET /api/medical/events?limit=50`（`limit: Annotated[int, Query(ge=1, le=200)] = 50`，依赖 `require_medical_user`，响应 `list[MedicalEventOut]`）。
  - `Settings.frontend_dist_dir: Path | None = None`；`app.frontend_static.DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"`。
  - `app.frontend_static.mount_frontend(app: FastAPI, dist_dir: Path) -> bool`：`dist_dir/index.html` 不存在时什么都不做并返回 False。存在时替换 `app.router.default`（只处理“没有任何路由匹配”的请求，所以不会遮住任何已有路由、也不改变已有路由的 405）：方法是 GET 或 HEAD、路径不是 `/api` 也不以 `/api/` 开头时，若路径对应 `dist_dir` 内的一个文件（`resolve()` 后必须仍在 `dist_dir` 内）就返回该文件，`/assets/` 下的文件带 `Cache-Control: public, max-age=31536000, immutable`；`/assets/` 下不存在的文件返回 404；其余路径一律返回 `index.html` 并带 `Cache-Control: no-cache`。其他情况交给原来的 `not_found`，所以未知的 `/api/...` 仍是统一格式的 404 JSON。
  - `create_app(*, serve_frontend: bool = True) -> FastAPI`：在全部路由注册之后，`serve_frontend` 为真时调用 `mount_frontend(app, settings.frontend_dist_dir or DEFAULT_DIST)`。任务 2 的 `app.e2e_server` 用 `serve_frontend=False` 建应用，加上自己的路由后再调用 `mount_frontend`。

- [ ] **Step 1: 写失败测试**

  `backend/tests/test_step11_backend.py`：
  - `test_conversation_messages_carry_their_ids`：参照 `tests/test_agent_store.py` 第 490 行附近那条测试，用 `conversations.append_message` 写一条用户消息与一条助手消息；GET 会话后每条消息都有 `id`，两条不同，且等于 `append_message` 返回对象的 `id`。
  - `test_streamed_done_message_id_matches_the_saved_assistant_message`：用 `tests/agent_fake.py` 的 `connect` 与 `scripted` 配好模拟模型，POST 消息（`stream: true`），解析出 `done` 事件里的 `message_id`；随后 GET 会话，最后一条助手消息的 `id` 等于它。
  - `test_audit_can_be_filtered_by_client_name`：直接插入本人 `SdkCallAudit` 三行（client_name 为 agent、agent、inspector）与他人一行 agent；不带参数返回本人三行；`client_name=agent` 返回本人两行；`client_name=inspector` 一行；`client_name=` 空串与 65 个字符都返回 422。
  - `test_medical_events_list_every_item_newest_first`：提交一份医嘱（手动加两条条目），确认一条、作废一条；GET `/api/medical/events` 返回四类事件（created、confirmed、created、voided）按时间倒序，每条带 `item_id`、`item_category`、`item_content`，内容与条目一致且不截断。
  - `test_medical_events_limit_bounds_and_ownership`：`limit=1` 只回一条；`limit=0` 与 `limit=201` 返回 422；另一个用户看不到这些事件。
  - `test_medical_events_include_system_review_events`：手动条目 `review_date` 设为今天并确认，下一次请求后事件里有 `review_due`，`source` 为 system，`detail.reason` 为“已到复查日期，请确认是否还需要继续遵守”。

  `backend/tests/test_frontend_static.py`（临时目录用 `tempfile.mkdtemp()`，在里面写 `index.html` 与 `assets/app.123.js`，再在临时目录的上一级写一个 `secret.txt`；应用用 `create_app(serve_frontend=False)` 加 `mount_frontend(app, dist)` 构造）：
  - `test_without_dist_nothing_is_served_and_api_still_works`：`mount_frontend` 指向不存在的目录返回 False；`GET /` 是 404 且响应体是 `{"error": {"code": "http_error", ...}}`；`GET /api/health` 是 200。
  - `test_root_and_client_routes_return_index_without_cache`：`/`、`/chat`、`/health/medical?tab=pending` 都返回 index.html，`Cache-Control: no-cache`，类型 text/html。
  - `test_hashed_assets_are_served_with_immutable_cache`：`/assets/app.123.js` 返回文件内容与 `immutable`；`/assets/missing.js` 返回 404。
  - `test_api_paths_are_never_shadowed`：`GET /api`、`GET /api/nope`、`POST /api/nope` 都是 404 的统一错误 JSON；`GET /docs` 与 `GET /openapi.json` 仍是原来的内容；`POST /api/auth/login` 带错误密码仍是 401。
  - `test_path_traversal_cannot_escape_dist`：`/%2e%2e/secret.txt` 与 `/..%2fsecret.txt` 都拿不到 secret.txt 的内容。
  - `test_create_app_mounts_the_configured_dist`：用 `monkeypatch` 设置 `FRONTEND_DIST_DIR` 指向临时目录并清 `get_settings` 缓存（结束后再清一次），`create_app()` 的 `GET /chat` 返回 index.html。

- [ ] **Step 2: 运行确认失败**

  Run: `uv run pytest tests/test_step11_backend.py tests/test_frontend_static.py -q -W error`
  Expected: FAIL（`id` 键不存在、`client_name` 未生效、`/api/medical/events` 404、`app.frontend_static` 不存在）。

- [ ] **Step 3: 实现** 上面 Interfaces 里的全部内容；`tests/test_agent_store.py` 第 509 行改为 `{"id", "role", "text", "evidence", "flags", "created_at"}`；三份旧文档各补一句（只补字段与参数说明，不改历史结论）。

- [ ] **Step 4: 运行确认通过**

  Run: `uv run pytest tests/test_step11_backend.py tests/test_frontend_static.py tests/test_agent_store.py tests/test_route_guards.py tests/test_sdk_core.py -q -W error`，然后全量 `uv run pytest -q -W error`（超时 600000 毫秒）
  Expected: 全部通过、零警告。

- [ ] **Step 5: 提交**

  ```
  git add backend/app/agent backend/app/agent_grants backend/app/medical backend/app/frontend_static.py backend/app/config.py backend/app/main.py backend/tests/test_step11_backend.py backend/tests/test_frontend_static.py backend/tests/test_agent_store.py docs/08-交付物/接口清单.md docs/06-交付物/调用审计说明.md docs/03-交付物/接口清单.md
  git commit -m "feat(api): add message ids, audit client filter, medical event list and SPA static serving" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 2: 前端脚手架与工具链（类型生成、字体子集、测试与端到端基础设施）

**Files:**
- Create: `frontend/package.json`、`frontend/pnpm-lock.yaml`、`frontend/index.html`、`frontend/vite.config.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.node.json`、`frontend/eslint.config.js`、`frontend/playwright.config.ts`、`frontend/.env.e2e`、`frontend/.gitignore`
- Create: `frontend/scripts/gen-api.mjs`、`gen-api-lib.mjs`、`gen-api-lib.d.mts`、`subset-fonts.mjs`、`font_metrics.py`、`check-budget.mjs`、`e2e-server.mjs`
- Create: `frontend/src/main.tsx`（占位，任务 4 替换）、`frontend/src/api/openapi.json`、`frontend/src/api/schema.d.ts`、`frontend/src/api/schema.test.ts`
- Create: `frontend/src/lib/titles.json`、`frontend/src/lib/titles.ts`、`frontend/src/lib/titles.test.ts`
- Create: `frontend/public/fonts/gl-serif-700.woff2`、`frontend/public/fonts/gl-num-500.woff2`、`frontend/src/styles/fonts.css`、`frontend/src/styles/fonts-manifest.json`
- Create: `frontend/src/test/setup.ts`、`frontend/src/test/render.tsx`、`frontend/src/test/msw/server.ts`、`frontend/src/test/msw/handlers/index.ts`、`frontend/src/test/deps.test.ts`
- Create: `frontend/e2e/support/api.ts`、`net.ts`、`a11y.ts`、`visual.ts`，`frontend/e2e/visual/frames.ts`、`frames.spec.ts`，`frontend/e2e/pages/smoke.spec.ts`
- Create: `backend/app/openapi_export.py`、`backend/app/e2e_server.py`、`backend/tests/test_openapi_snapshot.py`、`backend/tests/test_e2e_server.py`
- Modify: 仓库根目录 `.gitignore`（加入 Global Constraints 里“不得提交”的前端路径）

**Interfaces:**
- Consumes: 任务 1 的 `create_app(serve_frontend=...)`、`mount_frontend`。
- Produces:
  - `package.json` 脚本（名字固定，后续任务与文档都按这些名字写）：`dev`（vite）、`dev:lan`（`vite --mode lan`）、`build`（`vite build`）、`build:e2e`（`vite build --mode e2e --outDir dist-e2e`）、`build:check`（`vite build` 后 `node scripts/check-budget.mjs`）、`typecheck`（`tsc --noEmit -p tsconfig.json`）、`lint`（`eslint . --max-warnings 0`）、`test`（`vitest run`）、`api:gen`（`node scripts/gen-api.mjs`）、`fonts`（`node scripts/subset-fonts.mjs`）、`e2e`（`playwright test --project=iphone-13 --project=pixel-7`）、`e2e:pages`（`playwright test --project=layout-390 --project=layout-360`）、`visual`（`playwright test --project=visual`）。
  - 运行依赖：react、react-dom、react-router、@tanstack/react-query、react-aria-components、@internationalized/date。开发依赖：vite、@vitejs/plugin-react、@vitejs/plugin-basic-ssl、typescript、@types/react、@types/react-dom、@types/node、vitest、jsdom、@testing-library/react、@testing-library/user-event、@testing-library/jest-dom、msw、eslint、@eslint/js、typescript-eslint、eslint-plugin-react-hooks、globals、openapi-typescript、@playwright/test。都装当前稳定版，确切版本以锁文件为准。
  - `vite.config.ts`：`server.port 5173`、`strictPort`；`server.proxy['/api'] = { target: 'http://127.0.0.1:8000', timeout: 300000, proxyTimeout: 300000 }`（一轮对话可能连续调用模型很久才开始推送）；`mode === 'lan'` 时加 `basicSsl()` 并 `server.host = '0.0.0.0'`；`build.target ['safari16', 'chrome107']`、`build.manifest true`；`test`：`environment 'jsdom'`、`setupFiles ['src/test/setup.ts']`、`include ['src/**/*.test.{ts,tsx}']`、`css false`。
  - `.env.e2e`：`VITE_GALLERY=1`（只有端到端构建与开发模式注册 `/dev/gallery`）。
  - `index.html`：`<html lang="zh-CN">`；`<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">`；`<meta name="theme-color" content="#F7FAFE">`；两个字体 `<link rel="preload" as="font" type="font/woff2" crossorigin href="/fonts/gl-serif-700.woff2">` 与 `/fonts/gl-num-500.woff2`；`<div id="root"></div><div id="shell-root"></div>`。
  - `eslint.config.js`：`@eslint/js` recommended、typescript-eslint `recommendedTypeChecked`、react-hooks recommended；`no-restricted-globals: ['error', { name: 'EventSource', message: '用 src/api/sse.ts' }]`；`no-restricted-imports` 禁止 framer-motion、motion、gsap、react-spring、@react-spring/*、animejs；忽略 `dist`、`dist-e2e`、`src/api/schema.d.ts`、`playwright-report`、`test-results`。
  - `backend/app/openapi_export.py`：`python -m app.openapi_export <输出路径>` 写出 `json.dumps(create_app(serve_frontend=False).openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"`，UTF-8。
  - `scripts/gen-api-lib.mjs`：`export async function generateSchemaSource(openapi: object): Promise<string>`，内部用 openapi-typescript 的 `openapiTS(openapi, { alphabetize: true })` 与 `astToString`，开头加一行固定注释“由 pnpm api:gen 生成，不要手改”；`gen-api-lib.d.mts` 给出它的类型声明。
  - `scripts/gen-api.mjs`：`spawnSync('uv', ['run', '--directory', '../backend', 'python', '-m', 'app.openapi_export', '../frontend/src/api/openapi.json'], { stdio: 'inherit' })`，再读 `openapi.json` 调用 `generateSchemaSource` 写 `src/api/schema.d.ts`。快照是提交进仓库的文件，所以检查不需要运行中的服务。
  - `src/lib/titles.json`：全部写死的宋体标题（键到文字），本任务一次写全，后续任务只能用这些键；需要新标题的任务必须在这里加键并重新运行 `pnpm fonts`。键与文字固定为：`login` 登录，`register` 注册，`disclaimer` 免责声明，`onbBasics` 基本信息，`onbActivity` 活动与目标，`onbDiet` 饮食偏好与忌口，`chat` 对话，`photo` 拍照识别，`photoResult` 识别结果，`photoNotFood` 没有认出食物，`photoUnclear` 照片看不清，`photoFailed` 这次没有识别完成，`photoTips` 拍照小提示，`photoDrafts` 未处理的草稿，`mealEval` 整餐评价，`mealWhen` 吃的时间，`records` 记录，`health` 健康，`me` 我的，`profile` 个人档案，`mealNew` 手动记一餐，`workoutNew` 记一次训练，`weekTraining` 本周训练，`trend` 动作趋势，`medicalNew` 录入医嘱，`ended` 已结束，`audit` 审计记录，`continueSheet` 继续遵守这条医嘱，`confirmSheet` 确认这条医嘱生效，`resolveSheet` 确认解除这条医嘱，`voidSheet` 作废这条医嘱，`editItem` 修改这条医嘱，`manualItem` 手动补充一条，`phaseMenstrual` 经期，`phaseFollicular` 卵泡期，`phaseOvulation` 排卵期，`phaseLuteal` 黄体期，`phaseUnknown` 暂时无法判断阶段，`periodStart` 记录经期开始，`periodEnd` 记录经期结束，`dayLog` 记录今天，`restaurants` 附近吃什么，`nearbyList` 附近的店，`avoided` 已避开的类型，`models` 模型服务，`modelNew` 添加模型服务，`otherSettings` 其他设置，`privacy` 隐私与数据，`grants` 外部授权，`auditCalls` 调用记录，`savedArea` 已保存的大致区域，`clearArea` 清除大致区域，`revokeGrant` 吊销这个授权，`discardRecognition` 放弃这次识别，`editRecognitionItem` 修改这一项，`locationAsk` 用一次你的位置？，`noModel` 还没有可用的对话模型，`sessionExpired` 登录已过期，`loadFailed` 没能读取，`modelFailed` 没能连上模型服务，`emptyDiary` 这天没有饮食记录，`needsProfile` 还不能估算每日需要，`cycleInsufficient` 还不能预测下次经期，`careSevere` 请尽快就医，`careSelfHarm` 请联系专业帮助，`careMedication` 请咨询医生或药师，`careDiet` 请咨询医生或营养师，`gallery` 组件样张。
  - `src/lib/titles.ts`：`export const TITLES = titlesJson`；`export type TitleKey = keyof typeof TITLES`；`export const SERIF_EXTRA = '0123456789年月日，、：；（）·—/- '`。
  - `scripts/subset-fonts.mjs`：读 `.font-cache/NotoSerifSC-Bold.otf`（来源：github.com/notofonts/noto-cjk 的 Serif 发布包里的 SubsetOTF/SC）与 `.font-cache/SourceSerif4Variable-Roman.ttf`（来源：github.com/adobe-fonts/source-serif 的发布包）；宋体子集文字为 `TITLES` 全部字符加 `SERIF_EXTRA`，用 `uvx --from "fonttools[woff]" pyftsubset <源> --text-file=<临时文件> --flavor=woff2 --layout-features=palt,kern --output-file=public/fonts/gl-serif-700.woff2`；数字字体先 `uvx --from "fonttools[woff]" fonttools varLib.instancer <源> wght=500 opsz=16 -o .font-cache/ss4-500.ttf`，再用 pyftsubset 取 `0123456789,.:/-×%`（17 个字符，`--layout-features=tnum,lnum`）写 `public/fonts/gl-num-500.woff2`；用 `uv run --no-project --with fonttools python scripts/font_metrics.py <字体>` 读出 unitsPerEm、ascender、descender；写 `src/styles/fonts-manifest.json`（`{ serifChars, serifBytes, numChars, numBytes, metrics }`）与 `src/styles/fonts.css`：`@font-face` 的 `GL Serif`（700）与 `GL Num`（500，`font-display: swap`），以及用 `local("PingFang SC"), local("Microsoft YaHei"), local("Noto Sans CJK SC")` 的 `GL Serif Fallback`、`GL Num Fallback`，按读出的度量写 `ascent-override`、`descent-override` 与 `size-adjust`。
  - `scripts/check-budget.mjs`：读 `dist/.vite/manifest.json`，对 `index.html` 入口加对话路由（`src/features/chat/ChatPage.tsx`）及其静态导入的全部 JS 做 gzip 计数，上限 150 KB；这些块引用的 CSS gzip 后上限 22 KB；`public/fonts` 两个文件合计上限 45 KiB（46,080 字节）；超出时打印明细并以非零码退出。任务 6 之前对话页还不存在时只检查入口。
  - `backend/app/e2e_server.py`：`python -m app.e2e_server --port 8765 --dist <目录> --fixtures <目录>`。启动顺序：设置环境变量（`DATABASE_URL` 取 `TEST_DATABASE_URL` 或 `postgresql+psycopg://goodlife:goodlife@127.0.0.1:5433/goodlife_test`，`JWT_SECRET` 与 `FIELD_ENCRYPTION_KEY` 用 `tests/conftest.py` 里的测试值，`LLM_ALLOW_PRIVATE_HOSTS=true`）→ 启动模拟模型 `E2EModel` 与 `_MockAmap` → 设置 `AMAP_KEY=DEMO_AMAP_KEY`、`AMAP_BASE_URL=<模拟高德地址>` 并 `get_settings.cache_clear()` → `alembic upgrade head` → 清空全部表 → `write_fixtures(dir)` → `build_app(info, dist)` → `uvicorn.run(app, host="127.0.0.1", port=port)`；退出时关闭两个模拟服务。
    - `class E2EModel(_AcceptanceModel)`：`start()` 改用 `E2EHandler`；`class E2EHandler(_Handler)`：`do_GET` 也校验 `Authorization: Bearer DEMO_MODEL_KEY`（不对返回 401，这样密钥错误会在“获取模型”一步暴露），`/v1/models` 返回 `DEMO_MODEL_ID` 与 `VISION_MODEL_ID` 两个模型。
    - `write_fixtures(dir: Path) -> None`：用 Pillow 写 `meal.jpg`（640×480，颜色 `MEAL_COLOUR`，模拟看图模型认作麻婆豆腐加米饭）与 `white.jpg`（纯白，模拟看图模型答“不是食物”）。
    - `build_app(info: dict[str, str], dist: Path | None) -> FastAPI`：`create_app(serve_frontend=False)`，加 `GET /__e2e/info` 返回 `info`（`model_base_url`、`model_key`、`bad_key`（固定 `sk-e2e-bad-key`）、`chat_model_id`、`vision_model_id`），最后 `mount_frontend(app, dist)`（dist 为 None 时跳过）。
  - `scripts/e2e-server.mjs`：先 `pnpm build:e2e`，再在 `../backend` 下 `uv run python -m app.e2e_server --port 8765 --dist ../frontend/dist-e2e --fixtures ../frontend/e2e/.fixtures`，把子进程输出转发出来，收到退出信号时结束子进程。
  - `playwright.config.ts`：`webServer: { command: 'node scripts/e2e-server.mjs', url: 'http://127.0.0.1:8765/api/health', reuseExistingServer: false, timeout: 240000 }`；`use.baseURL 'http://127.0.0.1:8765'`；`outputDir 'test-results'`；项目：`iphone-13`（`devices['iPhone 13']`，WebKit，`testDir e2e/acceptance`）、`pixel-7`（`devices['Pixel 7']`，Chromium，`testDir e2e/acceptance`）、`layout-390`（Chromium，视口 390×844，`isMobile`、`hasTouch`，`testDir e2e/pages`）、`layout-360`（同上，视口 360×800）、`visual`（Chromium，视口 390×844，`testDir e2e/visual`）；`workers: 1`（共用一个测试库）。
  - `e2e/support/net.ts`：`blockExternal(page)`：`page.route` 把主机不是 127.0.0.1 的请求全部 abort（`file://` 的设计稿除外，但设计稿里的 Google 字体请求同样 abort）。
  - `e2e/support/api.ts`：`e2eInfo(request)`；`createUser(request, opts: { gender?: 'female' | 'male'; disclaimer?: boolean; profile?: 'complete' | 'empty' }) -> Promise<{ username: string; password: string; token: string }>`（用户名 `u` 加时间戳与随机数，小写字母数字下划线，3 到 32 位；`profile: 'complete'` 时 PATCH 六项建档字段）；`seedModelService(request, token, info)`（POST provider、fetch-models、PUT chat 与 vision 两个用途）；`seedPendingOrder(request, token, text)`；`seedActiveItem(request, token, fields)`；`seedReviewDueItem(request, token, fields)`（手动条目 `review_date` 为今天、确认）；`seedProposal(request, token, itemId, reason)`（POST propose-resolution）；`sendMessage(request, token, text)`（非流式）；`openAs(page, token, path)`（先打开 `/` 写 localStorage `goodlife.token` 再跳转）。全部只调用真实接口。
  - `e2e/support/a11y.ts`：`expectTouchTargets(page)`（可见的 a、button、input、select、textarea 与 role 为 button、tab、radio、checkbox、switch、slider、link 的元素，宽高都不小于 44；带 `data-hit44` 的元素允许视觉高 36，但其 `::before` 必须上下各外扩至少 4 像素）；`expectMinFontSize(page, 12)`（全部可见文字节点的计算字号不小于 12）；`expectNoHorizontalScroll(page)`；`expectCoverWorks(page)`（点遮盖后每个 `[data-sensitive]` 都有 `aria-hidden="true"` 与 `inert`，其 `::after` 的背景是不透明斜纹、没有任何 filter；连按 Tab 焦点不会进入敏感区；再点恢复）；`expectGlass(page, on)`（`[data-tier="chrome"]` 的计算 `backdrop-filter` 在 on 时含 `blur(16px)`，off 时为 none）；`expectForcedColorsSmoke(page)`（只在 Chromium：`emulateMedia({ forcedColors: 'active' })` 后 `.btn` 有实线边框、`.rnav a[aria-current="page"]::before` 有 outline、`.care` 边框 3 像素）。
  - `e2e/support/visual.ts`：`captureDeckFrame(page, frameId, width)`：打开 `file:///E:/workspace/good-life/docs/superpowers/design/step11/index.html`（由文件位置推算），视口宽设为 width，截图 `figure:has(figcaption b span:text-is("<frameId>")) .app`（状态面板用 `.panel` 的序号），存到 `test-results/visual/<frameId>-<width>-deck.png`；`captureApp(page, frameId, width)` 截整个视口存 `-app.png`。
  - `e2e/visual/frames.ts`：`export interface FrameSpec { id: string; widths: (360 | 390)[]; prepare: (ctx: { request: APIRequestContext; page: Page }) => Promise<string> }`（返回要打开的路径）；`export const FRAMES: FrameSpec[] = []`，后续每个界面任务往里加自己的画面。`frames.spec.ts` 对每个画面、每个宽度各截一对图，供评审并排比较。
  - `src/test/setup.ts`：引入 jest-dom 匹配器；MSW `server.listen({ onUnhandledRequest: 'error' })`、每个测试后 `resetHandlers`、清 localStorage；给 jsdom 补 `matchMedia`（可由测试改写 matches）、`IntersectionObserver`、`ResizeObserver`、`scrollTo`。
  - `src/test/render.tsx`：`renderWithProviders(ui, { queryClient? })`（QueryClient 关闭重试）；任务 4 在同一文件加 `renderRoute`。
  - `src/test/msw/handlers/index.ts`：`export const handlers: HttpHandler[] = []`，后续任务在同目录加按模块的文件并在这里汇总。

- [ ] **Step 1: 建 `frontend` 目录、安装依赖并写失败测试**

  先 `pnpm init`，再 `pnpm add` 运行依赖与 `pnpm add -D` 开发依赖。测试：
  - `src/api/schema.test.ts`：`it('generated api types match the committed openapi snapshot')`：读 `src/api/openapi.json`，调用 `generateSchemaSource`，结果与 `src/api/schema.d.ts` 逐字相等；不相等时提示运行 `pnpm api:gen`。
  - `src/lib/titles.test.ts`：`it('serif subset covers every fixed title')`：`TITLES` 全部字符与 `SERIF_EXTRA` 都在 `fonts-manifest.json` 的 `serifChars` 里；`it('font subsets stay within budget')`：`serifBytes` 不超过 40960，`serifBytes + numBytes` 不超过 35840。
  - `src/test/deps.test.ts`：`it('every direct dependency has an allowed license')`：`package.json` 的 dependencies 与 devDependencies 逐个读 `node_modules/<名字>/package.json` 的 `license`，必须在 MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause 之内；`it('no animation library is installed')`：上面禁止的名字一个都不在。
  - `backend/tests/test_openapi_snapshot.py`：`test_frontend_openapi_snapshot_is_current`：`frontend/src/api/openapi.json` 的内容与 `create_app(serve_frontend=False).openapi()` 按同一格式序列化后完全一致，失败信息提示在 frontend 下运行 `pnpm api:gen`。
  - `backend/tests/test_e2e_server.py`：`test_info_route_is_not_shadowed_by_the_spa`（`build_app(info, dist)` 后 `/__e2e/info` 返回 info，`/chat` 返回 index.html）；`test_e2e_model_rejects_a_bad_key_when_listing`（在 127.0.0.1 端口 0 启动 `E2EModel`，带假密钥 GET `/v1/models` 得到两个模型，带 `bad_key` 得到 401，结束时关闭）；`test_fixtures_have_the_expected_colours`（`write_fixtures` 写出的两张图平均颜色分别接近 `MEAL_COLOUR` 与纯白）。

- [ ] **Step 2: 运行确认失败**

  Run（frontend）: `pnpm exec vitest run src/api src/lib src/test`；Run（backend）: `uv run pytest tests/test_openapi_snapshot.py tests/test_e2e_server.py -q -W error`
  Expected: FAIL（快照、生成脚本、字体清单、e2e_server 都还不存在）。

- [ ] **Step 3: 实现** 上面 Interfaces 里的全部文件；运行 `pnpm api:gen` 生成快照与类型。字体：向控制者报告两个源文件的名字、来源与大小，用户同意后下载到 `frontend/.font-cache/`（已忽略），运行 `pnpm fonts`，提交生成的两个 woff2、`fonts.css` 与 `fonts-manifest.json`。浏览器：取得同意后运行 `pnpm exec playwright install chromium webkit`。`src/main.tsx` 暂时只渲染一个写着 good-life 的占位元素。`e2e/pages/smoke.spec.ts`：`/` 返回含 `#root` 与 `#shell-root` 的页面；`/api/health` 为 ok；`/api/nope` 是 404 JSON；页面没有对 127.0.0.1 以外的任何请求。

- [ ] **Step 4: 运行确认通过**

  Run（frontend）: `pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`、`pnpm e2e:pages`；Run（backend）: `uv run pytest tests/test_openapi_snapshot.py tests/test_e2e_server.py -q -W error`，再全量
  Expected: 全部通过；`pnpm e2e:pages` 两个宽度下 smoke 通过。

- [ ] **Step 5: 提交**

  ```
  git add .gitignore frontend backend/app/openapi_export.py backend/app/e2e_server.py backend/tests/test_openapi_snapshot.py backend/tests/test_e2e_server.py
  git commit -m "build(frontend): scaffold Vite React app with typed API generation, fonts and test tooling" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```
  提交前用 `git status --short` 确认没有 node_modules、dist、dist-e2e、.font-cache、e2e/.fixtures、test-results。

---

### Task 3: 设计系统（令牌、材质、玻璃模式、遮盖与共用组件）

**Files:**
- Create: `frontend/src/styles/tokens.css`（`index.html` 第 16 至 93 行的 `:root` 原样搬入，`--font-display` 改为 `"GL Serif","GL Serif Fallback",var(--font-sans)`，`--font-num` 改为 `"GL Num","GL Num Fallback",var(--font-sans)`）
- Create: `frontend/src/styles/base.css`（重置、`body` 背景、`:focus-visible`、`.n`/`.ns` 数字样式、`.t-display`/`.t-title`/`.t-h`/`.st-h`/`.t-small`/`.t-cap`，减弱动效块）、`frontend/src/styles/materials.css`（四种材质、降级、`data-sheet-open`、强制颜色块）
- Create: `frontend/src/styles/components/*.css`：button、ref、verdict、conf、sens、field-input、toggle、tabs、nav、header、dock、sheet、will、care、slip、fold、states、toast、ledger、ruler、cycle-ticks、status-mark、jump
- Create: `frontend/src/components/` 下：`Surface.tsx`、`Field.tsx`、`Icon.tsx`、`Button.tsx`、`ButtonLink.tsx`、`IconButton.tsx`、`Title.tsx`、`RefTag.tsx`、`VerdictMark.tsx`、`ConfidenceCells.tsx`、`StatusMark.tsx`、`CountUp.tsx`、`ThoughtLine.tsx`、`LedgerTicks.tsx`、`Ruler.tsx`、`ruler.ts`、`CycleTicks.tsx`、`EvidenceFold.tsx`、`SystemSlip.tsx`、`CareBlock.tsx`、`Sheet.tsx`、`WillList.tsx`、`ConfirmSheet.tsx`、`Checkbox.tsx`、`Switch.tsx`、`SegmentedTabs.tsx`、`TextTabs.tsx`、`RadioSegment.tsx`、`TextField.tsx`、`PasswordField.tsx`、`TagField.tsx`、`SelectField.tsx`、`DateField.tsx`、`states/LoadingState.tsx`、`states/ErrorState.tsx`、`states/EmptyState.tsx`、`states/InsufficientState.tsx`、`states/AuthNeededState.tsx`、`Toast.tsx`、`JumpCard.tsx`、`PageHeader.tsx`、`BottomNav.tsx`、`CoverButton.tsx`、`Dock.tsx`、`ShellPortal.tsx`、`Sensitive.tsx`、`cover.tsx`、`glass/GlassModeProvider.tsx`、`glass/lowEnd.ts`
- Create: `frontend/src/lib/motion.ts`、`frontend/src/api/errors.ts`
- Create: `frontend/src/dev/GalleryPage.tsx`；Modify: `frontend/src/main.tsx`（路径是 `/dev/gallery` 且开发模式或 `VITE_GALLERY` 为 1 时渲染样张页；任务 4 改为路由）
- Test: `frontend/src/components/*.test.tsx`（见步骤）、`frontend/e2e/pages/gallery.spec.ts`
- Modify: `frontend/e2e/visual/frames.ts`（加 `ds` 与状态面板 `st1` 至 `st12`）

**Interfaces:**
- Consumes: `TITLES`、`TitleKey`（任务 2）；`fonts.css`。
- Produces（后续任务只用这些名字）：
  - `api/errors.ts`：`class ApiError extends Error { status: number; code: string; details?: { field: string; message: string }[]; constructor(status, code, message, details?) }`（状态组件与面板在本任务就要用它；任务 4 的客户端从这里引入）。
  - 动效一律按 DESIGN.md 第五节的表取时长与曲线（令牌 `--d-1` 120、`--d-2` 200、`--d-3` 320、`--d-4` 480、`--d-frost` 160 与三条曲线），不另起数值。
  - `Surface({ tier: 'plate' | 'still' | 'chrome' | 'sheet'; as?: ElementType; className?; children })`：输出类名 `plate`、`still`、`chrome`、`sheet` 之一与 `data-tier`，不做运行时计算。
  - `Field()`：应用根节点的静态背景（`--field`，`background-size` 同设计稿），不随路由重绘。
  - `Icon({ name: IconName; size?: 18 | 20 | 24; onGlass?: boolean })`，`IconName` 为 camera、image、send、back、down、right、cover、eye、pin、nav、plus、check、x、alert、info、phone、search、refresh、lock、edit、trash、cal、clock、doc、bowl（路径照抄 `index.html` 第 888 至 915 行），`aria-hidden`，玻璃上线宽 1.7。
  - `Button({ variant: 'primary' | 'quiet' | 'text' | 'danger' | 'danger-outline'; size?: 'md' | 'sm'; block?; ink?; onField?; icon?: IconName; isDisabled?; onPress; type?; children })`（基于 React Aria `Button`，类名 `btn btn-pri`、`btn btn-qt`、`btn-txt`、`btn btn-dng`、`btn btn-dng-qt`，`sm` 加 `btn-sm` 与 `data-hit44`）；`ButtonLink({ to, variant, size?, block?, children })` 同样式的路由链接；`IconButton({ icon, label, onPress?, back?, pressed? })`（`.ibtn`，返回键加 `.back`）。
  - `Title({ k: TitleKey; level: 'display' | 'title' | 'h' | 'state'; as?: 'h1' | 'h2' | 'h3'; id? })`：全站唯一输出 `t-display`、`t-title`、`t-h`、`st-h` 类名的地方。
  - `RefTag()`：`<span class="ref">仅供参考</span>`。
  - `VerdictMark({ conclusion: 'suitable' | 'caution' | 'not_recommended' | 'unchecked'; label?: string })`：类名 `vd vd-ok|vd-warn|vd-no|vd-un`，默认文字取 `labels.ts` 的 `CONCLUSION_LABELS`（任务 4 建立；本任务先在组件内写同样的四个默认值，任务 4 改为引用）。
  - `ConfidenceCells({ value: number })`：五格，亮格数 `max(1, round(value * 5))`，文字 `value >= 0.85` 为高、`value < 0.6` 为低、其余为中（0.6 先写在组件里，任务 4 改为引用 `contract.ts` 的 `LOW_CONFIDENCE`）；`role="img"`、`aria-label="把握程度 0.84，中"`。
  - `StatusMark({ state: 'todo' | 'current' | 'running' | 'ok' | 'bad'; index?: number })`：步骤号圈（`.fs-m` 与 `.pm` 的样式），running 时转动的钴蓝弧线，减弱动效时静止。
  - `CountUp({ value: number; format?: (n: number) => string })`：600 毫秒三次方缓出；减弱动效时直接显示终值并监听偏好变化；只有数字变化时才动。
  - `ThoughtLine({ text: string })`：等待状态的一行文字加闪烁光标，减弱动效时光标不闪；`role="status"`。
  - `LedgerTicks({ segments: { kcal: number; tone: 1 | 2 | 3 | 4 }[]; need: number | null; step?: number; label: string })`：每格 25 千卡，格数 `round(max(合计, need) / step)`，格中点落在第几段就用第几种颜色（1 海军蓝、2 钴蓝、3 天青、4 `--sky-soft`），需要线与“需要 N”收在面板内，`role="img"` 加完整 `aria-label`，长出动效 480 毫秒、每格错开 6 毫秒。
  - `rulerMarks(width, value, step, major, ppu) -> { ticks: { x: number; major: boolean }[]; labels: { x: number; value: number }[] }`（DESIGN.md 第六节公式：中线 `c = width / 2`，刻度 `x = c + (k − value) × ppu − 0.75`，标签只取 `x − 14 >= 0` 且 `x + 14 <= width` 的大刻度）；`Ruler({ label, unit, value, onChange, min, max, step, major, ppu, hint? })`：React Aria `Slider` 语义（`aria-valuetext="165 厘米"`），拖动吸附到小刻度，方向键按 step 改值，点数字弹出 React Aria `NumberField`（`inputMode="decimal"`），容器尺寸变化用 ResizeObserver 重算，没有 ResizeObserver 时监听 resize，两端 44 像素淡出。
  - `CycleTicks({ length: number; periodDays: number; predicted: [number, number] | null; today: number | null; label: string })`。
  - `EvidenceFold({ lines: string[] })`：React Aria `Disclosure`，标题“依据”加条数胶囊，默认折叠，`grid-template-rows` 过渡，不支持时直接显示或隐藏。
  - `SystemSlip({ title: string; lines: string[] })`：静玻璃便笺，`role="note"`、`aria-label="系统附上的医嘱提醒"`，右上“系统附注”胶囊。
  - `CareBlock({ titleKey: TitleKey; text: string; phones: ('120' | '12356')[] })`：整块朱色、直角、出血到屏幕边、`role="alert"`，每个号码一个 `tel:` 白底按钮（“拨打 120”），底部固定一句“这是一条固定的安全提示，不是模型生成的。”，不可折叠、不可关闭。
  - `Sheet({ isOpen; onClose; titleKey: TitleKey; children; footer?: ReactNode })`：React Aria `ModalOverlay`、`Modal`、`Dialog`；遮罩 `--scrim` 只压暗；没有拖动把手，Esc 与按钮关闭；打开时焦点进入标题、关闭后回到触发处；带 `data-entering` 时是实色、`transitionend` 后去掉并淡入磨砂（160 毫秒，只过渡底色）；打开期间调用 `useSheetGlass()` 让根节点带 `data-sheet-open`，并隐藏轻提示。
  - `WillList({ items: { text: string; irreversible?: boolean }[] })`（`.will`，不可撤销的一项朱色）。
  - `ConfirmSheet({ isOpen; onClose; titleKey; quote?: ReactNode; will?: WillItem[]; confirmLabel: string; confirmVariant?: 'primary' | 'danger'; ack?: string; secondary?: { label: string; onPress: () => void }; note?: string; onConfirm: () => Promise<void>; error?: ApiError | null; resultText?: string })`：有 `ack` 时必须勾选该句子，确认按钮才可用；确认中按钮不可重复点；`resultText` 写进 `aria-live="assertive"` 区域；`error` 时在按钮上方显示后端说明与错误码。
  - `Checkbox`、`Switch({ label; description?; isSelected; onChange })`（`.tg` 胶囊开关、整行是标签、行高 56）、`SegmentedTabs({ items: { id: string; label: string; badge?: number }[]; selectedKey; onSelectionChange; ariaLabel })`（React Aria `Tabs`，`.ttabs`）、`TextTabs`（同签名，`.ttabs.sm`）、`RadioSegment({ label; options: { value: string; label: string }[]; value; onChange })`（React Aria `RadioGroup`，`.opts`）、`TextField({ label; value; onChange; hint?; error?: string; type?; inputMode?; autoComplete?; maxLength?; multiline?; rows?; isInvalid? })`、`PasswordField`（显示与隐藏切换）、`TagField({ label; tags: string[]; onChange; addLabel?: string })`（React Aria `TagGroup`，删除键 44）、`SelectField({ label; value; options; onChange })`（原生 select，`.sel`）、`DateField({ label; value: string | null; onChange; min?; max?; placeholder? })`（原生 `input type=date`）。
  - 状态组件：`LoadingState({ variant: 'diary' | 'list' | 'page'; text: string })`（骨架块加扫光、`role="status"` 文字）、`ErrorState({ titleKey?: TitleKey; error: ApiError; onRetry?: () => void; actions?: ReactNode; note?: string })`（标题默认 `loadFailed`，正文是 `error.message` 原文，下一行“错误码 {code}”，有 onRetry 时主按钮“重试”）、`EmptyState({ titleKey; body; actions? })`、`InsufficientState({ titleKey; notes: string[]; progressText?: string; actions? })`、`AuthNeededState({ titleKey; body; actions })`。
  - `ToastProvider`、`useToast(): { show(text: string): void }`（活玻璃、`aria-live="polite"`，面板打开时不显示）。
  - `JumpCard({ to: string; label: string; description?: string })`：对话里唯一的跳转件，只导航。
  - `PageHeader({ titleKey; variant: 'big' | 'sub' | 'chat'; back?: true | string; caption?: string; cover?: boolean; onRefresh?: () => void; children? })`：有 `onRefresh` 时右侧放刷新按钮（`IconButton icon="refresh" label="刷新"`，代替下拉刷新）；滚动容器顶部的 `position: sticky` 页头，列表顶部放 1 像素哨兵，IntersectionObserver 看到它离开时加 `stuck`（没有 IntersectionObserver 时监听滚动并按帧合批），玻璃画在 `::before` 上只过渡透明度；上沿加 `env(safe-area-inset-top)`；`cover` 为真时右上角放 `CoverButton`。
  - `BottomNav({ items: NavItem[]; embedded?: boolean })`：`<nav class="rnav" aria-label="主导航">`，`--cols` 为项数，当前项 `aria-current="page"` 画“积釉”（当前项变化时凹槽与短线用 240 毫秒 transform 移到新的一项，减弱动效时直接跳到），最右 60 宽的 `CoverCell`（按钮，`aria-pressed`，文字“遮盖”或“已遮盖”，读屏名“遮盖敏感内容”或“已遮盖，点按恢复显示”）；`embedded` 时去掉自身材质（放在对话底座里）。`NavItem = { key: 'chat' | 'records' | 'health' | 'me'; label: string; to: string }`。
  - `CoverButton()`：没有底部导航的二级页右上角的遮盖按钮，与 CoverCell 共用状态与读屏文字。
  - `Dock({ tall?: boolean; children })`：底部操作坞，活玻璃，渲染进 `#shell-root`；`ShellPortal({ children })`。
  - `CoverProvider`、`useCover(): { covered: boolean; toggle(): void; setCovered(v: boolean): void }`：`document.visibilityState` 变为 hidden 时设为 true；切换时向 `aria-live="polite"` 区域播报“已遮盖”或“已恢复显示”。
  - `Sensitive({ as?: ElementType; square?: boolean; className?; children })`：输出 `class="sens"` 与 `data-sensitive`；遮盖时 `aria-hidden="true"` 与 `inert`；不支持 inert 时把子树里的 a、button、input、textarea、select、`[tabindex]` 的 tabindex 存进 `data-ti` 后设为 -1，取消时恢复；斜纹 `border-radius: inherit`，`square` 时为 0。
  - `GlassModeProvider`、`useGlassPreference(): [ReduceTransparencyPref, (p: ReduceTransparencyPref) => void]`（`'system' | 'on' | 'off'`，localStorage 键 `goodlife.reduceTransparency`，对应界面“跟随系统 / 开 / 关”）、`useSheetGlass(open: boolean)`；`computeGlass({ pref, systemReduce, lowEnd }): 'on' | 'off'`：pref 为 on 时 off，为 off 时 on，为 system 时 `systemReduce || lowEnd` 则 off 否则 on。
  - `glass/lowEnd.ts`：`LOW_END_RULE_VERSION = 1`、`LOW_END_MEDIAN_MS = 24`、`LOW_END_MIN_FRAMES = 60`、`LOW_END_RETEST_DAYS = 30`、`LOW_END_STORAGE_KEY = 'goodlife.lowEnd'`；`medianInterval(deltas: number[]): number`；`verdictKey(appVersion: string, userAgent: string): string`（应用版本 + 浏览器主版本 + 规则版本）；`needsProbe(stored: StoredVerdict | null, key: string, now: number): boolean`（没有记录、键变了、或判为低端且超过 30 天时为真）；`initialLowEnd(stored, key, deviceMemory?: number): boolean`（`deviceMemory <= 2` 时先按低端起步，但仍需复测）；`startLowEndProbe({ getScroller, key, onVerdict }): () => void`（load 事件之后再空闲 1.5 秒（`requestIdleCallback`，没有时 setTimeout），只在第一次真实滚动时用 requestAnimationFrame 记录帧间隔，凑满 60 帧后取中位数，达到 24 毫秒判为低端并保存）。
  - `lib/motion.ts`：`usePrefersReducedMotion(): boolean`（读 `matchMedia('(prefers-reduced-motion: reduce)')` 并监听变化）。
  - 样张页 `GalleryPage`：按设计稿“设计系统”一节与 12 块状态面板的顺序展示上面全部组件与状态（含三项与四项导航、降级对照、就医提示、遮盖的医嘱面板）。

- [ ] **Step 1: 写失败测试**（每个文件只列关键断言）
  - `Surface.test.tsx`：`it('renders the tier class and data-tier')`、`it('renders as the given element')`。
  - `glass/GlassModeProvider.test.tsx`：`it('turns glass on by default')`（根节点 `data-glass="on"`）；`it('turns glass off when the system reduces transparency')`；`it('lets the user setting override the system and the low-end verdict')`（pref off 时即使系统减少透明且判为低端也 on；pref on 时 off）；`it('follows a change of the system preference')`；`it('marks the root while a sheet is open')`（`data-sheet-open` 出现与消失）。
  - `glass/lowEnd.test.ts`：`it('takes the median frame interval')`；`it('judges 24 ms or more as low end')`；`it('re-probes when the key changes or a low verdict is older than 30 days')`；`it('starts solid when device memory is 2 gb or less')`；`it('ignores frames outside real scrolling')`（用假的 rAF 与 scroll 事件驱动）。
  - `cover.test.tsx`：`it('covers every sensitive region with aria-hidden and inert')`；`it('announces covered and restored')`；`it('falls back to tabindex when inert is unsupported and restores the original values')`（测试里临时删掉 `HTMLElement.prototype.inert`，原本带 `tabindex="0"` 的元素恢复为 0）；`it('covers when the page becomes hidden')`；`it('uses square corners when asked')`。
  - `BottomNav.test.tsx`：`it('marks the current item')`；`it('renders three columns without health')`（`--cols` 为 3）；`it('toggles the cover cell label and accessible name')`（遮盖、已遮盖；“遮盖敏感内容”、“已遮盖，点按恢复显示”；cover cell 是按钮而不是链接）。
  - `Button.test.tsx`：各变体的类名；小号带 `data-hit44`；禁用时不触发；`ButtonLink` 导航。
  - `marks.test.tsx`：`RefTag` 文字；`VerdictMark` 四种类名与默认文字；`ConfidenceCells` 对 0.91、0.84、0.58 分别是 5、4、3 格与“高、中、低”，aria-label 带两位小数。
  - `CountUp.test.tsx`：`it('shows the final value at once when motion is reduced')`；`it('counts to the final value within 600 ms')`（假定时器加 rAF 替身）。
  - `ruler.test.ts`：`it('places the 160 label 40 px left of the needle at 165 cm')`（width 304，ppu 8）；`it('places the 55 label 24 px left of the needle at 56.5 kg')`（width 304，ppu 16，step 0.5，major 5）；`it('drops labels that do not fit')`。`Ruler.test.tsx`：方向键按 step 改值、`aria-valuetext`、点数字后可输入新值。
  - `LedgerTicks.test.tsx`：格数、各段颜色类、`aria-label` 原样。
  - `EvidenceFold.test.tsx`：默认 `aria-expanded="false"`、条数胶囊、点按展开。
  - `CareBlock.test.tsx`：`role="alert"`、两个号码的 `tel:` 链接、固定说明；`SystemSlip.test.tsx`：`role="note"` 与“系统附注”。
  - `Sheet.test.tsx`：`it('moves focus to the title and back to the trigger')`；`it('closes on escape')`；`it('has no drag handle')`；`it('is solid while entering')`（打开时有 `data-entering`，派发 transitionend 后消失）；`it('hides toasts while open')`。
  - `ConfirmSheet.test.tsx`：`it('keeps confirm disabled until the acknowledgement is checked')`；`it('announces the result assertively')`；`it('shows the backend message and code on failure')`；`it('runs the secondary action')`。
  - `states.test.tsx`：五种状态各自的角色、标题与动作；`ErrorState` 显示 `message` 原文与“错误码 llm_timeout”，点“重试”调用 onRetry。
  - `Title.test.tsx`：`it('only the title component renders serif title classes')`：用 `fs` 扫描 `src/**/*.tsx`（排除 `components/Title.tsx` 与测试文件），不得出现字面量 `t-display`、`t-title`、`t-h`、`st-h` 类名。
  - `PageHeader.test.tsx`：哨兵离开时加 `stuck`；`cover` 时右上有遮盖按钮；返回键是 44 点按区。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/components` → FAIL（模块不存在）。
- [ ] **Step 3: 实现** 全部组件、样式与样张页。CSS 规则逐条对照 `index.html` 的同名类（第 95 至 885 行），把展示页外框专用的规则（`.deck*`、`.app` 画框、`.sb` 状态栏、`:has()` 留白）去掉；`.sens::after` 层级 4，外壳层级 8；面板的 `max-height: calc(100% - 56px)` 与下沿 `max(env(safe-area-inset-bottom), 8px)`；浮起的导航、底座、操作坞下边距 `max(calc(env(safe-area-inset-bottom) - 16px), 18px)`。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`。
- [ ] **Step 5: 版式与无障碍检查**：写 `e2e/pages/gallery.spec.ts`（`openAs` 不需要登录，直接打开 `/dev/gallery`）：两种宽度下 `expectTouchTargets`、`expectMinFontSize`、`expectNoHorizontalScroll`；主按钮计算高度 48、圆角 16，小按钮 36 加 `data-hit44`，导航高 60、左右各 8、下沿 18，开关 50×30；`expectGlass(page, true)`，在样张页的“减少透明”演示开关切到开后 `expectGlass(page, false)`；`expectForcedColorsSmoke`；样张里的遮盖面板 `expectCoverWorks`；减弱动效（`emulateMedia({ reducedMotion: 'reduce' })`）下骨架没有扫光、计数直接是终值。在 `frames.ts` 加 `ds`（设计系统一节对样张页）与 `st1` 至 `st12`（12 块状态面板对样张页对应区块），运行 `pnpm e2e:pages`、`pnpm visual`，打开 `test-results/visual/` 并排比较：颜色、圆角、材质、按钮与胶囊形状、骨架、就医提示的直角与出血、导航“积釉”与短线都与设计稿一致；不一致就改到一致再继续。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add design tokens, materials, glass mode, cover and shared components" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 4: 接口客户端、应用外壳、守卫与按能力清单的导航

**Files:**
- Create: `frontend/src/api/client.ts`、`token.ts`、`keys.ts`、`types.ts`、`hooks/auth.ts`、`hooks/disclaimer.ts`、`hooks/profile.ts`
- Create: `frontend/src/app/App.tsx`、`paths.ts`、`routes.tsx`、`guards.tsx`、`AppShell.tsx`、`nav.ts`、`queryClient.ts`、`profile.ts`、`BootSplash.tsx`、`PagePlaceholder.tsx`
- Create: 全部页面的占位文件（每个文件只导出渲染 `PagePlaceholder` 的默认组件，后续任务替换）：`src/features/auth/LoginPage.tsx`、`src/features/onboarding/DisclaimerPage.tsx`、`src/features/onboarding/OnboardingPage.tsx`、`src/features/chat/ChatPage.tsx`、`src/features/photos/PhotoNewPage.tsx`、`src/features/photos/PhotoResultPage.tsx`、`src/features/meals/RecordsPage.tsx`、`src/features/meals/MealNewPage.tsx`、`src/features/fitness/WorkoutNewPage.tsx`、`src/features/health/HealthPage.tsx`、`src/features/medical/MedicalNewPage.tsx`、`src/features/restaurants/RestaurantsPage.tsx`、`src/features/me/MePage.tsx`、`src/features/me/ProfileEditPage.tsx`、`src/features/settings/ModelsPage.tsx`、`src/features/settings/ModelNewPage.tsx`、`src/features/settings/PrivacyPage.tsx`、`src/features/settings/DisclaimerViewPage.tsx`
- Create: `frontend/src/lib/contract.ts`、`labels.ts`、`dates.ts`、`format.ts`
- Modify: `frontend/src/main.tsx`、`frontend/index.html`（内联启动外壳）、`frontend/src/test/render.tsx`（加 `renderRoute`）、`frontend/src/test/msw/handlers/index.ts`
- Create: `frontend/src/test/msw/handlers/core.ts`、`frontend/src/test/fixtures/core.ts`
- Create: `backend/tests/test_frontend_contract.py`
- Test: `src/api/client.test.ts`、`src/app/guards.test.tsx`、`src/app/nav.test.ts`、`src/app/profile.test.ts`、`src/app/routes.test.tsx`、`src/app/AppShell.test.tsx`、`src/lib/dates.test.ts`、`src/lib/format.test.ts`、`e2e/pages/shell.spec.ts`

**Interfaces:**
- Consumes: 任务 3 的全部组件；`schema.d.ts`。
- Produces:
  - `api/token.ts`：`TOKEN_KEY = 'goodlife.token'`；`getToken(): string | null`、`setToken(token: string)`、`clearToken()`（读写都 try/catch）。
  - `api/client.ts`：从 `api/errors.ts`（任务 3）引入并再导出 `ApiError`；`onUnauthorized(listener: () => void): () => void`；`api<T>(path: string, init?: { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; json?: unknown; body?: BodyInit; query?: Record<string, string | number | boolean | undefined>; signal?: AbortSignal }): Promise<T>`。行为：带令牌；`json` 时设 `Content-Type: application/json`；204 返回 undefined；非 2xx 时解析 `{"error": {"code", "message", "details"}}` 为 ApiError；响应不是 JSON 时 `new ApiError(status, 'http_error', '服务暂时不可用，请稍后再试（HTTP ' + status + '）')`；网络失败 `new ApiError(0, 'network_error', '网络连接失败，请检查网络后重试')`；401 且错误码是 `not_authenticated` 或 `invalid_token` 时 `clearToken()` 并通知 `onUnauthorized` 的监听者。
  - `api/keys.ts`：`qk` 对象，键名固定：`me`、`disclaimer`、`disclaimerStatus`、`profile`、`capabilities`、`conversations`、`conversation(id)`、`opening`、`agentSettings`、`reviews`、`medicalItems`、`itemEvents(id)`、`medicalEvents(limit)`、`orders`、`constraints(category)`、`summary(date)`、`meals(date)`、`foodSearch(q)`、`food(id)`、`recognitions`、`recognition(id)`、`recognitionImage(id)`、`periods`、`dayLogs(start, end)`、`prediction`、`phase`、`tips`、`cycleStats`、`weekSummary`、`workouts(start, end)`、`exerciseSearch(q)`、`exerciseTrend(id)`、`restaurantSettings`、`needs`、`presets`、`providers`、`providerModels(id)`、`assignments`、`grants`、`audits(clientName)`。
  - `api/types.ts`：从 `components['schemas']` 取别名（`UserOut`、`ProfileOut`、`ProfileUpdate`、`DisclaimerOut`、`DisclaimerStatus`、`ConversationOut`、`ConversationDetailOut`、`MessageOut`、`TurnOut`、`OpeningOut`、`MedicalItemOut`、`MedicalEventOut`、`EventOut`、`OrderOut`、`ConstraintsOut`、`ContinueBody`、`SummaryOut`、`MealOut`、`MealCreate`、`NutrientsOut`、`FoodDetailOut`、`NutritionSearchOut`、`RecognitionOut`、`RecognitionSummaryOut`、`PhotoItemOut`、`PhotoItemIn`、`PhotoEvaluationOut`、`PeriodOut`、`DayLogOut`、`DayLogIn`、`PredictionOut`、`PhaseOut`、`TipsOut`、`CycleStatsOut`、`WeekSummaryOut`、`WorkoutOut`、`WorkoutIn`、`ExerciseSearchOut`、`ExerciseTrendOut`、`RestaurantSettingsOut`、`NeedOut`、`RestaurantSearchIn`、`RestaurantSearchOut`、`PresetOut`、`ProviderOut`、`ModelOut`、`ModelUpdatedOut`、`AssignmentOut`、`ConnectionReportOut`、`FetchModelsOut`、`GrantOut`、`AuditOut`、`Capabilities = Record<'cycle' | 'medical' | 'nutrition' | 'fitness', boolean>`）。FastAPI 对重名模型（ItemOut、ReasonOut、EvaluationOut、SearchOut、SettingsOut）会生成带模块前缀的键，别名一律指向 `openapi.json` 里实际出现的那个键。
  - `api/hooks/auth.ts`：`useMe()`（GET `/api/auth/me`）、`useLogin()`（POST `/api/auth/login`，成功后 `setToken`）、`useRegister()`（POST `/api/auth/register`）、`useLogout()`（POST `/api/auth/logout` 后清令牌与缓存，接口失败也清）。`hooks/disclaimer.ts`：`useDisclaimer()`（GET `/api/disclaimer`）、`useDisclaimerStatus()`（GET `/api/disclaimer/status`）、`useAcceptDisclaimer()`（POST `/api/disclaimer/accept` `{version}`）。`hooks/profile.ts`：`useProfile()`（GET `/api/profile`）、`useUpdateProfile()`（PATCH `/api/profile`，成功后刷新 profile 与 capabilities）、`useCapabilities()`（GET `/api/me/capabilities`）。
  - `app/paths.ts`：`PATHS = { root: '/', login: '/login', disclaimer: '/disclaimer', onboarding: '/onboarding/:step', chat: '/chat', photoNew: '/photos/new', photoResult: '/photos/:recId', records: '/records', mealNew: '/records/meals/new', workoutNew: '/records/workouts/new', health: '/health', cycle: '/health/cycle', medical: '/health/medical', medicalNew: '/health/medical/new', restaurants: '/restaurants', me: '/me', profileEdit: '/me/profile', models: '/settings/models', modelNew: '/settings/models/new', privacy: '/settings/privacy', disclaimerView: '/settings/disclaimer', gallery: '/dev/gallery' } as const`；查询参数约定：`/records?tab=diet|training&date=YYYY-MM-DD`、`/records/meals/new?date=&meal=`、`/health/medical?tab=pending|active|history`。
  - `app/routes.tsx`：`RouteHandle = { nav: 'tabs' | 'chat' | 'none'; navKey?: NavItem['key']; sensitive: boolean }`；全部页面用 React Router 的 `lazy` 按路由拆包；守卫嵌套顺序 `RequireAuth` → `RequireDisclaimer` → `RequireProfile` → `AppShell`；`/` 重定向 `/chat`；`/health` 重定向到第一个可用分段（都没有时到 `/chat`）；`/health/cycle` 包 `RequireCapability anyOf={['cycle']}`，`/health/medical` 与 `/health/medical/new` 包 `['medical']`，`/records` 包 `['nutrition', 'fitness']`，餐厅、拍照与手动记一餐包 `['nutrition']`，训练表单包 `['fitness']`；`/dev/gallery` 只在 `import.meta.env.DEV || import.meta.env.VITE_GALLERY === '1'` 时注册。`sensitive` 为真的路由：chat、photoResult、records、health、cycle、medical、medicalNew、restaurants、me、profileEdit（DESIGN.md 第四节的表）。
  - `app/guards.tsx`：`RequireAuth`（没有令牌跳 `/login`）；`RequireDisclaimer`（`status.accepted` 为假跳 `/disclaimer`）；`RequireProfile`（`isProfileComplete` 为假跳 `/onboarding/<firstIncompleteStep>`）；`RequireCapability({ anyOf: ('cycle' | 'medical' | 'nutrition' | 'fitness')[] })`（列出的能力全为假时跳 `/chat`）；加载中渲染 `BootSplash`；守卫里的请求失败渲染 `ErrorState` 带重试。`/login` 已登录时跳 `/`；`/disclaimer` 只要求登录；`/onboarding/:step` 要求登录与免责。
  - `app/profile.ts`：`isProfileComplete(p: ProfileOut): boolean`（见“已定的取舍”）；`firstIncompleteStep(p): 1 | 2`（基本信息四项与性别缺任一为 1，否则 2）。
  - `app/nav.ts`：`navItems(caps: Capabilities): NavItem[]`（对话；`nutrition || fitness` 时记录；`cycle || medical` 时健康；我的）；`healthSegments(caps): ('cycle' | 'medical')[]`；`recordSegments(caps): ('diet' | 'training')[]`。
  - `app/AppShell.tsx`：渲染 `Field`、唯一的滚动容器 `<main data-scroller>`（`padding-bottom` 由 handle 决定：tabs 104、chat 196、none 28；页面可用 `useDockPadding('short' | 'tall')` 改为 112 或 172）、`<Outlet />`、`handle.nav === 'tabs'` 时在 `#shell-root` 渲染 `BottomNav`；提供 `useScroller(): RefObject<HTMLElement>`；本任务把任务 3 的 `Dock` 接上：挂载时调用 `useDockPadding(tall ? 'tall' : 'short')`，卸载时恢复；启动 `startLowEndProbe`；挂载 `onUnauthorized` 监听（清缓存，跳 `/login`，state `{ expired: true }`）；首帧后移除启动外壳 `#boot-shell`。
  - `App.tsx`：`QueryClientProvider`（`queryClient.ts`：`retry` 只对 5xx 与网络错误重试一次、`staleTime 30000`、`refetchOnWindowFocus: false`）、`GlassModeProvider`、`CoverProvider`、`ToastProvider`、`RouterProvider`。
  - `index.html` 启动外壳：内联一小段 CSS（`body` 背景场与 `--chrome-solid` 实色）与 `<div id="boot-shell">`，路径是 `/` 或 `/chat` 时画出对话页的页头文字“对话”与底座轮廓（实色材质，尺寸与任务 6 的对话页一致）；其他路径用内联脚本把它隐藏。
  - `lib/contract.ts`（后端固定文案与常量的副本，任务 6 至 10 引用）：`HEALTH_DISCLAIMER`、`NOTICE_HEADER_PREFIX = '按你当前生效的医嘱，以下食物不建议：'`、`DUE_REASONS: Record<string, 'review' | 'end'>`（四句原文：已到复查日期、已过预计结束日期、今天是预计结束日期、即将到预计结束日期，每句后面都是“，请确认是否还需要继续遵守”；第一句映射 review，其余映射 end）、`PENDING_REVIEW_NOTE`（`app.nutrition.engine.PENDING_REVIEW_NOTE` 原文）、`SOURCE_NAMES`（`app.nutrition.engine.SOURCE_NAMES` 六项原文）、`REVIEW_REASON_CODES = ['low_confidence', 'needs_confirmation', 'grams_out_of_range', 'estimated_grams']`、`LOW_CONFIDENCE = 0.6`、`PHOTO_MEAL_NOTE = '拍照识别'`、`AGENT_CLIENT_NAME = 'agent'`、`MESSAGE_MAX_CHARS = 2000`、`MAX_NEEDS = 3`、`RISK_FLAG_PREFIX = 'risk_'`、`RISK_CATEGORIES = ['medication', 'pregnancy', 'severe_symptom', 'extreme_diet', 'self_harm']`、`FLAG_CLUE = 'resolution_clue'`、`FLAG_FALLBACK = 'guard_fallback'`。
  - `lib/labels.ts`（类型都是 `Record<枚举, string>`，由 TypeScript 保证覆盖完整）：`MEAL_LABELS`（早餐、午餐、晚餐、加餐）、`CONCLUSION_LABELS`（suitable 适合、caution 注意、not_recommended 不建议、unchecked 未核对）、`CATEGORY_LABELS`（diet_avoid 饮食禁忌、diet_require 饮食要求、medication_diet 用药相关饮食注意、exercise_limit 运动限制、other 其他）、`ITEM_STATUS_LABELS`（待核对、生效中、待复核、已解除、已作废）、`EVENT_ACTION_LABELS`（created 提取为待核对或手动录入（按 source 区分）、confirmed 确认生效、edited 修改、voided 作废、expired 自动作废、continued 继续执行、review_due 进入待复核、resolution_proposed 提出解除建议、resolution_proposal_cancelled 撤销解除建议、resolved 确认解除）、`EVENT_SOURCE_LABELS`（user 你本人、system 系统（打开应用时检查）、extractor 提取、agent 助手）、`CONFIDENCE_LABELS`（高、中、低）、`ACTIVITY_LABELS` 与 `ACTIVITY_HINTS`（sedentary 久坐：几乎不运动；light 轻度：每周运动 1 到 3 次；moderate 中度：每周运动 3 到 5 次；active 活跃：每周运动 6 到 7 次；very_active 非常活跃：体力劳动或每天高强度训练）、`GOAL_LABELS`（减脂、增肌、维持、不设）、`GENDER_LABELS`（女、男、其他）、`FLOW_LABELS`（无、点滴、少、中、多）、`MOOD_LABELS`（好、一般、低落、烦躁、焦虑）、`PHASE_TITLE_KEYS`（menstrual 到 `phaseMenstrual` 等，unknown 到 `phaseUnknown`）、`MUSCLE_LABELS`（胸、背、肩、肱二头肌、肱三头肌、股四头肌、腘绳肌、臀、小腿、核心、全身）、`EQUIPMENT_LABELS`（杠铃、哑铃、器械、绳索、徒手、壶铃、弹力带、无、其他）、`ACCESS_LABELS`（只读、读写）、`GRANT_STATUS_LABELS`（有效、已过期、已吊销）、`AUDIT_OUTCOME_LABELS`（ok 成功、error 失败）、`CLIENT_LABELS`（agent 应用内助手；其他客户端名原样显示）、`PURPOSE_LABELS`（chat 日常对话、vision 看图识别）、`PROVIDER_KIND_LABELS`（openai_compatible OpenAI 兼容格式、anthropic Anthropic、gemini Gemini）、`CAPABILITY_LABELS`（vision 看图、tools 工具调用、chat 对话）、`REVIEW_REASON_LABELS`（low_confidence 把握较低，建议核对菜名；needs_confirmation 没有匹配到营养库，不计入合计，请选择对应的食物、改名或删除；grams_out_of_range 克数不在常见范围内，请核对；estimated_grams 克数是估算的，建议核对）、`RISK_TITLE_KEYS`（severe_symptom 与 pregnancy 用 `careSevere`、self_harm 用 `careSelfHarm`、medication 用 `careMedication`、extreme_diet 用 `careDiet`）、`RISK_PHONES`（self_harm 与 extreme_diet 为 120 与 12356，其余为 120）。
  - `lib/dates.ts`：`todayISO()`、`addDays(iso, n)`、`addMonths(iso, n)`、`mondayOf(iso)`、`formatMonthDay(iso)`（“10月12日”）、`formatWeekday(iso)`（“周一”）、`formatTime(isoDateTime)`（本地 “18:40”）、`dayLabel(isoDateTime, now)`（“今天 18:40”“昨天 19:02”“10月9日”）、`formatStamp(isoDateTime)`（“10-12 18:40”）、`defaultMealType(now: Date)`（10 点前早餐、14 点前午餐、17 点前加餐、其余晚餐，只是表单默认值）。`lib/format.ts`：`fmtInt(n)`（千分位，1085 写作 1,085）、`fmtNum(n, digits)`、`fmtDistance(m)`（不足 1000 写“320 米”，否则“1.2 公里”）、`fmtBytes(n)`（“1.2 MB”）。
  - `test/render.tsx` 新增 `renderRoute(path: string, opts?: { token?: string | null; capabilities?: Partial<Capabilities>; profile?: Partial<ProfileOut>; accepted?: boolean }): RenderResult & { router }`：用 `createMemoryRouter(routes)` 与全套 Provider 渲染，并为 `/api/auth/me`、`/api/disclaimer/status`、`/api/profile`、`/api/me/capabilities` 装上按参数生成的 MSW 处理器。
  - `backend/tests/test_frontend_contract.py`：读 `frontend/src/lib/contract.ts` 的文本，断言其中逐字包含：`app.agent.safety.HEALTH_DISCLAIMER`；`app.agent.guard.NOTICE_HEADER.split("{foods}")[0]`；用 `SimpleNamespace` 调用 `app.medical.items._due_reason` 得到的四句原文；`app.nutrition.engine.PENDING_REVIEW_NOTE`；`SOURCE_NAMES` 每一项写成 `<键>: '<值>'`；`app.photos.matching.REVIEW_REASONS` 每一个；`LOW_CONFIDENCE = <REVIEW_CONFIDENCE>`；`app.photos.service.MEAL_NOTE`；`app.agent.assembly.CLIENT_NAME`；`MESSAGE_MAX_CHARS = <MAX_MESSAGE_CHARS>`；`MAX_NEEDS = <app.restaurants.needs.MAX_NEEDS>`；`RISK_CATEGORIES` 每一个；`FLAG_CLUE` 与 `FLAG_FALLBACK` 的值。

- [ ] **Step 1: 写失败测试**
  - `client.test.ts`：`it('sends the bearer token')`；`it('parses the unified error body with details')`；`it('maps a non json error to http_error')`；`it('maps a network failure to network_error')`；`it('clears the token and notifies on invalid_token')`；`it('does not clear the token on invalid_credentials')`；`it('returns undefined for 204')`；`it('serialises query parameters and skips undefined')`。
  - `guards.test.tsx`：`it('sends a visitor without a token to login')`；`it('sends an unaccepted user to the disclaimer before anything else')`；`it('sends an incomplete profile to the first missing onboarding step')`（缺身高去第 1 步，只缺目标去第 2 步）；`it('lets a complete user reach chat')`；`it('redirects a user without the cycle module away from the cycle page')`；`it('returns to login with the expired notice after a 401')`。
  - `profile.test.ts`：完整、缺一项、goal 为 none 也算完整。
  - `nav.test.ts`：`it('shows four items for a female user')`；`it('shows health for a male user because medical is open')`；`it('drops health when neither cycle nor medical is open')`（三项）；`healthSegments` 与 `recordSegments` 的组合。
  - `routes.test.tsx`：`it('registers a route for every path')`（`PATHS` 每一项都能匹配到路由，gallery 只在测试的开发模式下注册）；`it('marks the sensitive pages from the design')`。
  - `AppShell.test.tsx`：tabs 路由渲染底部导航进 `#shell-root`；none 路由没有导航；首帧后 `#boot-shell` 被移除。
  - `dates.test.ts`、`format.test.ts`：上面每个函数至少两个用例（含跨月、闰年、千分位、米与公里）。
  - `backend/tests/test_frontend_contract.py`：`test_contract_copies_match_the_backend`。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/api src/app src/lib`；`uv run pytest tests/test_frontend_contract.py -q -W error` → FAIL。
- [ ] **Step 3: 实现** 上面全部内容；把任务 3 里 `VerdictMark` 的默认文字改为引用 `CONCLUSION_LABELS`，`ConfidenceCells` 的阈值改为引用 `LOW_CONFIDENCE`；`main.tsx` 改为渲染 `App`。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`uv run pytest tests/test_frontend_contract.py -q -W error`。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/shell.spec.ts`：用 `createUser(profile: 'complete')` 登录后打开 `/records` 与 `/me` 占位页，两种宽度下导航左右 8、下沿 18、高 60、遮盖格 60 宽，`expectTouchTargets`、`expectNoHorizontalScroll`；打开 `/chat` 时用 PerformanceObserver 收集 `layout-shift`，加载完成后累计不超过 0.05；男性用户导航四项且健康页没有“经期”字样（任务 9 后再补经期内容）。运行 `pnpm e2e:pages`。
- [ ] **Step 6: 提交**

  ```
  git add frontend backend/tests/test_frontend_contract.py
  git commit -m "feat(frontend): add API client, app shell, guards and capability-driven navigation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 5: 登录注册、免责确认、建档向导、我的与修改档案

**Files:**
- Modify（替换占位）: `src/features/auth/LoginPage.tsx`、`src/features/onboarding/DisclaimerPage.tsx`、`src/features/onboarding/OnboardingPage.tsx`、`src/features/me/MePage.tsx`、`src/features/me/ProfileEditPage.tsx`
- Create: `src/features/onboarding/StepBasics.tsx`、`StepActivity.tsx`、`StepDiet.tsx`、`src/features/onboarding/fieldErrors.ts`
- Create: `src/api/hooks/agent.ts`（本任务只放 `useAgentSettings`、`useUpdateAgentSettings`，任务 6 补全）、`src/api/hooks/llm.ts`（本任务只放 `useProviders`、`useAssignments`，任务 10 补全）
- Create: `src/test/msw/handlers/auth.ts`、`src/test/fixtures/profile.ts`
- Test: `LoginPage.test.tsx`、`DisclaimerPage.test.tsx`、`OnboardingPage.test.tsx`、`MePage.test.tsx`、`ProfileEditPage.test.tsx`、`fieldErrors.test.ts`、`e2e/pages/onboarding.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 01、01b、02、13a、13b）

**Interfaces:**
- Consumes: 任务 3 的 `SegmentedTabs`、`TextField`、`PasswordField`、`Button`、`Checkbox`、`Dock`、`Ruler`、`RadioSegment`、`TagField`、`Switch`、`Sensitive`、`PageHeader`、`Title`；任务 4 的 hooks、`PATHS`、`labels.ts`。
- Produces:
  - 接口：`POST /api/auth/register {username, password}`（201）→ 立即 `POST /api/auth/login`；`GET /api/disclaimer` 的 `text` 按换行切成条目、`version` 显示在页头；`POST /api/disclaimer/accept {version}`；`PATCH /api/profile`（`ProfileUpdate` 的字段）；`GET /api/auth/me`（`username`、`created_at`）；`GET /api/agent/settings` 与 `PUT /api/agent/settings {openings_enabled}`；`GET /api/llm/providers` 与 `GET /api/llm/assignments`（我的页“模型服务”一行的摘要：“N 个，对话已设置”或“未设置”）；`GET /api/disclaimer/status`（“已确认 {version} 版”）。
  - `fieldErrors(error: ApiError): Record<string, string>`：把 `validation_error` 的 `details` 按字段名归位（字段名取 `field` 的最后一段），供各表单使用；业务错误码 `username_taken` 归到 username，`invalid_credentials` 归到整个表单。
  - 登录页（01）：分段 登录/注册；用户名提示“3 到 32 位，字母、数字或下划线”、密码提示“至少 8 位”（这两句是界面提示，校验以后端为准）；注册成功后进入免责页；`location.state.expired` 时顶部显示 `AuthNeededState`（`sessionExpired`，“请重新登录，记录不会丢失。”）。
  - 免责页（01b）：没有返回键；勾选“我已阅读并理解以上内容”后“确认并继续”可用（操作坞 tall）；409 `disclaimer_outdated` 时显示后端说明并重新读取正文。
  - 建档页（02 与线框）：`/onboarding/1` 出生年份（`SelectField`，近 100 年）、性别（`RadioSegment` 女、男、其他，下方“用于估算能量需要，也决定是否显示经期记录。”）、身高 `Ruler`（ppu 8、step 1、major 10、50 到 250，默认取档案值否则 165）、体重 `Ruler`（ppu 16、step 0.5、major 5、20 到 300，默认档案值否则 60）；`/onboarding/2` 活动水平五档单选（每档名称加 `ACTIVITY_HINTS`）、目标四选一；`/onboarding/3` 饮食偏好与忌口两组 `TagField`、健康状况多行输入（下方“只用于生成建议。医生的要求请到医嘱页录入，才会按约束执行。”），操作坞“完成”与文字按钮“跳过这一步”。每一步“下一步”都 PATCH 本步字段后再前进；第 3 步完成或跳过后到 `/chat`。进度条三段（`.steps`）。
  - 我的（13a）：用户名与注册日期；三列事实格（出生年份、性别、活动水平、身高、体重、目标，数字用 `.ns`）；忌口与健康状况两行；“修改档案”；两个开关整行 56 高：“打开应用时主动提问”（agent settings）与“经期记录”（只在 `profile.gender === 'female'` 时显示，开关值为 `!cycle_tracking_opt_out`，切换后刷新能力清单，导航随之变化）；链接到模型服务、隐私与数据（右侧写“含‘减少透明’”）、免责声明；“退出登录”。档案摘要与两个开关在 `Sensitive` 里。
  - 修改档案（13b）：身高、体重（`TextField inputMode="decimal"`）、活动水平（`SelectField`）、目标、两组标签、健康状况；右上遮盖按钮；页脚说明“出生年份 X，性别 Y；上次更新 日期”；操作坞“保存”，成功后返回我的并轻提示“已保存”；`validation_error` 的字段错误显示在对应字段下。

- [ ] **Step 1: 写失败测试**
  - `LoginPage.test.tsx`：`it('registers then logs in and goes to the disclaimer')`；`it('shows username_taken under the username field')`；`it('shows invalid credentials as a form error and keeps the token empty')`；`it('shows the expired notice after a 401')`；`it('maps validation details to fields')`。
  - `DisclaimerPage.test.tsx`：`it('shows the backend text line by line with its version')`；`it('enables confirm only after the checkbox')`；`it('accepts the shown version and continues to onboarding')`；`it('reloads on disclaimer_outdated and shows the message')`；`it('has no back button')`。
  - `OnboardingPage.test.tsx`：`it('saves step one with gender, birth year, height and weight')`（请求体逐字段断言）；`it('resumes at the first incomplete step')`；`it('saves activity and goal on step two')`；`it('lets step three be skipped')`；`it('saves tags and health conditions on step three')`；`it('exposes the rulers as sliders with value text')`。
  - `MePage.test.tsx`：`it('shows profile facts inside a sensitive region')`；`it('toggles openings through the agent settings api')`；`it('shows the cycle switch only for female users and updates capabilities')`；`it('summarises model services from providers and assignments')`；`it('logs out and returns to login')`。
  - `ProfileEditPage.test.tsx`：`it('patches only changed fields')`；`it('shows field errors from the backend')`；`it('has a cover button in the header')`。
  - `fieldErrors.test.ts`。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/features/auth src/features/onboarding src/features/me` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/onboarding.spec.ts`：两种宽度下登录、免责、建档三步、我的、修改档案各页 `expectTouchTargets`、`expectMinFontSize`、`expectNoHorizontalScroll`；刻度尺容器宽在 360 下为 304、390 下为 334；165 厘米时 160 的标签中心在指针左边 40 像素；分段控件每段高 44；输入框高 52、聚焦时 2 像素钴蓝内描边；我的与修改档案 `expectCoverWorks`。`frames.ts` 加 01（`/login`）、01b（新用户的 `/disclaimer`）、02（`/onboarding/1`）、13a（`/me`）、13b（`/me/profile`），运行 `pnpm visual` 并排比较后修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add login, disclaimer, onboarding, me and profile pages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 6: 聊天（流式回答、依据、附注、就医提示、开场卡片、待处理条、继续遵守面板）

**Files:**
- Create: `src/api/sse.ts`；Modify: `src/api/hooks/agent.ts`（补全）、`src/api/hooks/llm.ts`（`useAssignments` 已有）
- Create: `src/api/hooks/medical.ts`（本任务放 `useMedicalReviews`、`useMedicalItems`、`useItemEvents`、`useContinueItem`、`useCancelProposal`，任务 8 补全）
- Modify（替换占位）: `src/features/chat/ChatPage.tsx`
- Create: `src/features/chat/ChatDock.tsx`、`MessageList.tsx`、`AssistantMessage.tsx`、`UserMessage.tsx`、`OpeningCard.tsx`、`openingActions.ts`、`PendingStrip.tsx`、`NoModelPrompt.tsx`、`agentText.ts`、`useChatStream.ts`、`useVisualViewportInset.ts`
- Create: `src/features/medical/ContinueSheet.tsx`、`dueReason.ts`、`proposer.ts`、`useItemContext.ts`
- Create: `src/lib/photoHandoff.ts`
- Create: `src/test/msw/handlers/agent.ts`、`medical.ts`，`src/test/fixtures/agent.ts`、`medical.ts`
- Test: `sse.test.ts`、`agentText.test.ts`、`useChatStream.test.tsx`、`ChatPage.test.tsx`、`OpeningCard.test.tsx`、`PendingStrip.test.tsx`、`ContinueSheet.test.tsx`、`dueReason.test.ts`、`e2e/pages/chat.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 03a、03b、03c、03d、03e、03f）

**Interfaces:**
- Consumes: 任务 3 的 `EvidenceFold`、`SystemSlip`、`CareBlock`、`RefTag`、`JumpCard`、`Sheet`、`WillList`、`ThoughtLine`、`ErrorState`、`AuthNeededState`、`BottomNav`（embedded）、`Sensitive`；任务 4 的 `contract.ts`、`labels.ts`、`dates.ts`、`navItems`。
- Produces:
  - `api/sse.ts`：`type StreamEvent = { type: 'delta'; text: string } | { type: 'done'; turn: TurnDone } | { type: 'error'; code: string; message: string; status: number }`，`TurnDone = { message_id: string; evidence: string; flags: string[]; tools_used: string[] }`；`createSseParser(onEvent: (name: string, data: string) => void): { push(text: string): void; end(): void }`（统一 CRLF，按空行分事件，`data:` 多行用换行连接，忽略以冒号开头的注释行，跨块拼接）；`streamMessage(conversationId: string, text: string, opts: { signal?: AbortSignal; onEvent: (e: StreamEvent) => void }): Promise<void>`：POST `/api/agent/conversations/{id}/messages` `{ text, stream: true }`，`Accept: text/event-stream`；200 时用 `TextDecoder('utf-8', { stream: true })` 逐块解码；非 200 且是 `text/event-stream` 时读完并发出 `error` 事件（带状态码）；非 200 的 JSON 按 `api` 的规则转成 ApiError 抛出（含 401 处理）；网络失败抛 `network_error`。
  - `agentText.ts`：`splitAssistantText(text: string): { answer: string; notice: { lines: string[] } | null; disclaimer: string | null }`（末尾 `\n\n` 加 `HEALTH_DISCLAIMER` 时取出为 disclaimer；以 `NOTICE_HEADER_PREFIX` 开头的那一段起到 disclaimer 之前是 notice，按换行切成行，第一行是“按你当前生效的医嘱，以下食物不建议：……。”，其余每行“食物：说明”）；`visibleWhileStreaming(acc: string): string`（找到第一个 `\n\n`，若其后的文字是 `NOTICE_HEADER_PREFIX` 或 `HEALTH_DISCLAIMER` 的前缀或以它们开头，就只显示到它之前，避免附注与免责句在流入时闪进气泡）；`riskCategory(flags: string[]): RiskCategory | null`；`collapseRetriedUserMessages(messages: MessageOut[]): MessageOut[]`（相邻两条用户消息文字相同时只保留后一条）；`evidenceLines(evidence: string): string[]`；`jumpCardsFor(toolsUsed: string[], caps: Capabilities): { to: string; label: string }[]`（`nutrition_log_meal` 去看今天的饮食记录 `/records?tab=diet`、`fitness_log_workout` 去看训练记录 `/records?tab=training`、`medical_submit_order` 去医嘱页核对 `/health/medical?tab=pending`、`cycle_record_period` 去看经期 `/health/cycle`、`nutrition_nearby_restaurants` 去看附近餐厅 `/restaurants`；能力未开放的不给）。
  - `api/hooks/agent.ts`：`useConversations()`（GET `/api/agent/conversations`）、`useConversation(id)`（GET `/api/agent/conversations/{id}`）、`useCreateConversation()`（POST `/api/agent/conversations {}`）、`useOpening()`（GET `/api/agent/opening`，`staleTime: Infinity`，一次打开应用只取一次）、`useDeclineOpening()`（POST `/api/agent/opening/{id}/decline`）、`useAnswerOpening()`（POST `/api/agent/opening/{id}/answer`）、`useAgentSettings`、`useUpdateAgentSettings`。
  - `useChatStream(conversationId: string | null, ensureConversation: () => Promise<string>)`：返回 `{ live: { userText: string; text: string; phase: 'waiting' | 'streaming' | 'done' | 'error'; turn?: TurnDone; error?: ApiError } | null; send(text: string): Promise<void>; retry(): Promise<void> }`。发送时先显示用户气泡与 `ThoughtLine`（“正在查询你的记录并组织回答”，`aria-busy="true"`）；delta 按动画帧合批追加文本节点（减弱动效时攒到 done 一次显示）；done 后刷新会话，列表里出现 `id === turn.message_id` 的助手消息时移除临时气泡（不闪、不重复）；error 时保留用户原话，`retry` 用同一句话重发。
  - `api/hooks/medical.ts`（本任务部分）：`useMedicalReviews()`（GET `/api/medical/reviews`，只在 `caps.medical` 时启用）、`useMedicalItems()`（GET `/api/medical/items`）、`useItemEvents(id, enabled)`（GET `/api/medical/items/{id}/events`）、`useContinueItem()`（POST `/api/medical/items/{id}/continue` `{ review_date, end_date }`）、`useCancelProposal()`（POST `/api/medical/items/{id}/cancel-proposal`）；修改类钩子成功后刷新 reviews、medicalItems、constraints 与该条目的事件。
  - `features/medical/dueReason.ts`：`dueReasonOf(events: EventOut[]): string | null`（最后一条 `review_due` 的 `detail.reason`）；`dueFieldOf(reason: string | null): 'review' | 'end' | null`（查 `DUE_REASONS`）；`shortDue(reason: string): string`（取第一个“，”之前的部分，例如“已到复查日期”）。`proposer.ts`：`proposerOf(events): 'agent' | 'user' | null`（最后一条 `resolution_proposed` 的 source）。`useItemContext(item: MedicalItemOut)`：待复核或带建议时取事件，返回 `{ dueReason, dueField, proposer }`。
  - `ContinueSheet({ item: MedicalItemOut; dueReason: string | null; isOpen; onClose; onDone? })`（03d）：引文框（类别、内容、“生效 日期”）；“两个日期一起提交，留空的一项会被清除。”；复查日期行与预计结束行都显示，旁边写“原 日期”或“原 未设”；`dueFieldOf(dueReason)` 那一行加赭色圆头竖线并显示 `dueReason` 原文；复查日期快捷项“1 个月后”“3 个月后”“不再设”，也可选任意日期，触发项是复查日期时默认选中“1 个月后”，否则预填原值；预计结束默认原值（null 显示“不设（长期）”）；后果清单随选择变化：“状态从‘待复核’回到‘生效中’，建议继续按它约束。”、“复查日期改为 某日，那天打开应用时会再次提醒复核。”或“不再设复查日期。”、“预计结束保持不设，继续长期有效。”或“预计结束保持 某日，结束前一天起进入待复核。”或“预计结束改为 某日，结束前一天起进入待复核。”、“记一条审计：时间、由你本人确认、两个新日期。”；提交永远同时带 `review_date` 与 `end_date` 两个键（可为 null）；422 `still_due` 的说明显示在触发项下面，`invalid_item_dates` 显示在对应字段下；成功后关闭、轻提示“已继续遵守”并调用 onDone。
  - `openingActions.ts`：`openingActionsFor(opening: OpeningOut, target: MedicalItemOut | undefined, caps): OpeningAction[]`，`OpeningAction = { label: string; kind: 'continue' | 'navigate' | 'decline'; to?: string }`：review_due 且目标待复核：继续遵守、去医嘱页处理（`/health/medical?tab=active`）、稍后；review_due 且目标只带建议：去医嘱页处理、稍后；period_soon：看看安排（`/health/cycle`）、不用了；trained_no_meal_yesterday：去补记（`/records/meals/new?date=<昨天>`）、不用了；no_meal_today：拍一张（`/photos/new`）、手动记（`/records/meals/new`）、不用了；profile_stale：更新档案（`/me/profile`）、不用了；未知类型只有“不用了”。navigate 与 continue 成功都调用 answer，decline 调用 decline。
  - `OpeningCard({ opening; target?; onCollapsed })`（静玻璃，钴蓝圆头竖线，“今天想问你”，问句原文 18 号黑体 500）；稍后之后卡片收起，`review_due` 的目标进入待处理条。
  - `PendingStrip({ items: MedicalItemOut[] })`（03a、03e）：放在页头里的白瓷条，`Sensitive` 包住；收起时一条写“类别　待复核”或“类别　有解除建议”，多条写“医嘱待处理 N 条”，不放原文，含数值的文字不截断；展开后每条：类别、状态（待复核写“待复核，{shortDue}”，带建议写“有解除建议”）、内容原文、带建议的写“{助手或你}根据 某日 的话提出，仍在生效”加 `RefTag`；动作：待复核为“继续遵守”（打开 ContinueSheet）与“去医嘱页处理”，带建议为“不解除”（cancel-proposal，轻提示“已撤销解除建议”）与“去医嘱页处理”；正在作为开场卡片显示的那一条不出现在这里。
  - `NoModelPrompt()`：`AuthNeededState`（`noModel`，“对话和拍照识别都需要先添加一个模型服务，填地址与密钥，大约两分钟。”，按钮“去添加模型服务”到 `/settings/models/new`）；`GET /api/llm/assignments` 里没有 `purpose === 'chat'` 时显示在消息列表末尾，发消息遇到 409 `agent_model_not_configured` 时也显示。
  - `AssistantMessage({ message: { id; text; evidence; flags }; caps; live?: boolean; toolsUsed?: string[] })`：有 `risk_*` 时只渲染“系统”标签加 `CareBlock`（标题 `RISK_TITLE_KEYS`、正文是后端原文、号码 `RISK_PHONES`），不接其他内容；否则白瓷气泡（起点一角 8）里写 `answer`，下面 `EvidenceFold`（有依据时）、`RefTag` 加 disclaimer 原文；`notice` 画成 `SystemSlip`（标题“医嘱提醒”）；`guard_fallback` 时气泡下加一行“这是一条固定的安全回答，不是模型生成的。”；`resolution_clue` 且医嘱模块开放时只加一个 `JumpCard`“去医嘱页处理”到 `/health/medical?tab=active`；`toolsUsed` 生成的跳转卡片只出现在本次流式回答下。依据、附注与“仅供参考”在流完后才淡入上移 4 像素。
  - `MessageList`：`Sensitive square` 包住整段消息流，`aria-live="polite"`；日期分隔用 `dayLabel`；用户气泡钴蓝；列表只在末尾追加。
  - `ChatDock`（对话底座，活玻璃，渲染进 `#shell-root`）：快捷操作胶囊“附近吃什么”（`/restaurants`，nutrition 开放时）、“记一餐”（`/records/meals/new`，nutrition 开放时）、“看医嘱”（`/health/medical`，medical 开放时），最后一条助手消息是就医提示时整行隐藏；输入行：拍照按钮（隐藏的 `<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment">`）、相册按钮（同样的 accept、没有 capture）、多行输入框（`maxLength={MESSAGE_MAX_CHARS}`，胶囊形，Enter 发送、Shift+Enter 换行）、发送键；下面嵌入 `BottomNav embedded`。选了图片后 `setPendingPhoto(file)` 并导航到 `/photos/new`。
  - `lib/photoHandoff.ts`：`setPendingPhoto(file: File)`、`takePendingPhoto(): File | null`（模块内存，取走即清空）。
  - `useVisualViewportInset()`：iOS 软键盘弹起时（`visualViewport.height` 小于 `innerHeight`）在根节点设 `--kb` 为键盘高度，对话底座贴在键盘上沿、导航那一行隐藏；安卓靠 `interactive-widget=resizes-content`。
  - `ChatPage`：页头（`variant="chat"`，“对话”加今天的日期与星期，待处理条在页头里）；会话取 `useConversations()` 的第一个，没有时首次发送前调用 `useCreateConversation`；历史用 `collapseRetriedUserMessages` 后显示；开场卡片放在历史之后、为它与待处理条预留高度以免布局偏移。

- [ ] **Step 1: 写失败测试**
  - `sse.test.ts`：`it('parses events split across chunks')`；`it('handles crlf and multi line data')`；`it('ignores comments and unknown events')`；`it('decodes a multi byte character split between chunks')`；`it('reports an error event from a non 200 event stream with its status')`（MSW 返回 502 与 `event: error`）；`it('throws an api error for a non 200 json response')`；`it('clears the token on a 401 json response')`；`it('maps a network failure to network_error')`。
  - `agentText.test.ts`：`it('splits answer, notice and disclaimer')`（文本按 `app/agent/loop.py` 第 478 行的拼法构造）；`it('keeps a risk reply whole')`；`it('handles an answer without notice')`；`it('holds back a partial notice or disclaimer while streaming')`；`it('collapses a retried user message')`；`it('maps tools to jump cards only for open modules')`。
  - `useChatStream.test.tsx`：`it('shows the user text and a thinking line at once')`；`it('appends deltas and replaces the live bubble with the saved message by id')`（MSW 的会话处理器在 done 后返回带同一 id 的消息，最终只有一条助手消息）；`it('shows the whole answer at once when motion is reduced')`；`it('keeps the text and retries with it after an error')`（第二次请求体里的 text 与第一次相同）；`it('shows the no model prompt on agent_model_not_configured')`。
  - `ChatPage.test.tsx`：`it('shows the reference tag beside every assistant answer')`（验收 8）；`it('renders the medical notice as a system slip outside the answer bubble')`；`it('renders a risk reply as a care alert and hides quick actions')`；`it('labels a fixed fallback reply')`；`it('shows only a jump to the medical page for a resolution clue')`；`it('offers no confirm or resolve control anywhere in chat')`（同时有开场卡片、展开的待处理条、带线索的回答时，页面上没有名为“确认生效”“确认解除”的按钮，验收 3）；`it('folds evidence with its line count')`；`it('shows the no model prompt when chat is unassigned')`；`it('hides the medical quick action without the medical module')`；`it('offers camera and gallery inputs')`（拍照的 input 带 `capture="environment"`，相册的不带，accept 相同）；`it('hands a picked photo to the photo page')`；`it('wraps the stream and the strip in sensitive regions')`；`it('marks the answer busy while streaming')`。
  - `OpeningCard.test.tsx`：`it('offers continue, go to medical and later for a due item')`；`it('drops continue when the first review only has a proposal')`；`it('declines on later and collapses into the strip')`；`it('answers after continuing in the sheet')`；`it('maps other kinds to their jump actions')`。
  - `PendingStrip.test.tsx`：`it('describes a single item by category and state')`；`it('counts several items')`；`it('never truncates text with numbers')`（内容含“2000 毫克”时没有省略号）；`it('offers continue for a due item and keep for a proposal')`；`it('names who proposed and marks it for reference')`；`it('excludes the item shown as the opening card')`。
  - `ContinueSheet.test.tsx`：`it('shows both dates prefilled with their old values')`；`it('marks the field that triggered the review with the backend reason')`；`it('always submits both dates')`（选“不再设”后请求体是 `{"review_date": null, "end_date": <原值>}`，两个键都在）；`it('updates the consequence list with the choices')`；`it('shows still_due under the triggering field')`；`it('moves focus to the title and closes after success')`。
  - `dueReason.test.ts`：四句原文各自映射到正确的字段；`shortDue`；没有 review_due 事件时为 null。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/api/sse.test.ts src/features/chat src/features/medical` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build:check`（对话路由预算此时开始生效）。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/chat.spec.ts`（用 `seedModelService` 配好模拟模型，`sendMessage` 写入几轮历史；“晚饭吃什么”得到带依据的回答；“胸口很闷，一直出冷汗”得到就医提示；`seedReviewDueItem` 与 `seedProposal` 准备开场与待处理条）：两种宽度下对话底座左右 8、下沿 18，快捷胶囊 36 高带 `data-hit44`，输入框 44 高，用户气泡圆角为 22 22 8 22、助手气泡 8 22 22 22；就医提示左右贴屏幕边、圆角 0；滚动后页头加 `stuck`、玻璃层出现；页头与底座的模糊面积合计不超过视口 40%；`expectTouchTargets`、`expectMinFontSize`、`expectCoverWorks`（遮盖后就医提示四角没有朱色露出）；`expectGlass` 开与关。`frames.ts` 加 03a（开场）、03b（流式完成后滚到底）、03c（就医提示）、03d（点开场卡片的“继续遵守”）、03e（展开待处理条）、03f（滚到两个用户气泡分别在页头与底座下面），运行 `pnpm visual` 比较并修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add chat with streamed answers, opening card, review strip and continue sheet" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 7: 拍照识别与饮食记录

**Files:**
- Create: `src/api/upload.ts`、`src/api/hooks/photos.ts`、`src/api/hooks/nutrition.ts`
- Modify（替换占位）: `src/features/photos/PhotoNewPage.tsx`、`src/features/photos/PhotoResultPage.tsx`、`src/features/meals/RecordsPage.tsx`、`src/features/meals/MealNewPage.tsx`
- Create: `src/features/photos/compress.ts`、`RecognitionProgress.tsx`、`RecognitionFailure.tsx`、`ItemRow.tsx`、`ItemEditSheet.tsx`、`MealEvaluation.tsx`、`itemsUpdate.ts`、`src/features/meals/DiaryView.tsx`、`Ledger.tsx`、`NutrientTable.tsx`、`MealList.tsx`、`nutrientRows.ts`
- Create: `src/features/fitness/TrainingView.tsx`（占位，只渲染 `PagePlaceholder`，任务 9 替换）
- Create: `src/test/msw/handlers/photos.ts`、`nutrition.ts`，`src/test/fixtures/photos.ts`、`nutrition.ts`
- Test: `compress.test.ts`、`upload.test.ts`、`itemsUpdate.test.ts`、`PhotoNewPage.test.tsx`、`PhotoResultPage.test.tsx`、`nutrientRows.test.ts`、`DiaryView.test.tsx`、`MealNewPage.test.tsx`、`e2e/pages/photos.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 04a、04b、04c、05）

**Interfaces:**
- Consumes: 任务 3 的 `ConfidenceCells`、`VerdictMark`、`StatusMark`、`LedgerTicks`、`CountUp`、`Dock`、`Sheet`、`ConfirmSheet`、状态组件、`Sensitive`、`RefTag`；任务 4 的 `labels.ts`（`MEAL_LABELS`、`REVIEW_REASON_LABELS`、`CONCLUSION_LABELS`）、`contract.ts`（`SOURCE_NAMES`、`PHOTO_MEAL_NOTE`）；任务 6 的 `takePendingPhoto`。
- Produces:
  - `compress.ts`：`targetSize(width, height, maxEdge = 2048): { width; height }`（长边超过时等比缩小）；`compressImage(file: File): Promise<Blob>`（`createImageBitmap` 加 canvas 转 JPEG 质量 0.85；解码失败时原样返回文件，交给后端判断格式）。
  - `upload.ts`：`uploadRecognition(file: Blob, keepImage: boolean, onProgress: (sent: number, total: number) => void, signal?: AbortSignal): Promise<RecognitionOut>`：用 XMLHttpRequest 发 multipart（字段 `file` 与 `keep_image`）到 POST `/api/photos/recognitions`，带令牌，错误按 `api` 的规则转成 ApiError（含 401 处理），取消时抛 `AbortError`。
  - `api/hooks/photos.ts`：`useRecognitions()`（GET `/api/photos/recognitions`）、`useRecognition(id)`（GET `/api/photos/recognitions/{id}`）、`useUpdateRecognitionItems(id)`（PUT `/api/photos/recognitions/{id}/items` `{ items }`）、`useConfirmRecognition(id)`（POST `/confirm` `{ eaten_on, meal_type }`）、`useDiscardRecognition(id)`（POST `/discard`）、`useRecognitionImage(id, enabled)`（GET `/image` 取 blob 生成 object URL，卸载时释放；只在 `image_kept` 为真时启用）。
  - `itemsUpdate.ts`：`toItemsUpdate(items: PhotoItemOut[], change: { kind: 'edit'; id: string; name?: string; grams?: number; portion_text?: string; food_id?: string } | { kind: 'delete'; id: string }): PhotoItemIn[]`：没改的项只发 `{ id, name }`，原来有 `food_id` 时再带上 `food_id`（按 `app/photos/service.py::_revise` 的规则，这样原样保留）；改的那一项发 `{ id, name, ...改动的字段 }`；删除即不出现。
  - `api/hooks/nutrition.ts`：`useSummary(date)`（GET `/api/nutrition/summary?date=`）、`useMeals(date)`（GET `/api/nutrition/meals?date=`）、`useFoodSearch(q)`（GET `/api/nutrition/foods/search?q=`，q 为空不请求）、`useFood(id)`（GET `/api/nutrition/foods/{id}`）、`useCreateMeal()`（POST `/api/nutrition/meals`，成功后刷新当天的 summary 与 meals）。
  - 拍照页 `/photos/new`（04a、04c）：进入时若有 `takePendingPhoto()` 就直接开始；否则两个大按钮“拍照”（带 `capture="environment"`）与“从相册选”、勾选“保留照片（加密保存，可随时删除）”（默认不勾）与“未处理的草稿”列表（`useRecognitions` 里 status 为 draft 的项，点进 `/photos/:id`）；识别中 `RecognitionProgress`：上方照片占位写“你选的照片（不保留，识别后丢弃）”或“（加密保留）”，三步（上传完成“压缩后 1.2 MB”、正在认菜和份量、按营养库计算热量与营养），上传进度来自 XHR，响应到达前第二步转动；说明“可以离开这一页，识别完成后可在拍照页的‘未处理的草稿’里继续。”；操作坞“取消识别”。成功后 `replace` 到 `/photos/:id`。失败 `RecognitionFailure`：`photo_not_food` 标题 `photoNotFood`、`photo_unclear` 标题 `photoUnclear`，其余标题 `photoFailed`；正文原样显示后端说明，下一行“错误码 X。这次没有产生识别记录。”；动作：重拍、从相册换一张、手动记一餐（`/records/meals/new`）；错误码以 `llm_` 开头或为 `photo_recognition_failed` 时加“重试识别”（用内存里的同一张图）与“去设置”（`/settings/models`）；下方“拍照小提示”三条（光线、一餐一张、格式与 8 MB）。
  - 识别结果页 `/photos/:recId`（04b）：页头“识别结果”加返回与遮盖按钮；缩略图（`image_kept` 时显示图片，否则“图片 未保留”）与“草稿”、识别时间、`model_id`；有任何项带 `review_reasons` 时显示赭色提示条“有 N 项建议核对”；识别项面板（`Sensitive`）：每项菜名、热量（`nutrients.energy_kcal`，待确认写“待确认”）、份量说法与克数（`review_reasons` 含 `estimated_grams` 时写“（估算）”）、`ConfidenceCells`、“营养库：food_name”、评价里对应项的 `VerdictMark`；带 `review_reasons` 的项左侧赭色竖线，原因按 `REVIEW_REASON_LABELS` 逐条写出，动作“修改”（`ItemEditSheet`：菜名、份量说法、克数）与“删除这一项”；`needs_confirmation` 的项内嵌候选单选（React Aria `RadioGroup`，选中即 PUT 带 `food_id`）、“改个名字”“删除这一项”；合计四格（千卡、蛋白质、脂肪、钠，`totals`），下面原样显示 `disclaimer`。整餐评价面板（只在 `evaluation` 不为 null 时，`Sensitive`）：标题“整餐评价”加 `RefTag`，结论大字（`CONCLUSION_LABELS`），每项原因一行（`VerdictMark` 菜名、`SOURCE_NAMES` 来源、`message` 原文），`unchecked_notice` 放虚线框，`evaluation.disclaimer` 原文。吃的时间面板：日期（默认 `eaten_on` 或今天）与餐次（默认 `defaultMealType`）。“放弃这次识别”文字按钮打开 `ConfirmSheet`（`discardRecognition`）。操作坞主按钮“确认入库”，还有待确认项时不可用并写“确认入库（还有 N 项待确认）”；422 `photo_items_need_confirmation` 或 `photo_grams_out_of_range` 时轻提示后端说明并把焦点移到第一个需要处理的项；成功后跳 `/records?tab=diet&date=<eaten_on>`。已确认或已放弃的记录只读显示状态。
  - 记录页 `/records`（05）：`PageHeader variant="big"`（“记录”，`onRefresh` 刷新当天的汇总与记录），按 `recordSegments` 显示分段“饮食 / 训练”（只有一个时不显示分段）；`?tab=training` 时渲染 `TrainingView`。饮食 `DiaryView({ date })`：日期条（前一天、后一天，今天之后不可用）；`summary.needs.status === 'insufficient_profile'` 时能量账本的位置换成 `InsufficientState`（`needsProfile`，正文是 `needs.notes` 原文，动作“去补充档案”到 `/me/profile`）；`Ledger`：大数 `total.energy_kcal`（`CountUp`）/ `needs.energy_kcal` 千卡，“还可摄入” `remaining.energy_kcal`，`LedgerTicks`（段按 breakfast、lunch、dinner、snack 的顺序只取有记录的餐，颜色按出现顺序 1、2、3、4），图例四格（没记的餐写“未记”），`RefTag` 加 `needs.notes` 原文；`NutrientTable`（`nutrientRows(summary)` 生成）：蛋白质、脂肪、碳水化合物、膳食纤维、钠；已摄入、需要（区间写“低–高”）、还差（只有 `remaining` 里有的三项，其余“—”），4 像素进度条，钠一行写“上限”，`remaining.sodium_mg <= 0` 时整行赭色；`incomplete_fields` 非空时写“部分食物缺少 X 的数据，合计可能偏低”；`summary.disclaimer` 原文；`MealList`：按餐次分组，餐名、该餐第一条的时间（`formatTime(created_at)`）、该餐千卡（`summary.meals[type].energy_kcal`），每项“食物名 克数 克”与千卡，`note === PHOTO_MEAL_NOTE` 时整组下加“来自拍照识别”胶囊；没记的餐一行，右侧拍照图标（`/photos/new`）与“手动记一餐”。三块面板在一个 `Sensitive` 里。面板之后是背景场上的 `.on-field` 文字按钮“附近吃什么”（`/restaurants`，规格要求记录页也有附近餐厅入口）。当天完全没有记录时 `EmptyState`（`emptyDiary`，正文“{日期} 还没有记录。拍一张饭菜，或者手动记一餐。补记的记录会算进那一天。”，动作拍照记录与手动记一餐）。
  - 手动记一餐 `/records/meals/new`：搜索框（`useFoodSearch`，原样显示 `message`），结果是账目行；选中后读 `useFood` 的 `portions`，可按“克数”或“份量（单位 + 份数）”填写；日期（默认查询参数或今天）与餐次（默认查询参数或 `defaultMealType`）；操作坞“保存”（POST `{ eaten_on, meal_type, food_id, grams }` 或 `{ ..., portion: { unit, count } }`），成功后回到 `/records?tab=diet&date=` 并轻提示“已记下”。

- [ ] **Step 1: 写失败测试**
  - `compress.test.ts`：长边 4032 缩到 2048、竖图、小图不变。
  - `upload.test.ts`（用假的 XMLHttpRequest）：`it('sends file and keep_image as multipart with the token')`；`it('reports upload progress')`；`it('maps a 422 error body to an api error')`；`it('rejects with an abort error when cancelled')`。
  - `itemsUpdate.test.ts`：`it('sends untouched items as id and name only')`；`it('keeps food_id for items that have one')`；`it('sends the edited fields for the changed item')`；`it('drops a deleted item')`。
  - `PhotoNewPage.test.tsx`：`it('starts at once with a handed over photo')`；`it('shows three progress steps while recognising')`；`it('goes to the result page on success')`；`it('shows the not food state with the backend message and code')`（验收 7）；`it('offers retry and settings for a model failure')`；`it('lists unfinished drafts')`；`it('cancels the upload')`。
  - `PhotoResultPage.test.tsx`：`it('lists items with confidence, grams and review reasons')`；`it('picks a candidate by sending its food_id')`；`it('renames and deletes items through the full items list')`；`it('keeps confirm disabled while items need confirmation and counts them')`；`it('routes back to editing on photo_items_need_confirmation')`；`it('confirms with date and meal and opens that day')`；`it('shows the meal evaluation with a reference tag only for drafts')`（验收 8）；`it('shows the unchecked notice and both disclaimers verbatim')`；`it('loads the image only when it was kept')`（MSW 的 `/image` 处理器在 image_kept 为假时被调用就让测试失败）；`it('wraps names, numbers and evaluation in sensitive regions')`。
  - `nutrientRows.test.ts`：区间、只有三项有“还差”、钠为“上限”、`remaining.sodium_mg <= 0` 时 warn。
  - `DiaryView.test.tsx`：`it('offers the nearby restaurants entry')`；`it('shows the ledger with need and remaining from the summary')`；`it('shows needs notes beside a reference tag')`（验收 8）；`it('shows the insufficient profile state with the backend notes')`；`it('shows the empty day state with actions')`；`it('marks meals that came from a photo')`；`it('disables the next day after today')`；`it('shows a loading skeleton then a retryable error')`（验收 7）。
  - `MealNewPage.test.tsx`：`it('searches and shows the backend message for partial matches')`；`it('saves by grams')`；`it('saves by portion')`；`it('returns to the diary of that day')`。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/api/upload.test.ts src/features/photos src/features/meals` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build:check`。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/photos.spec.ts`（用 `seedModelService` 配好看图模型，`setInputFiles` 上传 `e2e/.fixtures/meal.jpg` 与 `white.jpg`）：两种宽度下识别结果页操作坞左右 8、下沿 18、主按钮 48；把握五格每格 6×8；候选行高 44；记录页能量刻度每格对应 25 千卡、需要线在面板内；营养表进度条 4 像素圆头；`expectTouchTargets`、`expectMinFontSize`、`expectNoHorizontalScroll`、`expectCoverWorks`（结果页与记录页）；减弱动效下能量刻度直接显示、计数直接是终值。`frames.ts` 加 04a（用 `page.route` 把识别请求挂起以停在识别中）、04b（模拟看图结果；另用 PUT 加一个营养库里没有的菜名以出现待确认项）、04c（white.jpg）、05（当天先确认一次识别再手动记两项），运行 `pnpm visual` 比较并修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add photo recognition flow and diet diary" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 8: 医嘱（待核对、生效中、历史与审计、录入、确认生效与确认解除）

**Files:**
- Modify: `src/api/hooks/medical.ts`（补全）
- Modify（替换占位）: `src/features/health/HealthPage.tsx`（经期与医嘱的分段框架，经期内容任务 9 填）、`src/features/medical/MedicalNewPage.tsx`
- Create: `src/features/cycle/CycleView.tsx`（占位，只渲染 `PagePlaceholder`，任务 9 替换）
- Create: `src/features/medical/MedicalView.tsx`、`PendingTab.tsx`、`ActiveTab.tsx`、`HistoryTab.tsx`、`OrderSource.tsx`、`PendingItem.tsx`、`ActiveItem.tsx`、`ProposalBlock.tsx`、`ConfirmEffectSheet.tsx`、`ResolveSheet.tsx`、`VoidSheet.tsx`、`ItemEditSheet.tsx`、`ManualItemSheet.tsx`、`EvidenceViewer.tsx`、`itemActions.ts`、`auditLine.ts`
- Create: `src/test/fixtures/medical.ts`（补全）、`src/test/msw/handlers/medical.ts`（补全）
- Test: `itemActions.test.ts`、`auditLine.test.ts`、`PendingTab.test.tsx`、`ActiveTab.test.tsx`、`HistoryTab.test.tsx`、`ConfirmEffectSheet.test.tsx`、`ResolveSheet.test.tsx`、`MedicalNewPage.test.tsx`、`HealthPage.test.tsx`、`e2e/pages/medical.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 07a 至 07f）

**Interfaces:**
- Consumes: 任务 6 的 `ContinueSheet`、`useItemContext`、`dueReason.ts`、`proposer.ts`、`useContinueItem`、`useCancelProposal`；任务 3 的 `ConfirmSheet`、`SegmentedTabs`、`TextTabs`、`WillList`、`Sensitive`、`RefTag`；任务 4 的 `labels.ts`、`contract.ts`。
- Produces:
  - `api/hooks/medical.ts`（补全）：`useOrders()`（GET `/api/medical/orders`）、`useCreateOrder()`（POST `/api/medical/orders` `{ text, order_date }`）、`useUploadEvidence(orderId)`（POST `/api/medical/orders/{id}/evidence`，multipart 字段 `file`，前端先按 10 MB 与 JPEG、PNG、WebP、PDF 提示，最终以后端结果为准）、`useEvidenceBlob(evidenceId)`（GET `/api/medical/evidence/{id}` 取 blob）、`useAddManualItem(orderId)`（POST `/api/medical/orders/{id}/items` `ManualItemCreate`）、`useUpdateItem()`（PATCH `/api/medical/items/{id}`）、`useConfirmItem()`（POST `/api/medical/items/{id}/confirm`，不带请求体）、`useVoidItem()`（POST `/api/medical/items/{id}/void` `{ reason }` 或不带）、`useResolveItem()`（POST `/api/medical/items/{id}/resolve`，不带请求体）、`useMedicalEvents(limit = 50)`（GET `/api/medical/events?limit=`）、`useConstraints(category?)`（GET `/api/medical/constraints?category=`）。全部修改成功后刷新 reviews、medicalItems、orders、constraints、medicalEvents 与相关条目的事件。
  - `itemActions.ts`：`itemActionsFor(item: MedicalItemOut): ItemAction[]`，按 DESIGN.md 第四节的动作表：pending_confirmation → 作废、修改、确认生效；pending_review → 继续遵守、确认解除；active 且 `resolution_proposed_at` 不为 null → 不解除、确认解除（放在解除建议区里）；active 无建议 → 修改、确认解除；resolved 与 voided → 无。`resolveSecondaryFor(item): { label: '继续遵守' | '不解除，撤销这条建议' | '取消'; action: 'open-continue' | 'cancel-proposal' | 'close' }`（解除面板的次按钮）。界面上“删除”一律写作“作废”。
  - `auditLine.ts`：`auditLine(event: MedicalEventOut): { time: string; action: string; content: string; transition: string; source: string }`：时间 `formatStamp(occurred_at)`；动作 `EVENT_ACTION_LABELS`（created 按 source 为 extractor 写“提取为待核对”、为 user 写“手动录入”）；内容是 `item_content` 原文；状态变化“A 到 B”（`ITEM_STATUS_LABELS`），`from_status` 等于 `to_status` 时写“状态不变”，`from_status` 为 null 时写“新建为 B”；来源 `EVENT_SOURCE_LABELS`，`detail.reason` 存在时在括号里接上原文，`detail.fields` 存在时写“修改了 N 个字段”。
  - `HealthPage`：`PageHeader variant="big"`（“健康”，`onRefresh` 刷新经期与医嘱的全部查询）；`healthSegments(caps)` 两个都有时显示分段“经期 / 医嘱”（医嘱段的徽标是 `reviews.length`），只有医嘱时不显示分段、直接是医嘱的三个子标签，只有经期时直接是经期内容；`/health/cycle` 与 `/health/medical` 决定选中段。
  - `MedicalView`：子标签 `TextTabs`（“待核对 N”“生效中 N”“历史与审计”，`?tab=` 同步），内容全部在 `Sensitive` 里；背景场上的“录入医嘱”是 `.on-field` 的钴蓝文字按钮。
  - 待核对（07b）：说明“提取出来的条目要逐条核对，确认前不参与任何建议。”；按医嘱分组：`OrderSource`（证据缩略或“原文”、录入日期与“提取出 N 条”，“查看”打开 `EvidenceViewer`；`order.notes` 与 `ignored` 原文折叠在“未提取的句子”里；“手动补充一条”打开 `ManualItemSheet`）；`PendingItem`：类别、“待核对”、有 `end_date` 时赭色“{end_date} 之后仍未确认，会自动作废”、原文（`source_excerpt`，浅灰圆角框）、字段表（提取内容 `content`、涉及 `subjects` 用顿号连接、生效日期、预计结束、复查日期、提取把握 `CONFIDENCE_LABELS`）；为空的日期字段用赭色写清确认后的后果（这是对“值为空”的说明，不是规则判断）：`review_date` 为 null 时“没有写明。确认后不设复查日期，可先补上”，`end_date` 为 null 时“没有写明。确认后视为长期有效，可先补上”；`missing_fields`（后端只会给出 `end_date` 与 `subjects`）含 `subjects` 时写“原文没有写明涉及的食物或行为，确认前需要补上”；`notes` 原文作说明；动作“作废”（`VoidSheet`，可填原因）、“修改”（`ItemEditSheet`：类别、内容、涉及、生效、预计结束、复查日期，PATCH 只发改动的字段）、“确认生效”（`ConfirmEffectSheet`）。
  - `ConfirmEffectSheet({ item, order })`（07c）：引文框（类别、内容、“来源：{证据文件名或‘原文’}，提取把握 X”）；“确认后会发生：”与四条后果：“状态从‘待核对’变为‘生效中’。”、“之后的对话、拍照评价和附近餐厅推荐都按它约束。”、有 `end_date` 时“预计结束 某日。结束前一天起进入待复核，那天打开应用时会提醒你。”否则“没有预计结束日期，视为长期有效。”、“记一条审计：时间、由你本人确认、来源与修改过的字段。”；主按钮“确认生效”、次按钮“返回修改”（打开 `ItemEditSheet`）；底部“医嘱只能在这里确认或解除，对话里无法完成。”；422 `subjects_required` 等错误原样显示。
  - `ResolveSheet({ item })`（07d）：引文框（类别、内容、“来源：{order_date} {证据文件名或‘原文’}”）；四条后果，最后一条朱色：“这条医嘱从‘{当前状态}’变为‘已解除’。”、“之后的训练与饮食建议不再按它约束。”、“记一条审计：时间、由你本人确认{，依据是 某日 的解除建议}。”、“解除不能撤销。以后需要时，请重新录入。”；必勾“我知道解除后不能撤销，需要重新录入才能恢复这条约束”；朱色“确认解除”；次按钮按 `resolveSecondaryFor`；结果用 `aria-live="assertive"` 播报“已解除：{内容}。审计已记录。”，随后关闭面板，条目出现在“历史与审计”。
  - 生效中（07a）：一块瓷胎面板里逐条 `ActiveItem`：类别、状态（待复核写赭色“待复核，{shortDue}”，生效中写“生效中”）、内容（17 号黑体 500，左侧圆头竖线）、日期行（生效、复查或预计结束）、待复核时写 `PENDING_REVIEW_NOTE` 原文；带建议的用 `ProposalBlock`：“{助手或你}提出了一条解除建议”加 `RefTag`、“依据是你在 某日 的对话里说：”或“理由：”接 `resolution_reason` 原文引用、“建议不会改变约束，只有你在这里确认后才会解除。”、按钮“不解除”“确认解除”。
  - 历史与审计（07e）：“已结束 N 条”（resolved 与 voided，颜色退一级、竖线变浅，状态写“已解除 日期”或“已作废 日期”（`closed_at`），下面一行写最后一个关闭事件的来源与原因）；“审计记录 最近 N 条”用 `useMedicalEvents(50)` 与 `auditLine`；系统事件的时间就是事件时间，不写成零点。
  - 录入医嘱 `/health/medical/new`（07f）：返回与遮盖按钮；说明“照你拿到的原文粘贴或拍照，不用改写。提取出的条目需要你逐条核对后才会生效。”；原文多行输入（计数“N / 5000”）、开具日期（默认今天、不晚于今天）、证据（可选，拍照与相册两个入口、列表可移除、显示大小与“加密保存”）；说明“提取后可以逐条修改，也可以在待核对里手动补充一条。”；操作坞“提取条目”：先 POST 医嘱，再逐个上传证据，全部完成后跳 `/health/medical?tab=pending`；任何一步失败原样显示错误，已建好的医嘱不重复提交。

- [ ] **Step 1: 写失败测试**
  - `itemActions.test.ts`：五种状态各自的动作；`resolveSecondaryFor` 的三种结果；动作文字里没有“删除”。
  - `auditLine.test.ts`：提取、手动录入、确认、系统进入待复核（带原因）、提出与撤销建议（状态不变）、作废带原因、修改字段数。
  - `PendingTab.test.tsx`：`it('groups pending items under their order source')`；`it('warns about auto voiding after the end date')`；`it('spells out missing fields and their consequence')`；`it('voids with an optional reason')`；`it('edits only the changed fields')`；`it('adds a manual item to an order')`。
  - `ConfirmEffectSheet.test.tsx`：`it('lists what will happen before confirming')`；`it('confirms only through the explicit button')`（打开面板不发请求，点“确认生效”才 POST `/confirm`，验收 3）；`it('returns to editing')`；`it('shows backend errors verbatim')`。
  - `ResolveSheet.test.tsx`：`it('requires the acknowledgement before resolving')`（验收 3）；`it('switches the secondary button by item state')`（待复核打开继续遵守面板、带建议调用 cancel-proposal、无建议只关闭）；`it('announces the result and moves the item to history')`。
  - `ActiveTab.test.tsx`：`it('shows due items with the backend reason and the pending review note')`；`it('shows who proposed a resolution with a reference tag')`（验收 8）；`it('keeps a proposal without resolving it')`；`it('opens the continue sheet for a due item')`；`it('never truncates contents with numbers')`。
  - `HistoryTab.test.tsx`：`it('lists closed items dimmed with their closing reason')`；`it('lists audit events across items from the events api')`。
  - `MedicalNewPage.test.tsx`：`it('creates the order then uploads each evidence file')`；`it('goes to the pending tab after extraction')`；`it('does not resubmit the order when an upload fails')`；`it('counts characters up to 5000')`。
  - `HealthPage.test.tsx`：`it('shows cycle and medical segments for a female user')`；`it('shows only medical tabs without the cycle module')`（男性用户页面上没有“经期”，验收 2）；`it('badges the medical segment with the review count')`。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/features/medical src/features/health` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/medical.spec.ts`（`seedPendingOrder` 用 `docs` 样例那段头孢的原文，`seedActiveItem`、`seedReviewDueItem`、`seedProposal` 准备三种生效中条目）：两种宽度下子标签每个点按区不小于 44、选中项下有 18×3 钴蓝胶囊；面板打开时只有面板一层模糊（导航的计算 `backdrop-filter` 为 none）、遮罩不模糊；解除面板勾选框 22×22、整行 44；`expectTouchTargets`、`expectMinFontSize`、`expectCoverWorks`（三个标签与录入页）；面板打开时 Tab 焦点不离开面板，关闭后回到触发按钮。`frames.ts` 加 07a、07b、07c、07d、07e、07f，运行 `pnpm visual` 比较并修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add medical pages with confirm, continue and resolve sheets" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 9: 经期与训练

**Files:**
- Create: `src/api/hooks/cycle.ts`、`src/api/hooks/fitness.ts`
- Modify（替换占位）: `src/features/cycle/CycleView.tsx`（任务 8 的 `HealthPage` 已在经期段渲染它）
- Create: `src/features/cycle/CycleCalendar.tsx`、`calendarCells.ts`、`cyclePanel.ts`、`PeriodSheet.tsx`、`DayLogSheet.tsx`
- Modify（替换占位）: `src/features/fitness/TrainingView.tsx`（任务 7 的 `RecordsPage` 已在训练段渲染它）、`src/features/fitness/WorkoutNewPage.tsx`
- Create: `src/features/fitness/WeekPanel.tsx`、`weekBars.ts`、`TrendRow.tsx`、`WorkoutRows.tsx`
- Create: `src/test/msw/handlers/cycle.ts`、`fitness.ts`，`src/test/fixtures/cycle.ts`、`fitness.ts`
- Test: `calendarCells.test.ts`、`cyclePanel.test.ts`、`CycleView.test.tsx`、`DayLogSheet.test.tsx`、`weekBars.test.ts`、`TrainingView.test.tsx`、`WorkoutNewPage.test.tsx`、`e2e/pages/cycle-fitness.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 06、08）

**Interfaces:**
- Consumes: 任务 3 的 `CycleTicks`、`Sheet`、`RadioSegment`、`DateField`、`TextField`、`RefTag`、`InsufficientState`、`Sensitive`；任务 4 的 `labels.ts`、`dates.ts`；任务 8 的 `useConstraints`。
- Produces:
  - `api/hooks/cycle.ts`：`usePeriods()`（GET `/api/cycle/periods`）、`useCreatePeriod()`（POST `/api/cycle/periods` `{ start_date }`）、`useUpdatePeriod()`（PATCH `/api/cycle/periods/{id}` `{ end_date }`）、`useDayLogs(start, end)`（GET `/api/cycle/day-logs?start=&end=`）、`usePutDayLog()`（PUT `/api/cycle/day-logs/{date}` `DayLogIn`）、`usePrediction()`（GET `/api/cycle/prediction`）、`usePhase()`（GET `/api/cycle/phase`）、`useTips()`（GET `/api/cycle/tips`）、`useCycleStats()`（GET `/api/cycle/stats`）；修改后刷新全部经期查询。
  - `cyclePanel.ts`：`cycleTicksModel(periods, prediction, phase): { length; periodDays; predicted; today } | null`（只做显示换算：周期起点是最近一次经期开始日，长度到预测范围最晚一天，经期天数取最近一次的实际天数（未结束时到今天），预测范围换成第几天）；`predictedPeriodDays(prediction, stats): string[]`（从 `next_period_start` 起取 `round(stats.avg_period_length)` 天，作为月历的“预计经期”）。
  - `calendarCells.ts`：`calendarCells(month: string, periods, predictedDays, predictedRange, dayLogs, today): Cell[]`，`Cell = { date: string; inMonth: boolean; recorded: boolean; predicted: boolean; inWindow: boolean; logged: boolean; today: boolean }`，周一开头。
  - `CycleView`（06）：`Sensitive` 包住除两个记录按钮外的全部内容；阶段大标题（`PHASE_TITLE_KEYS`）加 `RefTag`、“本周期第 N 天”与 `tips` 第一条的标题与内容原文；周期刻度面板（`CycleTicks`，完整 `aria-label`）与预测：`next_period_start` 大字（“10月28日”）、“预计下次开始。把握范围 A 至 B。”加 `RefTag`、“基于最近 N 个周期，周期长度在 X 到 Y 天之间。”（`stats.recent_cycle_lengths.length`、`shortest_cycle`、`longest_cycle`）、`prediction.notes` 与 `disclaimer` 原文；`prediction.status !== 'ok'` 时这一块换成 `InsufficientState`（`cycleInsufficient`，正文是 `prediction.notes` 原文，进度文字“已记录 N 个完整周期”（`stats.cycle_count`），动作“记录经期开始”）；月历 `CycleCalendar`：React Aria `Calendar`（`firstDayOfWeek="mon"`，`zh-CN`，只在本路由加载），格高 44、格内 36 圆角 12：已记录海军蓝实块、预计虚线框、预计开始范围下方虚线、有当天记录的右上小点、今天钴蓝内描边；图例四项；两个按钮：“记录经期开始”（最近一次经期还没结束时变为“记录经期结束”，打开 `PeriodSheet`）与“记录今天”（`DayLogSheet`）。全页只用海军蓝、灰与钴蓝，文案中性，不出现粉色、暖红与俗称。
  - `PeriodSheet({ mode: 'start' | 'end'; period? })`：只问日期（默认今天，不晚于今天）；开始 POST、结束 PATCH；错误原样显示。`DayLogSheet({ date? })`：日期（默认今天）、流量五档（`FLOW_LABELS`）、心情五档（`MOOD_LABELS`）、备注（500 字）；PUT 当天记录。
  - `api/hooks/fitness.ts`：`useWeekSummary()`（GET `/api/fitness/summary/week`）、`useWorkouts(start, end)`（GET `/api/fitness/workouts?start=&end=`）、`useCreateWorkout()`（POST `/api/fitness/workouts`）、`useExerciseSearch(q)`（GET `/api/fitness/exercises/search?q=`）、`useExerciseTrend(id)`（GET `/api/fitness/exercises/{id}/trend`）。
  - `weekBars.ts`：`weekBars(weekStart: string, workouts: WorkoutOut[], today: string): { date: string; label: string; minutes: number; isToday: boolean }[]`（每天的分钟数取 `duration_minutes`，为空时取各有氧项时长之和；标签“一”到“日”，今天写“今天”）。
  - `TrainingView`（08）：运动限制条（医嘱模块开放时 `useConstraints('exercise_limit')`，每条“运动限制生效中：{content}{，到 {end_date}}”，赭色浅底圆角，`Sensitive`）；`WeekPanel`：标题“本周训练”加“{周一} 至 {周日}”、三个数字（次数 `workout_count`、总时长（各柱之和）分钟、估算消耗 `energy_low_kcal`–`energy_high_kcal` 千卡加 `RefTag`；`energy_status` 为 `missing_body_weight` 时写 `note` 原文）、七根实心钴蓝柱（顶角 2，`role="img"` 加逐日 `aria-label`）；“搜索动作”胶囊框点按进入 `/records/workouts/new`；趋势行 `TrendRow`（最近一次训练里的第一个力量动作，阶梯线加圆点、最近一次实心钴蓝，“最大重量，近 N 次”“X 到 Y 千克”）；训练列表 `WorkoutRows`（近 30 天：动作名、时长、日期与星期、组次重量，`conflicts` 的 `message` 用赭色写在行内）；右上“记一次训练”加号按钮。
  - 记一次训练 `/records/workouts/new`（线框）：胶囊搜索框在顶（`useExerciseSearch`，原样显示 `message`），结果是账目行（动作名、`MUSCLE_LABELS`、`EQUIPMENT_LABELS`）；选中后：力量动作逐组填重量与次数（可加组），有氧填时长与距离；可再加动作；训练日期（默认今天，不晚于今天）与整次时长；操作坞“保存”（POST `WorkoutIn`），成功后回 `/records?tab=training` 并轻提示“已记下”；返回的 `conflicts` 原样轻提示。

- [ ] **Step 1: 写失败测试**
  - `calendarCells.test.ts`：2026 年 10 月从周一开始、前后补位、各状态标记、今天。
  - `cyclePanel.test.ts`：经期天数、预测范围换算、未结束的经期、没有预测时为 null。
  - `CycleView.test.tsx`：`it('shows the phase with a reference tag and the backend tip')`（验收 8）；`it('shows the prediction range and its disclaimer')`；`it('shows insufficient data with the backend notes and the cycle count')`（验收 7）；`it('keeps the two record buttons outside the sensitive region')`；`it('offers ending an open period')`；`it('uses no pink colour tokens')`（渲染结果的内联样式与类名里不出现 `--danger`、`pink`）。
  - `DayLogSheet.test.tsx`：五档流量与心情、PUT 的日期与请求体、错误原样显示。
  - `weekBars.test.ts`：没有时长时用有氧之和、今天标记、七天齐全。
  - `TrainingView.test.tsx`：`it('shows the exercise limit as sensitive medical content')`；`it('shows week figures with a reference tag on the energy estimate')`（验收 8）；`it('shows the missing body weight note verbatim')`；`it('shows conflicts on workout rows')`；`it('draws the trend of the latest strength exercise')`。
  - `WorkoutNewPage.test.tsx`：搜索、加组、保存请求体、保存后返回。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/features/cycle src/features/fitness` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build:check`（确认日历只进经期路由的块，对话路由预算不变）。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/cycle-fitness.spec.ts`（女性用户用 `POST /api/cycle/periods` 写四次经期；训练用 `POST /api/fitness/workouts` 写一周）：两种宽度下月历格高 44、格内方块 36、面板内边距 12（360 下每格约 44.6 宽）；训练柱顶角 2；`expectTouchTargets`、`expectMinFontSize`、`expectCoverWorks`（经期页遮盖后只剩两个按钮可点）；`expectForcedColorsSmoke` 下月历已记录格是 CanvasText 实块、今天是 Highlight 描边。`frames.ts` 加 06、08，运行 `pnpm visual` 比较并修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add cycle and fitness pages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 10: 附近餐厅与设置（模型服务四步、隐私与数据、免责声明）

**Files:**
- Create: `src/api/hooks/restaurants.ts`、`src/api/hooks/grants.ts`；Modify: `src/api/hooks/llm.ts`（补全）
- Modify（替换占位）: `src/features/restaurants/RestaurantsPage.tsx`、`src/features/settings/ModelsPage.tsx`、`ModelNewPage.tsx`、`PrivacyPage.tsx`、`DisclaimerViewPage.tsx`
- Create: `src/features/restaurants/LocationAsk.tsx`、`PlaceForm.tsx`、`NeedChips.tsx`、`ShopList.tsx`、`AvoidedTypes.tsx`、`useGeolocation.ts`；`src/features/settings/ProviderFlow.tsx`、`flowReducer.ts`、`StepCredentials.tsx`、`StepFetch.tsx`、`StepTest.tsx`、`StepAssign.tsx`、`ProviderRow.tsx`、`KeyMask.tsx`、`GlassPreference.tsx`、`SavedArea.tsx`、`GrantList.tsx`、`AuditList.tsx`
- Create: `src/test/msw/handlers/restaurants.ts`、`llm.ts`、`grants.ts`，`src/test/fixtures/restaurants.ts`、`llm.ts`、`grants.ts`
- Test: `RestaurantsPage.test.tsx`、`useGeolocation.test.ts`、`flowReducer.test.ts`、`ProviderFlow.test.tsx`、`ModelsPage.test.tsx`、`PrivacyPage.test.tsx`、`DisclaimerViewPage.test.tsx`、`e2e/pages/settings-restaurants.spec.ts`
- Modify: `e2e/visual/frames.ts`（加 09、10a、10b）

**Interfaces:**
- Consumes: 任务 3 的全部表单组件、`StatusMark`、`VerdictMark`、`ConfirmSheet`、`AuthNeededState`、`useGlassPreference`、`Sensitive`、`RefTag`；任务 4 的 `labels.ts`、`contract.ts`（`MAX_NEEDS`、`AGENT_CLIENT_NAME`、`SOURCE_NAMES`）、`format.ts`。
- Produces:
  - `api/hooks/restaurants.ts`：`useRestaurantSettings()`（GET `/api/restaurants/settings`）、`useSetConsent()`（PUT `/api/restaurants/settings/consent` `{ consent: 'granted' | 'denied' }`）、`useClearArea()`（DELETE `/api/restaurants/settings/area`）、`useNeeds()`（GET `/api/restaurants/needs`）、`useRestaurantSearch()`（POST `/api/restaurants/search`，`SearchIn`：`location { lng, lat, coord_type: 'gps' }` 或 `place` 加可选 `city` 或 `use_saved_area: true`，三选一；`needs`（最多 `MAX_NEEDS` 个键）、`radius` 2000、`remember_area`）。
  - `useGeolocation()`：`request(): Promise<{ lng: number; lat: number }>`（`navigator.geolocation.getCurrentPosition`，高精度、10 秒超时；拒绝或失败时 reject，调用方改用地点输入）。
  - 附近餐厅页（09）：页头“附近吃什么”加返回与遮盖按钮。`should_ask_location` 为真时先显示 `LocationAsk`（`AuthNeededState`，`locationAsk`，“只用来查找附近的餐厅，精确位置不会保存。不允许也没关系，可以输入地名或地标，以后不再询问。”，“允许定位”与“输入地点”两个整宽按钮）：允许 → PUT granted → 取浏览器定位 → 按坐标检索；输入地点 → PUT denied → 显示 `PlaceForm`，此后永远不再询问（只看后端的 `should_ask_location`）。已授权时进入页面自动取一次定位检索，浏览器拒绝或失败就显示地点输入并写“没能取得定位，输入地名或地标即可。”；已拒绝时写“没有开启定位，输入地名或地标即可，不会再请求定位。”。有已保存区域时多一个“用已保存的区域：{name}”选项。`PlaceForm`（`Sensitive`）：地名或地标、城市（可选）。`NeedChips`：先显示 `useNeeds` 的前四个，最后一个胶囊“全部 N 项”展开；多选，选满 `MAX_NEEDS` 个后其余不可选并写“最多选 3 项”；选中是钴蓝浅底加勾。“记住大致区域，下次不用再输入。可在设置里清除。”勾选行（`Sensitive`）。结果：`notice` 原文加 `RefTag`（每次结果都显示）；标题“附近的店”与“{半径} 内 N 家，按适合程度与距离”；`ShopList` 一块面板：店名、`VerdictMark`（suitable 适合、caution 注意、unchecked 未核对）、`type_name`、`fmtDistance(distance_m)`；按 `type_advice` 中同 `type_key` 的一项写“可点 …”“适量 …”“应避开 …”（顿号连接）；`type_key` 为 null 的店只写 `tip` 原文；右侧 56 的“导航”瓷扣是 `<a href={nav_url} target="_blank" rel="noopener noreferrer" aria-label="导航到{店名}">`。`AvoidedTypes`：标题“已避开的类型”加 `RefTag`，每类：类型名（朱色删除线）、被避开的店名、每条原因“{SOURCE_NAMES[source]} 代表菜‘{food_name}’：{message}”。最后 `disclaimer` 原文。错误：`restaurant_location_not_granted` 切到地点输入；其余 `restaurant_*` 用 `ErrorState` 原样显示并可重试。
  - `api/hooks/llm.ts`（补全）：`usePresets()`（GET `/api/llm/presets`）、`useProviders()`、`useCreateProvider()`（POST `/api/llm/providers` `{ name, kind, base_url, api_key }`）、`useUpdateProvider()`（PATCH `/api/llm/providers/{id}`）、`useDeleteProvider()`（DELETE）、`useFetchModels(id)`（POST `/api/llm/providers/{id}/fetch-models`）、`useProviderModels(id)`（GET `/api/llm/providers/{id}/models`）、`useAddModel(id)`（POST `/api/llm/providers/{id}/models` `{ model_id }`）、`useTestProvider(id)`（POST `/api/llm/providers/{id}/test` `{ model_id }`）、`useUpdateModelOverrides()`（PATCH `/api/llm/models/{pk}` `{ vision?, tools?, chat? }`，值 true 或 null）、`useAssignments()`、`useSetAssignment()`（PUT `/api/llm/assignments/{purpose}` `{ model_id: <模型主键> }`）。查询缓存里只存后端响应，密钥只存在表单组件的局部状态里。
  - `flowReducer.ts`：`FlowState = { providerId: string | null; steps: Record<1 | 2 | 3 | 4, { state: 'todo' | 'current' | 'ok' | 'bad'; message?: string; code?: string; field?: 'name' | 'base_url' | 'api_key' }> }`；`flowReducer(state, event)`；`stepForError(code: string): { step: 1 | 2 | 3; field?: ... }`：`llm_invalid_key` 与 `llm_key_required_for_new_url` 到第 1 步密钥字段，`llm_invalid_url` 到第 1 步地址字段，`llm_provider_exists` 到第 1 步名称字段，`llm_bad_url` 与 `llm_listing_unsupported_or_bad_url` 到第 2 步（动作“修改地址”回到第 1 步地址字段），获取时的其他错误到第 2 步（动作“重试”），测试时的错误到第 3 步（动作“重新测试”）。
  - `ProviderFlow`（10b、10a，`/settings/models/new`）：四步竖排（`StatusMark` 步骤号：完成为钴蓝圆点加勾，当前为钴蓝圆圈，失败为朱色圈并在标题右侧写短结论）。第 1 步“填写地址与密钥”：类型（`usePresets` 的预设，选中后填好类型、名称与地址；另有“自定义”可选 `PROVIDER_KIND_LABELS` 三种）、名称、服务地址、密钥（`PasswordField`，“保存后只显示掩码，原文无法再查看。”）；“保存并获取模型”：POST 创建 → 成功后立即清空密钥输入框并在步骤里显示地址与 `KeyMask`（锁图标加 `key_hint`）→ 自动进入第 2 步。失败时出错字段 2 像素朱色内描边，下方紧贴后端说明原文与“错误码 X”；第 1 步失败后的按钮是“重新保存并获取模型”（已创建时 PATCH 改动的字段，改了密钥才带 `api_key`）。第 2 步“获取模型”：POST fetch-models，成功写“{total} 个”与“其中 X 个能看图，Y 个能调用工具。”（按返回模型的 `capabilities` 计数）；后端说不支持列出模型时提供“手动添加模型编号”。第 3 步“测试连通”：选一个模型（默认第一个 `capabilities.chat` 不为 false 的）→ POST test → 成功写“用时 N 秒”（前端计时）与 `report.chat?.message ?? report.message` 原文；失败写 `report.message` 原文与 `report.chat?.code ?? report.listing.code`。第 4 步“选择用途模型”：日常对话与看图识别两个下拉（本服务的模型），每个下拉下方是能力胶囊（`CAPABILITY_LABELS`；`overrides` 中不为 null 的写“… 手动”并用虚线框），两个勾选“能看图（手动标注）”“能调用工具（手动标注）”对应 PATCH overrides（取消即发 null），返回的 `assignment_warnings` 原文显示；“保存用途”依次 PUT chat 与 vision（未选的不发），错误原样显示在对应下拉下；完成后回到 `/settings/models` 并轻提示“已保存”。
  - `ModelsPage`（10a 上半）：服务列表（名称、地址（不截断数值）、`KeyMask`、“测试连通”文字按钮，结果用 `VerdictMark`（ok 写“已连通”）与后端说明）；当前用途（`useAssignments`：日常对话、看图识别各写模型与服务名）；“添加模型服务”按钮；“其他设置”三行链接（隐私与数据、已保存的大致区域（右侧区域名）、免责声明）。
  - `PrivacyPage`（线框）：遮盖说明（“打开后医嘱、经期、档案等内容用斜纹盖住；应用切到后台再回来时自动遮盖。”）；`GlassPreference`：“减少透明”分段“跟随系统 / 开 / 关”（`useGlassPreference`），下方“会关掉磨砂玻璃，界面改用实色，更省电。”；`SavedArea`：已保存的大致区域名与保存时间，“清除”打开 `ConfirmSheet`（`clearArea`）→ DELETE；`GrantList`：`GET /api/agent-grants` 每个授权的名称、`ACCESS_LABELS`、`GRANT_STATUS_LABELS`、到期与最近使用时间，有效的可“吊销”（`ConfirmSheet`（`revokeGrant`）→ DELETE `/api/agent-grants/{id}`）；`AuditList`：筛选胶囊“全部”加最近 200 条（不筛选时取）里出现过的客户端名（`CLIENT_LABELS`，agent 写“应用内助手”），选中后 `GET /api/agent-grants/audit?limit=50&client_name=<名>`；每行时间、客户端、能力名、结果（`AUDIT_OUTCOME_LABELS`）、错误码、耗时毫秒。
  - `DisclaimerViewPage`（线框）：`GET /api/disclaimer` 正文按行显示、版本号；`GET /api/disclaimer/status` 的确认时间；只读。
  - `KeyMask({ hint: string })`：锁图标加掩码文字，`aria-label="密钥 {hint}"`。

- [ ] **Step 1: 写失败测试**
  - `RestaurantsPage.test.tsx`：`it('asks for location only when the backend says so')`；`it('records denial and never asks again')`（PUT denied 后再次进入页面不出现询问，验收 7 的需要授权状态）；`it('searches with gps coordinates after consent')`（请求体 `coord_type` 为 gps）；`it('falls back to the place form when the browser refuses')`；`it('searches by place and city')`；`it('limits needs to three')`；`it('shows the notice with a reference tag on every result')`（验收 8）；`it('shows dish advice from the type advice')`；`it('shows only the tip for unknown types')`；`it('lists avoided types with dish attributed reasons apart from the list')`；`it('links navigation to nav_url')`；`it('remembers the rough area when asked')`；`it('switches to the place form on restaurant_location_not_granted')`。
  - `useGeolocation.test.ts`：成功、拒绝、超时。
  - `flowReducer.test.ts`：每个错误码落到正确的步骤与字段；成功事件推进步骤。
  - `ProviderFlow.test.tsx`：`it('creates the provider and fetches models')`；`it('clears the key input and shows only the backend mask after saving')`（页面文字、各输入框的值、localStorage、sessionStorage、查询缓存里都找不到密钥原文，只有 `key_hint`，验收 9）；`it('marks the key field on llm_invalid_key and resaves with a patch')`；`it('sends the user back to the address on llm_bad_url')`；`it('tests a model and shows the backend message')`；`it('shows a timeout in step three with a retest action')`；`it('assigns chat and vision models')`；`it('marks capabilities manually and shows assignment warnings')`（验收 5 的界面部分）。
  - `ModelsPage.test.tsx`：服务列表只有掩码；测试连通结果；当前用途。
  - `PrivacyPage.test.tsx`：`it('switches the reduce transparency preference')`（根节点 `data-glass` 随之变化）；`it('clears the saved area after confirmation')`；`it('lists grants and revokes an active one')`；`it('filters the audit list by client name')`（请求带 `client_name=agent`，列表只剩这些行）。
  - `DisclaimerViewPage.test.tsx`：正文、版本与确认时间。
- [ ] **Step 2: 运行确认失败**：`pnpm exec vitest run src/features/restaurants src/features/settings` → FAIL。
- [ ] **Step 3: 实现**。
- [ ] **Step 4: 运行确认通过**：`pnpm lint`、`pnpm typecheck`、`pnpm test`。
- [ ] **Step 5: 版式与无障碍检查**：`e2e/pages/settings-restaurants.spec.ts`（餐厅页用 Playwright 的 `geolocation` 与 `permissions: ['geolocation']`；模拟高德已由 e2e_server 配好）：两种宽度下导航瓷扣 56×56、需求胶囊 36 高带 `data-hit44`、步骤号圈 28、密钥失败的输入框 2 像素朱色内描边；`expectTouchTargets`、`expectMinFontSize`、`expectNoHorizontalScroll`、`expectCoverWorks`（餐厅页只盖地点与“记住区域”）；隐私页把“减少透明”切到开后 `expectGlass(page, false)`，切回关后 `expectGlass(page, true)`。`frames.ts` 加 09（拒绝定位后手动地点检索）、10a（四步走到第 4 步）、10b（用 `bad_key` 走到第 1 步失败），运行 `pnpm visual` 比较并修到一致。
- [ ] **Step 6: 提交**

  ```
  git add frontend
  git commit -m "feat(frontend): add nearby restaurants and settings pages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

### Task 11: 端到端验收流程（iPhone 13 与 Pixel 7）

**Files:**
- Create: `frontend/e2e/acceptance/new-user.spec.ts`、`cycle-entry.spec.ts`、`medical-confirm.spec.ts`、`review-on-open.spec.ts`、`model-settings.spec.ts`、`states.spec.ts`、`reference-tags.spec.ts`、`key-mask.spec.ts`、`glass-a11y.spec.ts`
- Modify: `frontend/e2e/support/api.ts`（如需补充种子函数）

**Interfaces:**
- Consumes: 任务 2 的 `app.e2e_server`、`e2e/support/*`；任务 5 至 10 的全部页面。
- Produces: 每个用例都在 `iphone-13`（WebKit，390 宽）与 `pixel-7`（Chromium）两个项目里各跑一遍；每个文件开头 `test.beforeEach(({ page }) => blockExternal(page))`；截图只写 `test-results/`。编排：`pnpm e2e` → Playwright `webServer` 运行 `scripts/e2e-server.mjs`（`pnpm build:e2e` → `uv run python -m app.e2e_server --port 8765 ...`：迁移并清空测试库、启动模拟模型与模拟高德、写两张测试图片、在 8765 端口提供后端与 `dist-e2e`）→ 跑用例 → Playwright 结束子进程。前提：Docker 里的数据库已启动；同一时间不要跑后端 pytest。

- [ ] **Step 1: 写验收用例**（测试名用英文；每个用例的关键断言）
  - `new-user.spec.ts`（验收 1）：`test('a new user completes the whole flow through the ui only')`：在 `/login` 注册 → 免责页勾选并确认 → 建档三步（第 1 步拖动刻度尺并用方向键微调，第 2 步选活动与目标，第 3 步添加一个忌口标签后完成）→ 对话页出现“还没有可用的对话模型” → 点“去添加模型服务”按 `e2eInfo` 的地址与假密钥走完四步，对话选 `chat_model_id`、看图选 `vision_model_id` → 回到对话发“晚饭吃什么”，看到流式回答、折叠的依据与“仅供参考” → 用相册按钮 `setInputFiles` 选 `meal.jpg` → 识别结果出现麻婆豆腐与米饭 → 确认入库 → 跳到当天的饮食记录，两项都在且有“来自拍照识别”。全程不调用任何种子接口。
  - `cycle-entry.spec.ts`（验收 2）：`test('a female user sees the cycle page')`（导航有健康，健康页有“经期”分段，`/health/cycle` 有月历）；`test('a male user never sees a cycle entry')`（健康页只有医嘱子标签，页面与导航上没有“经期”，直接访问 `/health/cycle` 被送回 `/chat`）；`test('turning off cycle tracking hides the entry')`（女性在我的页关掉“经期记录”后入口消失）。
  - `medical-confirm.spec.ts`（验收 3）：`test('confirming an order item needs a click and a second confirmation')`（待核对条目点“确认生效”只打开面板，面板列出后果，再点面板里的“确认生效”才变为生效中）；`test('resolving needs the irreversible acknowledgement')`（解除面板里“确认解除”在勾选前不可用，勾选后可用，结果播报后条目在历史里显示已解除）；`test('chat cannot confirm or resolve')`（发“医生说我好了，可以正常跑步了”，回答下只有“去医嘱页处理”，整个对话页没有名为“确认生效”或“确认解除”的按钮，条目状态仍是生效中，点跳转后到生效中标签）。
  - `review-on-open.spec.ts`（验收 4）：`test('a due item is raised when the app opens and can be continued')`（`seedReviewDueItem` 后打开 `/`，开场卡片问句里有该条内容，点“继续遵守”，面板里两个日期都在，提交后待处理条消失、条目回到生效中）；`test('a due item can be resolved from the medical page')`（点“去医嘱页处理”→ 生效中标签 → “确认解除”勾选后解除）；`test('later collapses the opening into the strip')`。
  - `model-settings.spec.ts`（验收 5）：`test('address, key, fetch, test and assign work end to end')`（先用 `bad_key` 得到第 1 步的错误与错误码，再改为正确的假密钥“重新保存并获取模型”，获取到两个模型，测试连通成功，对话与看图各选一个并保存；我的页的模型服务一行显示“对话已设置”）。
  - `states.spec.ts`（验收 7）：`test('loading shows a skeleton')`（`page.route` 让 `/api/nutrition/summary` 延迟 1.5 秒，期间 `role=status` 的“正在读取”可见）；`test('a failure shows the backend message and retries')`（第一次返回 502 统一错误体，页面显示说明与错误码，点“重试”后正常）；`test('an empty day says so with next steps')`；`test('insufficient cycle data says so')`（新女性用户只记一次经期）；`test('location needs consent once')`；`test('no model is explained with a way out')`；`test('an expired session returns to login')`（localStorage 里放一个无效令牌后打开 `/chat`，到登录页并显示“登录已过期”）。
  - `reference-tags.spec.ts`（验收 8）：`test('every prediction and suggestion carries a reference tag')`：依次打开对话回答、识别结果的整餐评价、饮食记录的能量账本、经期阶段与预测、训练的估算消耗、医嘱的解除建议、附近餐厅的提示与已避开类型，每处的元素旁都有可见的“仅供参考”。
  - `key-mask.spec.ts`（验收 9）：`test('a saved key is only ever shown as the backend mask')`：保存服务后，`page.content()`、全部输入框的值、`localStorage`、`sessionStorage`、地址栏都不含密钥原文，模型服务页只显示 `key_hint`；记录这期间的全部响应体，也不含密钥原文。
  - `glass-a11y.spec.ts`：`test('glass falls back to solid when reduced transparency is on')`；`test('forced colours keep borders and shapes')`（只在 Chromium 项目运行，WebKit 项目 `test.skip`）；`test('touch targets and font sizes hold on the main pages')`（对话、记录、健康、我的、附近餐厅、模型服务各跑 `expectTouchTargets` 与 `expectMinFontSize`）；`test('cover hides sensitive content and comes back when the page was hidden')`（派发 `visibilitychange` 为 hidden 再回来，页面处于遮盖状态）；`test('reduced motion removes movement')`。
- [ ] **Step 2: 运行**：`pnpm e2e`（超时设 600000 毫秒）。凡是失败，先判断是用例写错还是界面有问题；界面问题回到对应任务的文件修正并补对应的 Vitest 测试，然后重跑直到全部通过。
- [ ] **Step 3: 回归**：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build:check`、`pnpm e2e:pages`、`pnpm e2e`；后端全量 `uv run pytest -q -W error`（与 Playwright 分开运行）。
- [ ] **Step 4: 提交**

  ```
  git add frontend/e2e
  git commit -m "test(frontend): add Playwright acceptance flows on iPhone 13 and Pixel 7" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```
  若 Step 2 修了界面，界面修改的文件一并加入这次提交，提交信息改为 `test(frontend): add Playwright acceptance flows and fix issues they found`。

---

### Task 12: 交付文档、依赖许可证、README 与验收记录

**Files:**
- Create: `docs/11-交付物/页面清单与信息结构说明.md`、`关键流程交互说明.md`、`状态与异常界面清单.md`、`手机端适配说明与测试设备清单.md`、`验收记录.md`
- Modify: `docs/01-交付物/依赖许可证.md`（新增“## 五、前端依赖（步骤 11）”，含“运行依赖”“开发依赖”“字体资源”“构建工具”四张表，并在“结论”末尾补一句前端依赖全部是 MIT、Apache-2.0 或 BSD，字体为 OFL-1.1）
- Modify: `README.md`（新增“## 22. 前端 H5”，含“### 安装”“### 开发”“### 打包与由后端提供”“### 局域网 HTTPS 真机测试”“### 端到端测试”；开头的完成情况加步骤 11）
- Modify: `docs/00-总览与串联.md`（步骤 11 一行的状态改为“待验收”）
- Create: `backend/tests/test_frontend_docs.py`

**Interfaces:**
- Consumes: 全部前序任务的实际代码与测试。
- Produces:
  - 页面清单与信息结构说明：按 `PATHS` 逐个路由写页面名称、入口、信息结构（从上到下的区块）、读写的接口、是否敏感区、能力清单条件；导航的四项与三项变体、守卫顺序。
  - 关键流程交互说明：建档、拍照识别、医嘱核对与解除（含继续遵守、不解除、解除面板的次按钮表）、经期记录、模型配置五个流程，每个写步骤、每步的界面反馈与失败时的出路。
  - 状态与异常界面清单：加载中、失败可重试、无数据、数据不足、需要授权（定位、没有模型、登录过期）五类，每类列出出现在哪些页面、标题、正文来自哪里、下一步动作；列出界面处理的全部错误码（照片模块全部 `photo_` 错误码、模型配置流程用到的 `llm_` 错误码、`agent_model_not_configured`、`agent_model_error`、`restaurant_` 错误码、`still_due`、`subjects_required`、`disclaimer_outdated`、`username_taken`、`invalid_credentials`、`invalid_token`、`not_authenticated`、`validation_error`、`network_error`、`http_error`）与各自的界面表现；就医提示与遮盖。
  - 手机端适配说明与测试设备清单：竖屏、安全区、软键盘、触控目标与字号、玻璃预算与四种降级、强制颜色、减弱动效、最低引擎（iOS Safari 16、Chromium 107）、首屏预算；设备表（自动化：iPhone 13 模拟（WebKit）、Pixel 7 模拟（Chromium）、视口 390 与 360；真机一：任一 iPhone，iOS 16 以上，Safari；真机二：中端安卓机，Chrome 或系统浏览器；可选：微信内置浏览器）；“真机核对清单”逐条：拍照入口调起相机、相册入口调起相册、拍照后识别成功、定位授权与拒绝后的地点输入、局域网 HTTPS 下定位可用、软键盘弹起时对话底座贴住键盘、遮盖与切后台自动遮盖、系统“降低透明度”与应用内“减少透明”的说明、低亮度下细线与骨架可见、对话页快速滚动 5 秒时 90% 的帧不超过 16.7 毫秒、导航跳转唤起高德。
  - 验收记录：开头的填写说明（自动化测试列的写法：后端写“文件名 加两个冒号 加测试名”；前端写“frontend 下的相对路径 加两个冒号 加测试标题”）；9 行表格，列为 序号、验收项、自动化测试、手动核对方法、结果、用户验收；“用户验收”列全部留空；第 6 条的“结果”写“已通过两种模拟设备的自动化验证；需用户真机核对（见《手机端适配说明与测试设备清单》的真机核对清单）”；其余各条的“结果”写“已通过自动化验证”；之后是“## 自动化验证记录”（日期、环境、Vitest 与 Playwright 的用例数按实际数出来、后端全量结果、首屏预算实测值）与“## 代为验收记录”（先写“待代验”，由验收会话填写）。
  - `backend/tests/test_frontend_docs.py`（参照 `tests/test_restaurant_docs.py` 的写法）：
    - `test_delivery_docs_exist_and_contain_no_code`：`docs/11-交付物/` 正好是这五份；不含三个反引号、不含反引号、不含“pnpm ”、“uv run”、“python -m”。
    - `test_acceptance_record_has_nine_rows_and_an_empty_user_column`：9 行、每行 6 列、前五列非空、第 6 列为空。
    - `test_criterion_6_waits_for_the_users_real_devices`：第 6 行的结果含“需用户真机核对”，手动核对方法含“真机”；其余行不含。
    - `test_acceptance_rows_reference_existing_tests`：后端引用匹配 `(test_\w+\.py)::(test_\w+)` 并在 `backend/tests` 里找得到定义；前端引用匹配 `(frontend/(?:src|e2e)/[\w./-]+?\.(?:test\.tsx?|spec\.ts))::([a-z0-9][a-z0-9 ,'_-]*[a-z0-9])`，文件存在且文件里出现 `'<标题>'`；第 1 至 5 行与第 7 至 9 行每行至少一个前端引用，全表至少 40 个引用。
    - `test_page_list_covers_every_route`：用正则取出 `frontend/src/app/paths.ts` 里全部以斜杠开头的路径字面量（`/dev/gallery` 除外），每个都出现在页面清单里。
    - `test_states_doc_lists_every_photo_error_code`：从 `backend/app/photos` 源码里取出全部 `photo_` 错误码，都在状态清单里；另检查“加载中”“失败”“无数据”“数据不足”“需要授权”“登录已过期”与上面列出的其余错误码。
    - `test_device_doc_lists_devices_engines_and_the_real_device_checklist`：含“iPhone 13 模拟”“Pixel 7 模拟”“390”“360”“iOS Safari 16”“Chromium 107”“真机核对清单”“拍照”“相册”“定位”“降低透明度”。
    - `test_license_doc_lists_every_frontend_dependency_with_its_locked_version`：读 `frontend/package.json` 的全部直接依赖，从 `frontend/pnpm-lock.yaml` 的 importers 段用正则取出各自的解析版本，在“五、前端依赖（步骤 11）”一节里每个依赖都有一行，含该版本与 MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause 之一；字体资源表含 Noto Serif SC、Source Serif 4 与 OFL-1.1。
    - `test_readme_and_overview_record_step_11`：README 含“## 22. 前端 H5”与五个小节标题、`pnpm dev:lan` 与 `pnpm e2e`；总览里步骤 11 一行为 `| 11 | 前端 H5 | 11-前端H5.md | 08 至 10 | 待验收 |`。

- [ ] **Step 1: 写失败测试** `backend/tests/test_frontend_docs.py`。
- [ ] **Step 2: 运行确认失败**：`uv run pytest tests/test_frontend_docs.py -q -W error` → FAIL（文档不存在）。
- [ ] **Step 3: 写文档**：全部按实际代码与实际测试名写；依赖许可证的版本取锁文件里的解析版本，许可证取 `node_modules/<名字>/package.json` 的 `license`；README 的命令写在代码块里（README 不是交付文档）。
- [ ] **Step 4: 运行确认通过**：`uv run pytest tests/test_frontend_docs.py -q -W error`，然后后端全量 `uv run pytest -q -W error`；前端 `pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build:check`。
- [ ] **Step 5: 提交**

  ```
  git add docs/11-交付物 docs/01-交付物/依赖许可证.md README.md docs/00-总览与串联.md backend/tests/test_frontend_docs.py
  git commit -m "docs(frontend): add step 11 delivery docs, license records and acceptance record" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

---

## 需要关注（实现时不改，验收时向用户说明）

1. 后端 `app/agent/openings.py` 的 `_review_due` 取 `medical.list_reviews` 的第一条，而这份列表也包含“生效中且只带解除建议”的条目，所以开场卡片可能由解除建议触发，与 DESIGN.md 第四节“开场卡片只会因到期触发”不一致。前端按“已定的取舍”处理（这种情况不给“继续遵守”）；是否在后端只取待复核条目，由用户决定。
2. 聊天在一轮回答完整生成后才开始推送，中间没有保活；开发代理的超时已放宽到 300 秒，但真机经过其他代理或网关时仍可能被提前断开，真机核对时留意。
3. 重试会在会话里多存一条相同的用户消息，界面只显示一次；若要彻底避免，需要后端提供“重试上一轮”的接口。
4. 字体子集的体积按设计稿的估算设了上限；若用户以后加了很多新标题，`titles.test.ts` 会提示超出 40 KB。
