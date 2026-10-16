// 月历的格子（只做显示换算，不判断任何规则）：周一开头，前后补齐整周（相邻月份的格子只占位，不带任何状态）；当月每格标出已记录的经期（没结束的算到今天）、
// 预计经期（已记录的那天不再标预计）、预计开始范围、有当天记录与今天。日期都是 YYYY-MM-DD 字符串，按字符串比较。
import type { DayLogOut, PeriodOut } from '../../api/types'
import { addDays, addMonths, mondayOf } from '../../lib/dates'

export interface Cell {
  date: string
  inMonth: boolean
  recorded: boolean
  predicted: boolean
  inWindow: boolean
  logged: boolean
  today: boolean
}

/** 月历这一页从哪天到哪天（周一开头、补齐整周）；month 是 YYYY-MM（或这个月里的任何一天） */
export function gridRange(month: string): [string, string] {
  const first = `${month.slice(0, 7)}-01`
  const last = addDays(addMonths(first, 1), -1)
  return [mondayOf(first), addDays(mondayOf(last), 6)]
}

/** month 是 YYYY-MM（或这个月里的任何一天） */
export function calendarCells(
  month: string,
  periods: readonly PeriodOut[],
  predictedDays: readonly string[],
  predictedRange: { earliest: string; latest: string } | null,
  dayLogs: readonly Pick<DayLogOut, 'log_date'>[],
  today: string,
): Cell[] {
  const first = `${month.slice(0, 7)}-01`
  const last = addDays(addMonths(first, 1), -1)
  const [start, end] = gridRange(month)
  const predicted = new Set(predictedDays)
  const logged = new Set(dayLogs.map((log) => log.log_date))
  const cells: Cell[] = []
  for (let date = start; date <= end; date = addDays(date, 1)) {
    if (date < first || date > last) {
      cells.push({ date, inMonth: false, recorded: false, predicted: false, inWindow: false, logged: false, today: false })
      continue
    }
    const recorded = periods.some((p) => date >= p.start_date && date <= (p.end_date ?? today))
    cells.push({
      date,
      inMonth: true,
      recorded,
      predicted: !recorded && predicted.has(date),
      inWindow: predictedRange !== null && date >= predictedRange.earliest && date <= predictedRange.latest,
      logged: logged.has(date),
      today: date === today,
    })
  }
  return cells
}
