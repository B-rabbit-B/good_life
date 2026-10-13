import { describe, expect, it } from 'vitest'
import { activeItem, dueItem, pendingItem, proposalItem, resolvedItem, voidedItem } from '../../test/fixtures/medical'
import { itemActionsFor, resolveSecondaryFor } from './itemActions'

const labels = (item: Parameters<typeof itemActionsFor>[0]) => itemActionsFor(item).map((action) => action.label)
const kinds = (item: Parameters<typeof itemActionsFor>[0]) => itemActionsFor(item).map((action) => action.kind)

describe('item actions', () => {
  it('offers void, edit and confirm for an item waiting to be checked', () => {
    expect(kinds(pendingItem())).toEqual(['void', 'edit', 'confirm'])
    expect(labels(pendingItem())).toEqual(['作废', '修改', '确认生效'])
  })

  it('offers continue and resolve for an item due for review', () => {
    expect(kinds(dueItem())).toEqual(['continue', 'resolve'])
    expect(labels(dueItem())).toEqual(['继续遵守', '确认解除'])
    // 待复核的条目即使也带着解除建议，仍按待复核处理
    expect(kinds(dueItem({ resolution_proposed_at: '2026-10-10T11:20:00Z', resolution_reason: '好了' }))).toEqual(['continue', 'resolve'])
  })

  it('offers keep and resolve for an active item with a proposal', () => {
    expect(kinds(proposalItem())).toEqual(['cancel-proposal', 'resolve'])
    expect(labels(proposalItem())).toEqual(['不解除', '确认解除'])
  })

  it('offers edit and resolve for an active item without a proposal', () => {
    expect(kinds(activeItem())).toEqual(['edit', 'resolve'])
    expect(labels(activeItem())).toEqual(['修改', '确认解除'])
  })

  it('offers nothing for resolved and voided items', () => {
    expect(itemActionsFor(resolvedItem())).toEqual([])
    expect(itemActionsFor(voidedItem())).toEqual([])
  })

  it('never writes delete', () => {
    const all = [pendingItem(), dueItem(), proposalItem(), activeItem(), resolvedItem(), voidedItem()]
      .flatMap((item) => labels(item))
    expect(all.some((label) => label.includes('删除'))).toBe(false)
    expect(['继续遵守', '不解除，撤销这条建议', '取消']).toEqual(
      [dueItem(), proposalItem(), activeItem()].map((item) => resolveSecondaryFor(item).label),
    )
  })
})

describe('resolve secondary button', () => {
  it('opens the continue sheet for an item due for review', () => {
    expect(resolveSecondaryFor(dueItem())).toEqual({ label: '继续遵守', action: 'open-continue' })
  })

  it('cancels the proposal for an active item with one', () => {
    expect(resolveSecondaryFor(proposalItem())).toEqual({ label: '不解除，撤销这条建议', action: 'cancel-proposal' })
  })

  it('only closes for an active item without a proposal', () => {
    expect(resolveSecondaryFor(activeItem())).toEqual({ label: '取消', action: 'close' })
  })
})
