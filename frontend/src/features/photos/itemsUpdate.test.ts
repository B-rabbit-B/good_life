import { describe, expect, it } from 'vitest'
import { photoItem } from '../../test/fixtures/photos'
import { toItemsUpdate } from './itemsUpdate'

const rice = photoItem({ id: 'a', name: '杂粮饭', food_id: 'cfcd:rice', food_name: '杂粮饭' })
const pending = photoItem({
  id: 'b', name: '酸汤肥牛', status: 'needs_confirmation', food_id: null, food_name: null, nutrients: null,
  candidates: [{ food_id: 'dish:beef', name: '肥牛（火锅用）' }], review_reasons: ['needs_confirmation'],
})
const liver = photoItem({ id: 'c', name: '卤猪肝', food_id: 'cfcd:liver', food_name: '猪肝（卤）' })

describe('items update', () => {
  it('sends untouched items as id and name only', () => {
    const body = toItemsUpdate([pending, liver], { kind: 'edit', id: 'c', grams: 60 })
    expect(body[0]).toEqual({ id: 'b', name: '酸汤肥牛' })
  })

  it('keeps food_id for items that have one', () => {
    const body = toItemsUpdate([rice, pending], { kind: 'delete', id: 'b' })
    expect(body).toEqual([{ id: 'a', name: '杂粮饭', food_id: 'cfcd:rice' }])
  })

  it('sends the edited fields for the changed item', () => {
    expect(toItemsUpdate([rice, pending], { kind: 'edit', id: 'b', name: '肥牛' })).toEqual([
      { id: 'a', name: '杂粮饭', food_id: 'cfcd:rice' },
      { id: 'b', name: '肥牛' },
    ])
    expect(toItemsUpdate([pending], { kind: 'edit', id: 'b', food_id: 'dish:beef' }))
      .toEqual([{ id: 'b', name: '酸汤肥牛', food_id: 'dish:beef' }])
    expect(toItemsUpdate([pending], { kind: 'edit', id: 'b', portion_text: '一大份', grams: 300 }))
      .toEqual([{ id: 'b', name: '酸汤肥牛', portion_text: '一大份', grams: 300 }])
  })

  it('keeps the chosen food when only the amount changes', () => {
    expect(toItemsUpdate([liver], { kind: 'edit', id: 'c', grams: 60 }))
      .toEqual([{ id: 'c', name: '卤猪肝', grams: 60, food_id: 'cfcd:liver' }])
  })

  it('lets a renamed item match again by its new name', () => {
    expect(toItemsUpdate([liver], { kind: 'edit', id: 'c', name: '鸡肝' })).toEqual([{ id: 'c', name: '鸡肝' }])
  })

  it('drops a deleted item', () => {
    expect(toItemsUpdate([rice, pending, liver], { kind: 'delete', id: 'a' }).map((item) => item.id)).toEqual(['b', 'c'])
  })
})
