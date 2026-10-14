# frontend/src 目录说明书

## 职责
- 前端源码。main.tsx 先引入全局样式（fonts、tokens、base、materials），再渲染 app/App.tsx（查询客户端、磨砂模式、遮盖、轻提示与路由）。
- 子目录：lib（最底层工具与后端文案副本）、api（接口、缓存键与失效）、components（不认业务的界面零件）、features（各功能页面）、app（外壳、路由、守卫、敏感区登记）、styles（令牌、基础样式、材质与各组件的样式表，组件自己引入自己的样式表）、test（测试支撑）、dev（组件样张页）。

## 边界
- 依赖方向由 test/boundaries.test.ts 扫描全部非测试源码的相对导入来守护，规则逐条是：
  - lib 不引用 api（例外：labels 只取 api/schema 的类型、formErrors 认 api/errors 的 ApiError）；
  - api 不引用 app、components、features；
  - components 不引用 features，也不引用 app（例外：app/shellContext、app/sensitiveAreas）；
  - 一个功能目录引用另一个功能目录只能经它的 index（例外：对话页按需加载 medical/ContinueSheet，只能写在 lazy 动态引入里）。
- 测试没有约束的方向照现状保持：features 会引用 app 的 paths、AppShell 的登记钩子、nav 等；app 的 routes 按需加载 features 与 dev；lib 不引用 components、features、app。新增例外要写进测试的 ALLOWED 并写明原因，过期的例外会让测试失败。
- 界面不做业务规则判断：模块是否开放看 /api/me/capabilities，结论与错误原样显示后端的 message 与 code。

## 入口
- 路由表 app/routes.tsx：每个页面按需加载；对话页是首屏，受首屏预算约束。
- 各目录的说明书：api、app、components、lib、features、test、dev 下各有一份 CLAUDE.md；styles 没有单独的说明书，规则写在这里与 lib/CLAUDE.md（字体）。
- 测试与源码放在一起（*.test.ts、*.test.tsx），支撑代码在 test/。

## 禁区
- 不用 EventSource（eslint 禁止，流式对话用 api/sse.ts 的 fetch 读流）；不引入动画库。
- 不在 lib、api、components 里写某个页面专用的东西；只有一个功能用的就留在那个功能目录。
- 敏感内容必须包在 components/Sensitive 里并在 app/sensitiveAreas.ts 登记，不登记的敏感区会让单元与端到端的核对失败。
- 每个文件不超过 800 行（生成的 api/schema.d.ts 与 openapi.json 除外）。
