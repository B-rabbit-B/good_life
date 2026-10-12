// 医嘱条目与事件的测试数据：一条到了复查日的待复核条目、一条带解除建议仍在生效的条目。
import type { EventOut, MedicalItemOut } from '../../api/types'

export const REVIEW_REASON = '已到复查日期，请确认是否还需要继续遵守'
export const END_SOON_REASON = '即将到预计结束日期，请确认是否还需要继续遵守'

export function medicalItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return {
    id: '00000000-0000-4000-8000-0000000000d1',
    order_id: '00000000-0000-4000-8000-0000000000f1',
    category: 'diet_require',
    status: 'active',
    origin: 'manual',
    confidence: null,
    content: '低盐饮食，每日钠不超过 2000 毫克',
    subjects: ['盐'],
    source_excerpt: null,
    start_date: '2026-07-12',
    end_date: null,
    review_date: '2026-11-12',
    missing_fields: [],
    notes: [],
    resolution_proposed_at: null,
    resolution_reason: null,
    confirmed_at: '2026-07-12T08:00:00Z',
    closed_at: null,
    created_at: '2026-07-12T08:00:00Z',
    updated_at: '2026-07-12T08:00:00Z',
    low_confidence: false,
    ...over,
  }
}

/** 到了复查日、已转为待复核的条目 */
export function dueItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({ status: 'pending_review', review_date: '2026-10-12', ...over })
}

/** 仍在生效、带着助手提出的解除建议的条目 */
export function proposalItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({
    id: '00000000-0000-4000-8000-0000000000d2',
    category: 'exercise_limit',
    content: '膝关节术后六周内避免跑跳',
    subjects: ['跑跳'],
    review_date: null,
    resolution_proposed_at: '2026-10-10T11:20:00Z',
    resolution_reason: '用户转述医生说已经好了',
    ...over,
  })
}

let seq = 0
export function itemEvent(action: string, over: Partial<EventOut> = {}): EventOut {
  seq += 1
  return {
    id: `00000000-0000-4000-8000-1000000000${String(seq).padStart(2, '0')}`,
    seq, occurred_at: '2026-10-12T08:00:00Z', action, from_status: 'active', to_status: 'active', source: 'system',
    detail: null, ...over,
  }
}

export const reviewDueEvent = (reason = REVIEW_REASON) =>
  itemEvent('review_due', { to_status: 'pending_review', detail: { reason } })

export const proposedEvent = (source: 'agent' | 'user' = 'agent') =>
  itemEvent('resolution_proposed', { source, detail: { reason: '用户转述医生说已经好了' } })
