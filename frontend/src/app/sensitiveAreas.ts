// “本页有敏感区”的登记表（DESIGN.md 第四节“隐私遮盖”的表）。
// 页面在渲染时调用 useSensitivePage(页面键)（见 AppShell.tsx）登记自己，并把表里的每一块内容包进
// <Sensitive area="…">；全局遮盖开关盖住的正是这些区域。sensitiveAreaMismatch 用来核对页面上的敏感区
// 与登记表是否一致（单元测试与端到端测试都用它；这个文件不依赖 React 与浏览器，端到端测试可以直接引入）。

export const SENSITIVE_AREAS = {
  /** 全部消息、附注、开场卡片、待复核条 */
  chat: ['messages', 'notes', 'opening', 'reviewBar'],
  /** 饮食：能量账本、营养表、三餐；训练：顶部的运动限制（它是医嘱内容） */
  records: ['ledger', 'nutrients', 'meals', 'constraints'],
  /** 菜名、份量、数字（都在识别项里）与整餐评价 */
  photoResult: ['dishes', 'evaluation'],
  /** 地点输入、“记住大致区域”一行 */
  restaurants: ['place', 'rememberArea'],
  /** 医嘱的三个标签：全部内容 */
  medical: ['content'],
  /** 录入医嘱：全部内容 */
  medicalNew: ['content'],
  /** 经期：全部内容（两个记录按钮除外） */
  cycle: ['content'],
  /** 我的：全部档案内容、两个开关与单独同意两行 */
  me: ['profile', 'switches', 'consents'],
  /** 修改档案：全部档案内容（设计稿 13b 没有开关，两个开关只在“我的”） */
  profileEdit: ['profile'],
  /** 记一次训练：顶部的运动限制 */
  workoutNew: ['constraints'],
  /** 模型服务：“其他设置”里已保存的大致区域名 */
  models: ['savedArea'],
  /** 隐私与数据：已保存的大致区域、外部授权列表、调用记录；导出、清空对话与删除账号三块（不含内容，随本页一起遮盖） */
  privacy: ['savedArea', 'grants', 'audit', 'exportData', 'clearChat', 'deleteAccount'],
} as const

export type SensitivePage = keyof typeof SENSITIVE_AREAS
export type SensitiveArea = (typeof SENSITIVE_AREAS)[SensitivePage][number]

/** 滚动容器上记录当前页面键的属性；Sensitive 上记录区域名的属性 */
export const SENSITIVE_PAGE_ATTR = 'data-sensitive-page'
export const SENSITIVE_AREA_ATTR = 'data-sensitive-area'
export const UNNAMED_AREA = '(未命名)'

export function isSensitivePage(value: string): value is SensitivePage {
  return Object.prototype.hasOwnProperty.call(SENSITIVE_AREAS, value)
}

export interface SensitiveAreaMismatch {
  page: SensitivePage | null
  missing: string[]
  unexpected: string[]
}

/**
 * 核对敏感区：marker 是滚动容器上登记的页面键，present 是页面上每个 Sensitive 的区域名（没写 area 的记作 UNNAMED_AREA）。
 * missing 是登记表里有、页面上没有的区域；unexpected 是页面上有、登记表里没有的（包括没写 area 的 Sensitive）。
 * expected 默认是该页登记的全部区域；某些区域按数据才出现时（例如今天没有开场卡片），传入这一情形下应有的子集。
 * 页面没有登记时 page 为 null，此时页面上的任何敏感区都算 unexpected。
 */
export function compareSensitiveAreas(
  marker: string | null,
  present: readonly string[],
  expected?: readonly SensitiveArea[],
): SensitiveAreaMismatch {
  const page = marker !== null && isSensitivePage(marker) ? marker : null
  const registered: readonly string[] = page ? SENSITIVE_AREAS[page] : []
  const wanted: readonly string[] = expected ?? registered
  const presentSet = new Set(present)
  return {
    page,
    missing: wanted.filter((area) => !presentSet.has(area)),
    unexpected: [...new Set(present.filter((area) => !registered.includes(area)))],
  }
}

/** 在 DOM 上核对（单元测试用；端到端测试用 e2e/support/a11y.ts 的 expectSensitiveAreas） */
export function sensitiveAreaMismatch(root: ParentNode, expected?: readonly SensitiveArea[]): SensitiveAreaMismatch {
  const marker = root.querySelector(`[${SENSITIVE_PAGE_ATTR}]`)?.getAttribute(SENSITIVE_PAGE_ATTR) ?? null
  const present = Array.from(root.querySelectorAll('[data-sensitive]'))
    .map((el) => el.getAttribute(SENSITIVE_AREA_ATTR) ?? UNNAMED_AREA)
  return compareSensitiveAreas(marker, present, expected)
}
