import { describe, expect, it } from 'vitest'
import { summary } from '../../test/fixtures/nutrition'
import { nutrientRows } from './nutrientRows'

describe('nutrient rows', () => {
  it('lists the five nutrients in order with intake and unit', () => {
    const rows = nutrientRows(summary())
    expect(rows.map((row) => row.label)).toEqual(['蛋白质', '脂肪', '碳水化合物', '膳食纤维', '钠'])
    expect(rows.map((row) => row.intake)).toEqual(['52.4', '38.1', '128.0', '9.2', '1,640'])
    expect(rows.map((row) => row.unit)).toEqual(['克', '克', '克', '克', '毫克'])
  })

  it('writes a range need as low to high', () => {
    const rows = nutrientRows(summary())
    expect(rows.map((row) => row.need)).toEqual(['70', '41–62', '231–301', '25–30', '2,000'])
  })

  it('shows what is left only for the nutrients the backend reports', () => {
    const rows = nutrientRows(summary())
    expect(rows.map((row) => row.remaining)).toEqual(['17.6', '—', '—', '—', '360'])
  })

  it('marks sodium as an upper limit', () => {
    const rows = nutrientRows(summary())
    expect(rows.map((row) => row.limit)).toEqual([false, false, false, false, true])
  })

  it('warns on the sodium row once nothing is left', () => {
    expect(nutrientRows(summary()).some((row) => row.warn)).toBe(false)
    const over = nutrientRows(summary({ remaining: { energy_kcal: 765, protein_g: 17.6, sodium_mg: 0 } }))
    expect(over.map((row) => row.warn)).toEqual([false, false, false, false, true])
    const below = nutrientRows(summary({ remaining: { energy_kcal: 765, protein_g: 17.6, sodium_mg: -120 } }))
    expect(below.find((row) => row.key === 'sodium')?.remaining).toBe('-120')
    expect(below.find((row) => row.key === 'sodium')?.warn).toBe(true)
  })

  it('fills the bar by intake over need, capped at the end', () => {
    const rows = nutrientRows(summary())
    expect(rows[0]?.fill).toBeCloseTo(52.4 / 70)
    expect(rows[1]?.fill).toBeCloseTo(38.1 / 41)
    expect(rows[4]?.fill).toBeCloseTo(1640 / 2000)
    const full = nutrientRows(summary({ total: { ...summary().total, protein_g: 200 } }))
    expect(full[0]?.fill).toBe(1)
  })

  it('shows dashes when the needs cannot be estimated', () => {
    const rows = nutrientRows(summary({ needs: { ...summary().needs, status: 'insufficient_profile', energy_kcal: null,
      protein_g: null, fat_g_low: null, fat_g_high: null, carbohydrate_g_low: null, carbohydrate_g_high: null,
      fiber_g_low: null, fiber_g_high: null, sodium_mg_max: null }, remaining: null }))
    expect(rows.map((row) => row.need)).toEqual(['—', '—', '—', '—', '—'])
    expect(rows.map((row) => row.remaining)).toEqual(['—', '—', '—', '—', '—'])
    expect(rows.map((row) => row.fill)).toEqual([0, 0, 0, 0, 0])
  })

  it('shows a dash for a missing intake value', () => {
    const rows = nutrientRows(summary({ total: { ...summary().total, fiber_g: null } }))
    expect(rows[3]?.intake).toBe('—')
  })
})
