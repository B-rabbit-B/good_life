# frontend/src/styles 目录说明书

## 职责
- 全站样式。tokens.css 是颜色、字号、间距、圆角、阴影、模糊量等设计令牌的唯一来源（从设计稿 :root 搬入）；base.css 是基础排版；materials.css 定义四种材质（瓷胎、静玻璃、活玻璃、厚玻璃）。
- components/ 下一个组件或一块功能界面一张样式表，既有共用组件的（button.css、sheet.css），也有功能页面的（medical.css、chat.css、restaurants.css 等）；由用到它的组件或页面自己引入。

## 边界
- main.tsx 按 fonts、tokens、base、materials 的顺序引入全局样式，组件样式表排在它们之后。
- fonts.css 与 fonts-manifest.json 是 pnpm fonts（scripts/subset-fonts.mjs）生成的，不手改；lib/titles.test.ts 用 manifest 检查宋体子集覆盖与字体预算。
- 玻璃只在浏览器支持 backdrop-filter 且根节点 data-glass="on" 时启用，否则是实色；data-glass 由 components/glass/GlassModeProvider 按用户设置、系统“减少透明”与低端机判定（glass/lowEnd.ts）决定。

## 入口
- 改颜色、圆角、字号之类先改 tokens.css 里的令牌，不在组件样式表里写死数值。
- 玻璃性能预算（模糊总面积不超过视口 40% 等）见 docs/superpowers/design/step11/DESIGN.md 第十二节；降级规则见 GlassModeProvider 与 lowEnd.ts。

## 禁区
- 不手改生成的 fonts.css 与 fonts-manifest.json；不新增宋体标题（子集余量极小）。
- 不让对话路由的样式超出首屏预算（gzip 22 KB，pnpm build:check）；只在其他页面用的样式不要被对话页引入。
- 不在滚动列表里用 backdrop-filter；新的玻璃面积要先对照预算。
