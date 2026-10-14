# frontend/src/dev 目录说明书

## 职责
- 组件样张页 /dev/gallery（GalleryPage.tsx 与 gallery.css）：按设计稿“设计系统”一节与 12 块状态面板的顺序摆出全部共用组件，供与 docs/superpowers/design/step11/index.html 并排比较。
- 只做展示，数据都是设计稿里的示例，不发任何请求。

## 边界
- 依赖：components、api（只取 ApiError 构造错误示例）、styles；不引用 features。
- 只在开发模式或 VITE_GALLERY=1（端到端构建 .env.e2e）时由 app/routes.tsx 注册，正式构建里这段路由连同它的分包一起去掉。
- 端到端的 e2e/pages/gallery.spec.ts 与 e2e/visual 用它做页面级检查与截图比对。

## 入口
- 开发时运行 pnpm dev 后打开 /dev/gallery；新增或改动共用组件时在这里补一块示例。
- 测试：frontend/e2e/pages/gallery.spec.ts；可视比对见 frontend/e2e/visual。

## 禁区
- 不放业务页面或真实数据；不让正式构建注册这个路由。
- 不让任何正式页面引用这里的代码。
- 不让文件超过 800 行（GalleryPage.tsx 已有六百多行）：再加较多示例前先按设计稿的分节拆成几个文件。
