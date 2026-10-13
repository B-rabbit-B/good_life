import { describe, expect, it } from 'vitest'
import { formatStamp } from '../../lib/dates'
import {
  activeItem, dueItem, EXPIRED_REASON, medicalEvent, pendingItem, proposalItem, REVIEW_REASON, voidedItem,
} from '../../test/fixtures/medical'
import { auditLine } from './auditLine'

describe('audit line', () => {
  it('writes an extraction', () => {
    const item = pendingItem()
    const line = auditLine(medicalEvent(item, 'created', {
      occurred_at: '2026-10-11T13:15:00Z', from_status: null, to_status: 'pending_confirmation', source: 'extractor',
    }))
    expect(line).toEqual({
      time: formatStamp('2026-10-11T13:15:00Z'),
      action: '提取为待核对',
      content: '服药期间及停药后 7 天内禁止饮酒',
      transition: '新建为 待核对',
      source: '提取',
    })
  })

  it('writes a manual entry', () => {
    const line = auditLine(medicalEvent(pendingItem(), 'created', { from_status: null, to_status: 'pending_confirmation', source: 'user' }))
    expect(line.action).toBe('手动录入')
    expect(line.source).toBe('你本人')
  })

  it('writes a confirmation by the user', () => {
    const line = auditLine(medicalEvent(activeItem(), 'confirmed', { from_status: 'pending_confirmation', to_status: 'active', source: 'user' }))
    expect(line).toMatchObject({ action: '确认生效', transition: '待核对 到 生效中', source: '你本人' })
  })

  it('writes a system review with its reason at the time it was checked', () => {
    const line = auditLine(medicalEvent(dueItem(), 'review_due', {
      occurred_at: '2026-10-12T10:40:00Z', from_status: 'active', to_status: 'pending_review', source: 'system',
      detail: { reason: REVIEW_REASON },
    }))
    expect(line).toEqual({
      time: formatStamp('2026-10-12T10:40:00Z'),
      action: '进入待复核',
      content: '低盐饮食，每日钠不超过 2000 毫克',
      transition: '生效中 到 待复核',
      source: `系统（打开应用时检查，${REVIEW_REASON}）`,
    })
    expect(line.time).not.toMatch(/00:00$/)
  })

  it('writes proposing and withdrawing a resolution without a status change', () => {
    const item = proposalItem()
    const proposed = auditLine(medicalEvent(item, 'resolution_proposed', {
      from_status: 'active', to_status: 'active', source: 'agent', detail: { reason: '用户转述医生说已经好了' },
    }))
    expect(proposed).toMatchObject({ action: '提出解除建议', transition: '状态不变', source: '助手（用户转述医生说已经好了）' })
    const cancelled = auditLine(medicalEvent(item, 'resolution_proposal_cancelled', { from_status: 'active', to_status: 'active', source: 'user' }))
    expect(cancelled).toMatchObject({ action: '撤销解除建议', transition: '状态不变', source: '你本人' })
  })

  it('writes a void with its reason and an automatic void', () => {
    const item = voidedItem()
    const voided = auditLine(medicalEvent(item, 'voided', {
      from_status: 'pending_confirmation', to_status: 'voided', source: 'user', detail: { reason: '重复录入' },
    }))
    expect(voided).toMatchObject({ action: '作废', transition: '待核对 到 已作废', source: '你本人（重复录入）' })
    const expired = auditLine(medicalEvent(item, 'expired', {
      from_status: 'pending_confirmation', to_status: 'voided', source: 'system', detail: { reason: EXPIRED_REASON },
    }))
    expect(expired).toMatchObject({ action: '自动作废', source: `系统（打开应用时检查，${EXPIRED_REASON}）` })
  })

  it('counts the edited fields', () => {
    const line = auditLine(medicalEvent(activeItem(), 'edited', {
      from_status: 'active', to_status: 'active', source: 'user', detail: { fields: ['end_date', 'subjects'] },
    }))
    expect(line).toMatchObject({ action: '修改', transition: '状态不变', source: '你本人，修改了 2 个字段' })
    const confirmed = auditLine(medicalEvent(activeItem(), 'confirmed', {
      from_status: 'pending_confirmation', to_status: 'active', source: 'user', detail: { fields: ['content'] },
    }))
    expect(confirmed.source).toBe('你本人，修改了 1 个字段')
  })

  it('shows an unknown action code as it is', () => {
    expect(auditLine(medicalEvent(activeItem(), 'something_new')).action).toBe('something_new')
  })
})
