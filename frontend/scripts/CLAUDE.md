# frontend/scripts 目录说明书

## 职责
- 构建、生成与端到端启动用的 Node 与 Python 小脚本，都由 package.json 的命令调用：
  - check-budget.mjs（pnpm build:check）：构建后沿入口与对话页（src/features/chat/ChatPage.tsx）的静态导入收集全部块，检查首屏预算：脚本 gzip 150 KB、样式 gzip 22 KB、预加载字体合计 45 KiB、脚本块最多 8 个；超出时列出各文件大小并以失败退出。
  - gen-api.mjs 与 gen-api-lib.mjs（pnpm api:gen）：调用后端导出接口快照 src/api/openapi.json，再用 openapi-typescript 生成 src/api/schema.d.ts（键排序，结果只取决于快照）；src/api/schema.test.ts 用同一个库检查生成结果是最新的。
  - subset-fonts.mjs（pnpm fonts）加 font_metrics.py、font_names.py：从 .font-cache 里的源字体生成两个自托管字体子集（GL Serif 宋体标题、GL Num 数字）、回退字体的度量规则、src/styles/fonts.css 与 fonts-manifest.json；子集按 SIL OFL 改名并保留版权与许可证记录。
  - e2e-server.mjs：Playwright 的 webServer，先构建 dist-e2e，再在后端目录启动 app.e2e_server；收到退出信号时连同子进程一起结束。

## 边界
- 被 package.json 与 playwright.config.ts 调用；不被 src 引用。Python 脚本经 uv 临时安装 fonttools 运行，不进后端的依赖。
- gen-api 会调用后端目录的 uv；后端接口变了才需要运行，结果两份文件一起提交。
- 字体子集只覆盖 src/lib/titles.json 的标题加 SERIF_EXTRA；宋体子集余量极小，本步骤不新增标题。

## 入口
- 在 frontend 下运行 pnpm build:check、pnpm api:gen、pnpm fonts；e2e-server.mjs 由 pnpm e2e 系列命令自动启动，不手动运行。
- 字体源文件的出处写在 subset-fonts.mjs 开头，放进 .font-cache 后再运行 pnpm fonts。

## 禁区
- 不放宽 check-budget.mjs 的上限来让构建通过；超了就减小对话路由的代码或改成按需加载。
- 不提交 .font-cache、dist、dist-e2e；字体许可证全文在 public/fonts/OFL.txt，生成的子集不能用保留字体名。
- subset-fonts.mjs 调用的 fonttools 已钉确切版本 4.66.1（src/test/deps.test.ts 守护）；换版本前先核对子集结果，并同步依赖许可证文档。
- 字体源文件由用户本人准备；uv 取 fonttools 时缓存里没有就会联网下载，Claude 运行前先报告文件名、来源与大小并等用户同意。
