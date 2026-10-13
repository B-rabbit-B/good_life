import { describe, expect, it } from 'vitest'
import { cardioWorkout, strengthWorkout } from '../../test/fixtures/fitness'
import { weekBars } from './weekBars'

const MONDAY = '2026-10-12'

describe('week bars', () => {
  it('has all seven days from monday with today marked', () => {
    const bars = weekBars(MONDAY, [], '2026-10-15')
    expect(bars.map((bar) => bar.date)).toEqual([
      '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16', '2026-10-17', '2026-10-18',
    ])
    expect(bars.map((bar) => bar.label)).toEqual(['一', '二', '三', '今天', '五', '六', '日'])
    expect(bars.filter((bar) => bar.isToday).map((bar) => bar.date)).toEqual(['2026-10-15'])
    expect(bars.every((bar) => bar.minutes === 0)).toBe(true)
  })

  it('uses the workout duration, or the sum of its cardio when it has none', () => {
    const cardio = cardioWorkout('2026-10-13', 'ex:brisk_walking', '快走', 35)
    const twoCardio = { ...cardio, cardio: [...cardio.cardio, { ...cardio.cardio[0]!, position: 2, duration_minutes: 10 }] }
    const bars = weekBars(MONDAY, [
      strengthWorkout(MONDAY),
      twoCardio,
      strengthWorkout('2026-10-14', { duration_minutes: 20 }),
      cardioWorkout('2026-10-14', 'ex:spinning', '动感单车', 25, { duration_minutes: 30 }),
      strengthWorkout('2026-10-14', { duration_minutes: null }),
      cardioWorkout('2026-10-19', 'ex:brisk_walking', '快走', 40),
    ], '2026-10-18')
    expect(bars.map((bar) => bar.minutes)).toEqual([50, 45, 50, 0, 0, 0, 0])
  })
})
