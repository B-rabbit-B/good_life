// 审计列表的一行（07e）：时间、动作、条目内容原文、状态变化与来源。事件的原因原文照搬，不改写。
import type { MedicalEventOut } from '../../api/types'
import { formatStamp } from '../../lib/dates'
import { EVENT_SOURCE_LABELS, eventActionLabel, ITEM_STATUS_LABELS } from '../../lib/medicalLabels'

export interface AuditLine {
  time: string
  action: string
  content: string
  transition: string
  source: string
}

/** 来源后面接上原因原文：来源本身带括号时并进同一对括号（“系统（打开应用时检查，原因）”） */
export function withReason(source: string, reason: unknown): string {
  if (typeof reason !== 'string' || reason === '') return source
  return source.endsWith('）') ? `${source.slice(0, -1)}，${reason}）` : `${source}（${reason}）`
}

export function auditLine(event: MedicalEventOut): AuditLine {
  const to = ITEM_STATUS_LABELS[event.to_status]
  let transition = `新建为 ${to}`
  if (event.from_status !== null) {
    transition = event.from_status === event.to_status ? '状态不变' : `${ITEM_STATUS_LABELS[event.from_status]} 到 ${to}`
  }
  let source = withReason(EVENT_SOURCE_LABELS[event.source], event.detail?.reason)
  const fields = event.detail?.fields
  if (Array.isArray(fields)) source += `，修改了 ${fields.length} 个字段`
  return {
    time: formatStamp(event.occurred_at),
    action: eventActionLabel(event.action, event.source),
    content: event.item_content,
    transition,
    source,
  }
}
