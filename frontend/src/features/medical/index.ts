// 医嘱模块对其他页面公开的部分：健康页的医嘱视图与子标签，对话页按需加载的继续遵守面板。
// 对话页的首屏只用条目上下文（api/itemContext），不静态引入这里：静态引入会把整个医嘱视图带进对话页的首屏。
export { ContinueSheet } from './ContinueSheet'
export { MedicalTabs, MedicalView } from './MedicalView'
