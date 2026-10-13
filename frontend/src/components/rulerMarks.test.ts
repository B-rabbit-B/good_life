// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { rulerMarks } from './rulerMarks'

describe('ruler marks', () => {
  it('places the 160 label 40 px left of the needle at 165 cm', () => {
    const { ticks, labels } = rulerMarks(304, 165, 1, 10, 8)
    const needle = 304 / 2
    const label = labels.find((l) => l.value === 160)
    expect(label?.x).toBe(needle - 40)
    // 1.5 像素宽的刻度向左偏 0.75，让中心对齐
    expect(ticks).toContainEqual({ x: needle - 40 - 0.75, major: true })
    expect(ticks).toContainEqual({ x: needle - 0.75, major: false })
    // 可见范围 v ± c / ppu：165 ± 19
    expect(ticks).toHaveLength(39)
    expect(labels.map((l) => l.value)).toEqual([150, 160, 170, 180])
  })

  it('places the 55 label 24 px left of the needle at 56.5 kg', () => {
    const { ticks, labels } = rulerMarks(304, 56.5, 0.5, 5, 16)
    const needle = 304 / 2
    expect(labels.find((l) => l.value === 55)?.x).toBe(needle - 24)
    // 可见范围 56.5 ± 9.5：47 到 66，每 0.5 一格
    expect(ticks).toHaveLength(39)
    expect(labels.map((l) => l.value)).toEqual([50, 55, 60, 65])
    expect(ticks.filter((t) => t.major)).toHaveLength(4)
    expect(ticks.every((t) => Number.isFinite(t.x))).toBe(true)
  })

  it('drops labels that do not fit', () => {
    // 168 时 150 的刻度在 x = 8，标签宽 28 放不下，只画刻度
    const { ticks, labels } = rulerMarks(304, 168, 1, 10, 8)
    expect(ticks).toContainEqual({ x: 8 - 0.75, major: true })
    expect(labels.map((l) => l.value)).not.toContain(150)
    for (const label of labels) {
      expect(label.x - 14).toBeGreaterThanOrEqual(0)
      expect(label.x + 14).toBeLessThanOrEqual(304)
    }
    // 宽度为 0（还没量到）时什么都不画
    expect(rulerMarks(0, 165, 1, 10, 8)).toEqual({ ticks: [{ x: -0.75, major: false }], labels: [] })
  })
})
