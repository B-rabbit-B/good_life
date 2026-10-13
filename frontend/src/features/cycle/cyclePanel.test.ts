import { describe, expect, it } from 'vitest'
import { insufficientPrediction, period, phase, prediction, stats } from '../../test/fixtures/cycle'
import { cycleTicksModel, predictedPeriodDays } from './cyclePanel'

// 设计稿 06：最近一次 9月29日至10月3日，预计 10月28日开始、把握范围 10月26日至30日，今天 10月12日
const TODAY = '2026-10-12'
const DECK_PREDICTION = prediction(TODAY, {
  next_period_start: '2026-10-28',
  next_period_range: { earliest: '2026-10-26', latest: '2026-10-30' },
})
const PERIODS = [period('2026-09-29', '2026-10-03'), period('2026-08-31', '2026-09-04')]

describe('cycle ticks model', () => {
  it('counts days from the latest start to the end of the predicted range', () => {
    expect(cycleTicksModel(PERIODS, DECK_PREDICTION, phase(TODAY))).toEqual({
      length: 32, periodDays: 5, predicted: [28, 32], today: 14,
    })
  })

  it('takes the latest period whatever the order', () => {
    expect(cycleTicksModel([...PERIODS].reverse(), DECK_PREDICTION, phase(TODAY))?.periodDays).toBe(5)
  })

  it('counts an open period through today', () => {
    const model = cycleTicksModel([period('2026-09-29', null)], DECK_PREDICTION, phase('2026-10-01'))
    expect(model).toMatchObject({ periodDays: 3, today: 3 })
  })

  it('is null without a prediction or a period', () => {
    expect(cycleTicksModel(PERIODS, insufficientPrediction(), phase(TODAY))).toBeNull()
    expect(cycleTicksModel([], DECK_PREDICTION, phase(TODAY))).toBeNull()
  })
})

describe('predicted period days', () => {
  it('takes the rounded average period length from the predicted start', () => {
    expect(predictedPeriodDays(DECK_PREDICTION, stats({ avg_period_length: 4.5 })))
      .toEqual(['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01'])
    expect(predictedPeriodDays(DECK_PREDICTION, stats({ avg_period_length: 3.2 })))
      .toEqual(['2026-10-28', '2026-10-29', '2026-10-30'])
  })

  it('is empty without a prediction or an average length', () => {
    expect(predictedPeriodDays(insufficientPrediction(), stats())).toEqual([])
    expect(predictedPeriodDays(DECK_PREDICTION, stats({ avg_period_length: null }))).toEqual([])
  })
})
