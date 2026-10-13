// 经期模块对其他页面公开的部分：健康页按需加载经期视图（连同月历，只看医嘱时不下载）。
export const loadCycleView = () => import('./CycleView')
