// 周期刻度与月历的显示换算（不重算任何规则，数字都来自后端的经期、预测、阶段与统计）。
import type { CycleStatsOut, PeriodOut, PhaseOut, PredictionOut } from '../../api/types'
import { addDays } from '../../lib/dates'

const DAY_MS = 86_400_000

/** 从 start 那天算起是第几天（start 当天是第 1 天）；用 UTC 的年月日算，避开时区 */
function dayOf(start: string, iso: string): number {
  const utc = (value: string) => {
    const [y = 0, m = 1, d = 1] = value.split('-').map(Number)
    return Date.UTC(y, m - 1, d)
  }
  return Math.round((utc(iso) - utc(start)) / DAY_MS) + 1
}

export interface CycleTicksModel {
  /** 刻度从最近一次经期开始日数到预测范围的最晚一天 */
  length: number
  /** 最近一次经期的实际天数（还没结束时到今天） */
  periodDays: number
  /** 预测范围是第几天到第几天 */
  predicted: [number, number]
  /** 今天是第几天 */
  today: number
}

/** 周期刻度的数字；没有预测（数据不足、已暂停）或没有任何经期时为 null */
export function cycleTicksModel(
  periods: readonly PeriodOut[], prediction: PredictionOut, phase: PhaseOut,
): CycleTicksModel | null {
  const range = prediction.status === 'ok' ? prediction.next_period_range : null
  if (!range || periods.length === 0) return null
  const latest = periods.reduce((a, b) => (b.start_date > a.start_date ? b : a))
  const start = latest.start_date
  return {
    length: dayOf(start, range.latest),
    periodDays: dayOf(start, latest.end_date ?? phase.day),
    predicted: [dayOf(start, range.earliest), dayOf(start, range.latest)],
    today: dayOf(start, phase.day),
  }
}

/** 月历上的“预计经期”：从预计开始日起，取平均经期天数（四舍五入）那么多天；没有预测或平均天数时为空 */
export function predictedPeriodDays(prediction: PredictionOut, stats: CycleStatsOut): string[] {
  const start = prediction.status === 'ok' ? prediction.next_period_start : null
  if (!start || stats.avg_period_length === null) return []
  return Array.from({ length: Math.round(stats.avg_period_length) }, (_, i) => addDays(start, i))
}
