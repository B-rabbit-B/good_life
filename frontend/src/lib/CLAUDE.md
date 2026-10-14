# frontend/src/lib 目录说明书

## 职责
- 最底层的工具与“前端唯一可以写死的东西”：
  - contract.ts：后端固定文案与常量的副本（健康提示、医嘱提醒开头、到期原因原文、风险类别、上限数字等），每一项注明出自后端哪个常量，backend/tests/test_frontend_contract.py 逐字、逐项核对；
  - labels.ts 与各模块的 *Labels.ts：枚举到中文的标签映射，类型取自生成的接口类型，后端加了取值这里会编译报错；
  - titles.json 与 titles.ts：全部写死的宋体标题，宋体字体子集只含这些字加 SERIF_EXTRA；
  - formErrors.ts（把后端错误归到表单字段，说明原文照搬）、singleFlight.ts（单次锁）、dates.ts、format.ts、motion.ts（减少动效偏好）、photoHandoff.ts（对话底座把照片交给拍照页，只在内存里）、queryParams.ts。

## 边界
- 依赖：不引用 api（例外：labels 只取 api/schema 的类型、formErrors 认 api/errors 的 ApiError，test/boundaries.test.ts 登记）；也不引用 components、features、app。
- 被几乎所有层引用；vite.config.ts 把 dates、labels、motion、contract 放进对话页与其他页面共用的 common 块。
- 这里只有映射、格式与流程工具，不做业务判断：结论、说明与错误码都原样显示后端返回的内容。

## 入口
- 改后端固定文案时，同一个提交里改 contract.ts（后端测试会提醒）；新增副本先确认后端常量的名字并在注释里写明出处。
- 宋体子集预算：宋体不超过 40 KiB，宋体加数字子集不超过 45 KiB（titles.test.ts）；当前余量只有约 96 字节。改标题后在 frontend 运行 pnpm fonts 重新生成子集与 styles/fonts-manifest.json。
- 测试：titles.test.ts、formErrors.test.ts、singleFlight.test.tsx、dates.test.ts、format.test.ts、motion.test.tsx、photoHandoff.test.tsx。

## 禁区
- 步骤 12 不在 titles.json 新增任何键：新面板与新区块的标题一律用黑体（面板用 SheetTitle 的 title，区块用 sec-l 小标题）。
- 不在 contract.ts 之外抄后端文案或常量；不把副本改写成“意思差不多”的文字。
- 不把业务规则写成工具函数（例如按性别判断经期、按数值判断能不能吃）。
- photoHandoff 不写任何浏览器存储；照片不落地。
