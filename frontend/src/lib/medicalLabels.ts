// 医嘱页专用的标签映射：条目状态、审计动作与审计来源（流程文案，不含业务判断）。
// 不放在 labels.ts：那个文件在对话页首屏的块里，放进去会让对话页多下载这几张只有医嘱页用的表。
import type { EventAction, EventSource, ItemStatus } from './labels'

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  pending_confirmation: '待核对', active: '生效中', pending_review: '待复核', resolved: '已解除', voided: '已作废',
}

/** created 按来源区分：提取器是“提取为待核对”，你本人是“手动录入”（用 eventActionLabel） */
export const EVENT_ACTION_LABELS: Record<EventAction, string> = {
  created: '提取为待核对',
  confirmed: '确认生效',
  edited: '修改',
  voided: '作废',
  expired: '自动作废',
  continued: '继续执行',
  review_due: '进入待复核',
  resolution_proposed: '提出解除建议',
  resolution_proposal_cancelled: '撤销解除建议',
  resolved: '确认解除',
}
export const CREATED_MANUAL_LABEL = '手动录入'

/** 审计里一条事件的动作名；后端新加的动作原样显示代码 */
export function eventActionLabel(action: string, source: EventSource): string {
  if (action === 'created' && source === 'user') return CREATED_MANUAL_LABEL
  return (EVENT_ACTION_LABELS as Record<string, string>)[action] ?? action
}

export const EVENT_SOURCE_LABELS: Record<EventSource, string> = {
  user: '你本人', system: '系统（打开应用时检查）', extractor: '提取', agent: '助手',
}
