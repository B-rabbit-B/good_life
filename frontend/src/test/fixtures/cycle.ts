// 经期的测试数据（设计稿 06 的样子，日期都相对今天）：四次经期、三个完整周期（30、29、29 天），
// 最近一次经期 13 天前开始、持续 5 天，今天是本周期第 14 天（卵泡期）；预测下次在 16 天后开始，把握范围前后 2 天。
// 说明与免责句照抄后端（app/cycle/engine.py、app/cycle/tips.py、tips_rules.json）。
import type { CycleStatsOut, DayLogOut, PeriodOut, PhaseOut, PredictionOut, TipOut, TipsOut } from '../../api/types'
import { addDays, todayISO } from '../../lib/dates'

export const PREDICTION_DISCLAIMER = '预测仅供参考，不能用于避孕或诊断。'
export const INSUFFICIENT_DATA_NOTE = '数据不足：至少需要记录 3 次月经的开始日期，才能给出预测，目前的结果仅供参考。'
export const FEW_CYCLES_NOTE = '记录的周期还比较少，预测仅供参考，预测区间已相应放宽。'
export const TIPS_DISCLAIMER = '以上内容是一般性的生活方式建议，不构成医疗建议，不能用于避孕，也不能用于诊断；身体不适请及时就医。'

export const FOLLICULAR_TIP: TipOut = {
  id: 'follicular-exercise',
  phase: 'follicular',
  category: 'lifestyle',
  severity: 'info',
  title: '适合安排运动',
  content: '这一阶段不少人精力较好，可以按自己的状态安排强度稍高的运动。',
  basis: '部分人在经期结束后主观精力更好，个体差异很大，以自身感受为准。',
}

const ANY_TIP: TipOut = {
  id: 'any-follow-medical-advice',
  phase: 'any',
  category: 'lifestyle',
  severity: 'info',
  title: '有医嘱以医嘱为准',
  content: '以上提示是一般性的生活建议；如果你有医生给出的饮食或用药要求，请以医嘱为准。',
  basis: '本产品只提供生活方式参考，不替代医生的个体化建议。',
}

let seq = 0
const uuid = () => {
  seq += 1
  return `40000000-0000-4000-8000-${String(seq).padStart(12, '0')}`
}

export function period(start: string, end: string | null): PeriodOut {
  return { id: uuid(), start_date: start, end_date: end, created_at: `${start}T08:00:00Z` }
}

/** 最近一次经期开始的日期：13 天前（今天是第 14 天） */
export const latestStart = (today = todayISO()) => addDays(today, -13)

/** 四次经期，新的在前（与 GET /api/cycle/periods 的顺序一致）；open 时最近一次还没结束 */
export function deckPeriods(today = todayISO(), { open = false }: { open?: boolean } = {}): PeriodOut[] {
  const s = latestStart(today)
  return [
    period(s, open ? null : addDays(s, 4)),
    period(addDays(s, -29), addDays(s, -25)),
    period(addDays(s, -58), addDays(s, -54)),
    period(addDays(s, -88), addDays(s, -84)),
  ]
}

export function prediction(today = todayISO(), overrides: Partial<PredictionOut> = {}): PredictionOut {
  const next = addDays(latestStart(today), 29)
  return {
    status: 'ok',
    next_period_start: next,
    next_period_range: { earliest: addDays(next, -2), latest: addDays(next, 2) },
    ovulation_day: addDays(next, -14),
    ovulation_range: { earliest: addDays(next, -16), latest: addDays(next, -12) },
    fertile_window: { earliest: addDays(next, -19), latest: addDays(next, -13) },
    flags: ['few_cycles'],
    notes: [FEW_CYCLES_NOTE],
    disclaimer: PREDICTION_DISCLAIMER,
    ...overrides,
  }
}

export function insufficientPrediction(): PredictionOut {
  return {
    status: 'insufficient_data',
    next_period_start: null,
    next_period_range: null,
    ovulation_day: null,
    ovulation_range: null,
    fertile_window: null,
    flags: [],
    notes: [INSUFFICIENT_DATA_NOTE],
    disclaimer: PREDICTION_DISCLAIMER,
  }
}

export function phase(today = todayISO(), overrides: Partial<PhaseOut> = {}): PhaseOut {
  return {
    day: today,
    phase: 'follicular',
    cycle_day: 14,
    days_until_next_period: 16,
    is_predicted: true,
    reason: null,
    flags: ['few_cycles'],
    disclaimer: PREDICTION_DISCLAIMER,
    ...overrides,
  }
}

export function tips(today = todayISO(), overrides: Partial<TipsOut> = {}): TipsOut {
  return { phase: phase(today), tips: [FOLLICULAR_TIP, ANY_TIP], disclaimer: TIPS_DISCLAIMER, ...overrides }
}

export function stats(overrides: Partial<CycleStatsOut> = {}): CycleStatsOut {
  return {
    cycle_count: 3,
    period_count: 4,
    avg_cycle_length: 29.2,
    cycle_length_std: 0.5,
    shortest_cycle: 29,
    longest_cycle: 30,
    avg_period_length: 5,
    recent_cycle_lengths: [30, 29, 29],
    logged_days: 2,
    top_symptoms: [],
    average_pain_on_bleeding_days: null,
    ...overrides,
  }
}

export function dayLog(date: string, overrides: Partial<DayLogOut> = {}): DayLogOut {
  return {
    log_date: date, flow: null, pain: null, mood: 'good', symptoms: [], note: null, updated_at: `${date}T12:00:00Z`,
    ...overrides,
  }
}
