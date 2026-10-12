// 待复核的原因：后端在 review_due 事件的 detail.reason 里写明（四句原文之一，见 contract.ts 的 DUE_REASONS）。
// 界面原样显示原文，只用映射找出触发复核的是复查日期还是预计结束。
import type { EventOut } from '../../api/types'
import { DUE_REASONS } from '../../lib/contract'

/** 最后一条 review_due 事件的原因原文；没有时为 null */
export function dueReasonOf(events: EventOut[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i]
    if (event?.action !== 'review_due') continue
    const reason = event.detail?.reason
    return typeof reason === 'string' ? reason : null
  }
  return null
}

/** 触发复核的字段：复查日期（review）或预计结束（end）；原因不认识时为 null */
export function dueFieldOf(reason: string | null): 'review' | 'end' | null {
  if (reason === null) return null
  return Object.prototype.hasOwnProperty.call(DUE_REASONS, reason) ? (DUE_REASONS[reason] ?? null) : null
}

/** 原因的第一个分句，例如“已到复查日期” */
export function shortDue(reason: string): string {
  return reason.split('，')[0] ?? reason
}
