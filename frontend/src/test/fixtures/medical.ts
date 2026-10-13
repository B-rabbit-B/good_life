// 医嘱的测试数据：条目（待核对、生效中、待复核、带解除建议、已解除、已作废）、医嘱单、证据与事件。
// 内容照设计稿 07a 至 07f。
import type { EventOut, EvidenceOut, MedicalEventOut, MedicalItemOut, OrderOut } from '../../api/types'

export const REVIEW_REASON = '已到复查日期，请确认是否还需要继续遵守'
export const END_SOON_REASON = '即将到预计结束日期，请确认是否还需要继续遵守'
export const EXPIRED_REASON = '未确认的条目已过预计结束日期，自动作废'

export const ORDER_ID = '00000000-0000-4000-8000-0000000000f1'
export const SOURCE_TEXT = '头孢呋辛酯片 0.25g，每日两次，连服 7 天。服药期间及停药后 7 天内禁止饮酒。'

export function medicalItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return {
    id: '00000000-0000-4000-8000-0000000000d1',
    order_id: ORDER_ID,
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
    start_date: '2026-09-05',
    end_date: '2026-10-17',
    review_date: null,
    resolution_proposed_at: '2026-10-10T11:20:00Z',
    resolution_reason: '用户转述医生说已经好了',
    ...over,
  })
}

/** 生效中、没有建议的条目 */
export function activeItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({
    id: '00000000-0000-4000-8000-0000000000d3',
    category: 'diet_avoid',
    content: '避免动物内脏与浓肉汤（高嘌呤）',
    subjects: ['动物内脏', '浓肉汤'],
    start_date: '2026-08-20',
    review_date: '2026-12-20',
    ...over,
  })
}

/** 提取出来、等待核对的条目（设计稿 07b） */
export function pendingItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({
    id: '00000000-0000-4000-8000-0000000000c1',
    category: 'medication_diet',
    status: 'pending_confirmation',
    origin: 'extracted',
    confidence: 'medium',
    content: '服药期间及停药后 7 天内禁止饮酒',
    subjects: ['酒精饮品', '含酒精的菜（如醉虾、酒酿）'],
    source_excerpt: SOURCE_TEXT,
    start_date: '2026-10-11',
    end_date: '2026-10-25',
    review_date: null,
    notes: ['涉及用药，时间范围可能以用药或停药为起点，请务必对照原文核对'],
    confirmed_at: null,
    created_at: '2026-10-11T13:15:00Z',
    updated_at: '2026-10-11T13:15:00Z',
    ...over,
  })
}

export function resolvedItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({
    id: '00000000-0000-4000-8000-0000000000e1',
    category: 'diet_avoid',
    status: 'resolved',
    content: '术后两周内避免辛辣刺激食物',
    subjects: ['辛辣'],
    review_date: null,
    closed_at: '2026-09-20T00:30:00Z',
    ...over,
  })
}

export function voidedItem(over: Partial<MedicalItemOut> = {}): MedicalItemOut {
  return medicalItem({
    id: '00000000-0000-4000-8000-0000000000e2',
    category: 'diet_require',
    status: 'voided',
    content: '每日饮水不少于 1500 毫升',
    subjects: ['饮水'],
    review_date: null,
    confirmed_at: null,
    closed_at: '2026-09-06T02:00:00Z',
    ...over,
  })
}

export function evidence(over: Partial<EvidenceOut> = {}): EvidenceOut {
  return {
    id: '00000000-0000-4000-8000-0000000000a1',
    filename: '出院小结.jpg',
    content_type: 'image/jpeg',
    size_bytes: 1_258_291,
    created_at: '2026-10-11T13:15:05Z',
    ...over,
  }
}

/** 医嘱单；items 由处理器按 order_id 从条目里取，这里给的会被覆盖 */
export function order(over: Partial<OrderOut> = {}): OrderOut {
  return {
    id: ORDER_ID,
    order_date: '2026-10-11',
    source_text: `${SOURCE_TEXT}一周后门诊复查。`,
    extractor: 'rule-based-v1',
    created_at: '2026-10-11T13:15:00Z',
    ignored: [{ text: '头孢呋辛酯片 0.25g，每日两次，连服 7 天', reason: '用药信息（药名、用法、剂量）不在本系统判断范围内，请遵医嘱或咨询医生、药师' }],
    notes: [],
    items: [],
    evidence: [evidence()],
    ...over,
  }
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

/** 跨条目审计列表里的一条事件 */
export function medicalEvent(item: MedicalItemOut, action: string, over: Partial<MedicalEventOut> = {}): MedicalEventOut {
  return {
    ...itemEvent(action),
    item_id: item.id,
    item_category: item.category,
    item_content: item.content,
    ...over,
  }
}
