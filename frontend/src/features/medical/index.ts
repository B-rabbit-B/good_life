// 医嘱模块对其他页面公开的部分：健康页的医嘱视图与子标签。
// 对话页首屏用的条目上下文在 api/itemContext；对话页按需加载的继续遵守面板直接按模块动态引入（见 test/boundaries.test.ts 的例外），
// 不经这里：经这里会把整个医嘱视图一起下载。
export { MedicalTabs, MedicalView } from './MedicalView'
