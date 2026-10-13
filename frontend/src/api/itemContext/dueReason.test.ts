import { describe, expect, it } from 'vitest'
import type { EventOut } from '../types'
import { DUE_REASONS } from '../../lib/contract'
import { dueFieldOf, dueReasonOf, shortDue } from './dueReason'
import { proposerOf } from './proposer'

function event(seq: number, action: string, over: Partial<EventOut> = {}): EventOut {
  return {
    id: `e${seq}`, seq, occurred_at: '2026-10-12T08:00:00Z', action, from_status: 'active', to_status: 'active',
    source: 'system', detail: null, ...over,
  }
}

describe('due reason', () => {
  it('maps each backend reason to the field that triggered the review', () => {
    expect(dueFieldOf('已到复查日期，请确认是否还需要继续遵守')).toBe('review')
    expect(dueFieldOf('已过预计结束日期，请确认是否还需要继续遵守')).toBe('end')
    expect(dueFieldOf('今天是预计结束日期，请确认是否还需要继续遵守')).toBe('end')
    expect(dueFieldOf('即将到预计结束日期，请确认是否还需要继续遵守')).toBe('end')
    expect(Object.keys(DUE_REASONS)).toHaveLength(4)
    expect(dueFieldOf('别的说法')).toBeNull()
    expect(dueFieldOf(null)).toBeNull()
  })

  it('takes the reason of the last review_due event', () => {
    const events = [
      event(1, 'created', { source: 'user' }),
      event(2, 'review_due', { detail: { reason: '已到复查日期，请确认是否还需要继续遵守' } }),
      event(3, 'continued', { source: 'user' }),
      event(4, 'review_due', { detail: { reason: '即将到预计结束日期，请确认是否还需要继续遵守' } }),
    ]
    expect(dueReasonOf(events)).toBe('即将到预计结束日期，请确认是否还需要继续遵守')
    expect(dueReasonOf(events.slice(0, 1))).toBeNull()
    expect(dueReasonOf([])).toBeNull()
  })

  it('shortens a reason to its first clause', () => {
    expect(shortDue('已到复查日期，请确认是否还需要继续遵守')).toBe('已到复查日期')
    expect(shortDue('没有逗号')).toBe('没有逗号')
  })

  it('names who made the last proposal', () => {
    expect(proposerOf([event(1, 'resolution_proposed', { source: 'agent' })])).toBe('agent')
    expect(proposerOf([
      event(1, 'resolution_proposed', { source: 'agent' }), event(2, 'resolution_proposed', { source: 'user' }),
    ])).toBe('user')
    expect(proposerOf([event(1, 'review_due')])).toBeNull()
  })
})
