# frontend/src/components 目录说明书

## 职责
- 不认业务的界面零件：按钮、输入框与刻度尺、底部面板（Sheet、ConfirmSheet）、页头、导航、操作坞、标题（Title）、状态页（states/）、标记与小图形、磨砂材质（Surface、glass/）、遮盖（cover、Sensitive）、轻提示（Toast）。
- 样子与无障碍照 docs/superpowers/design/step11/DESIGN.md：React Aria 提供焦点、键盘与读屏行为；每个组件引入自己的样式表（styles/components/ 下）。
- Sensitive：遮盖时盖上不透明斜纹并设 aria-hidden 与 inert，浏览器不支持 inert 时暂存并恢复可聚焦元素的 tabindex；area 名必须是 app/sensitiveAreas.ts 登记过的。

## 边界
- 依赖：lib、api（只取 ApiError 这类错误类型）、styles；不引用 features；引用 app 只限 shellContext 与 sensitiveAreas（test/boundaries.test.ts 守护）。
- 被引用：features、app、dev 的组件样张页。
- 底部面板没有拖动把手、点遮罩不关，只能用 Esc 或按钮关闭；同一子标签里同一时间只开一个（useSheetHost）。

## 入口
- 单次锁：ConfirmSheet 的确认经 lib/singleFlight 的 useSingleFlight，双击或连按时第二次直接跳过；按钮的 isPending 要等下一次渲染才生效，不能只靠它。
- 面板锁定：确认请求进行中（含次按钮自己的请求）时确认、次按钮与取消都停用，面板不响应 Esc 关闭（onBusyChange）；需要“请求中不能关”的新面板沿用这一套。
- 不可撤销的动作用 ConfirmSheet 的 ack（必须勾选的一句话），勾选前确认按钮不可用。
- 标题：固定的宋体标题用 Title 与 lib/titles；面板标题二选一：titleKey（宋体，键在 titles.json）或 title（黑体，任意文字）。
- 测试与组件同名放在一起；整体渲染与读屏检查见 shell.test.tsx、graphics.test.tsx、marks.test.tsx 等。

## 禁区
- 不放业务判断与业务文案（例如“医嘱”“经期”专用的逻辑）；只有一个功能用的零件留在那个功能目录。
- 本步骤不新增 titleKey 与 titles.json 的键（宋体子集余量极小）：新面板用 title，新区块用 sec-l 小标题，都是黑体。
- 不用动画库；动效用 CSS 与 lib/motion，并尊重减少动效的设置。
- 不绕开 Sensitive 自己做遮盖，也不给 Sensitive 写未登记的 area。
