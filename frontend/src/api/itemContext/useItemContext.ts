import { useItemEvents } from '../hooks/medical'
import type { MedicalItemOut } from '../types'
import { dueFieldOf, dueReasonOf } from './dueReason'
import { proposerOf } from './proposer'

export interface ItemContext {
  /** 后端写的到期原因原文（最后一条 review_due 事件） */
  dueReason: string | null
  /** 触发复核的是复查日期还是预计结束 */
  dueField: 'review' | 'end' | null
  /** 解除建议是谁提出的 */
  proposer: 'agent' | 'user' | null
}

/** 待复核或带解除建议的条目：取它的事件，读出到期原因与提出建议的人；其他条目不请求 */
export function useItemContext(item: MedicalItemOut | undefined): ItemContext {
  const enabled = item !== undefined && (item.status === 'pending_review' || item.resolution_proposed_at !== null)
  const events = useItemEvents(item?.id ?? '', enabled)
  const list = enabled ? (events.data ?? []) : []
  const dueReason = dueReasonOf(list)
  return { dueReason, dueField: dueFieldOf(dueReason), proposer: proposerOf(list) }
}
