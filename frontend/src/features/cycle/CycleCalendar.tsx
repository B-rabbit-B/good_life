// 经期月历（设计稿 06）：React Aria Calendar（周一开头、中文），只在经期这一块按需加载。格高 44、格内 36 圆角 12 的方块（相邻月份补齐整周的格子留空占位：无数字、无标记、不可点、不可聚焦、读屏不可见）：
// 已记录是海军蓝实块，预计是虚线框，预计开始范围在格子下方画虚线，有当天记录的右上一个小点，今天是钴蓝内描边；点中已记录经期里的一天时在方块外再画一圈更粗的钴蓝框；选经期时开始与结束两格是实心钴蓝、中间连成浅钴蓝色带，开始日之前与今天之后的日子变淡。
// 点今天或更早的一天交给经期页处理（月历下的“选中日期”面板；今天以后的日子不可选，但仍能翻到以后的月份看预计）。每格的状态另写在一段只给读屏的说明里（格子的读屏名称由 React Aria 生成）。
import { parseDate } from '@internationalized/date'
import { useState } from 'react'
import {
  Button as AriaButton, Calendar, CalendarCell, CalendarGrid, CalendarGridBody, CalendarGridHeader, CalendarHeaderCell,
  I18nProvider,
} from 'react-aria-components'
import { useDayLogs } from '../../api/hooks/cycle'
import type { PeriodOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { addDays, formatMonthDay } from '../../lib/dates'
import '../../styles/components/cycle.css'
import { calendarCells, gridRange, type Cell } from './calendarCells'

export interface RangePick {
  start: string
  end: string | null
}

/** 选经期时的标记：开始与结束两格实心、中间连成色带；开始日之前与今天之后变淡 */
function pickClass(cell: Cell, today: string, range: RangePick | null): string[] {
  if (!range || !cell.inMonth) return []
  const { start, end } = range
  return [
    cell.date < start || cell.date > today ? 'dim' : '', cell.date === start ? 'ss' : '', cell.date === end ? 'se' : '',
    end && cell.date >= start && cell.date <= end ? 'sb' : '',
  ]
}

function cellClass(cell: Cell | undefined, selected: string | null, today: string, range: RangePick | null): string {
  if (!cell) return 'd'
  return [
    'd', cell.inMonth ? '' : 'out', cell.recorded ? 'rec' : '', cell.predicted ? 'prd' : '', cell.inWindow ? 'win' : '',
    cell.logged ? 'log' : '', cell.today ? 'today' : '', cell.inMonth && cell.date === selected ? 'sel' : '', ...pickClass(cell, today, range),
  ].filter(Boolean).join(' ')
}

/** 连续的日期写成“10月1日至10月3日”，几段之间用顿号 */
function spans(dates: string[]): string {
  const parts: string[] = []
  let start: string | null = null
  let prev: string | null = null
  const flush = () => {
    if (start && prev) parts.push(start === prev ? formatMonthDay(start) : `${formatMonthDay(start)}至${formatMonthDay(prev)}`)
  }
  for (const date of dates) {
    if (prev && addDays(prev, 1) === date) {
      prev = date
      continue
    }
    flush()
    start = date
    prev = date
  }
  flush()
  return parts.join('、')
}

function summary(cells: Cell[]): string {
  const inMonth = cells.filter((cell) => cell.inMonth)
  const pick = (flag: 'recorded' | 'predicted' | 'inWindow' | 'logged') => spans(inMonth.filter((c) => c[flag]).map((c) => c.date))
  return [
    ['已记录经期', pick('recorded')], ['预计经期', pick('predicted')], ['预计开始范围', pick('inWindow')], ['有当天记录', pick('logged')],
  ].filter(([, text]) => text).map(([label, text]) => `${label}：${text}`).join('；') || '这个月没有记录。'
}

export function CycleCalendar({ periods, predictedDays, predictedRange, today, selected, range, onPick }: {
  periods: PeriodOut[]
  predictedDays: string[]
  predictedRange: { earliest: string; latest: string } | null
  today: string
  /** 点中已记录经期里的那一天（不在当前显示的月份时不标） */
  selected: string | null
  /** 正在选经期：开始日与结束日（还没选结束日时为 null）；开始日之前的日子不可点 */
  range: RangePick | null
  /** 点了某一天（不晚于今天） */
  onPick: (date: string) => void
}) {
  const [focused, setFocused] = useState(today)
  const month = focused.slice(0, 7)
  const [start, end] = gridRange(month)
  const logs = useDayLogs(start, end)
  const cells = calendarCells(month, periods, predictedDays, predictedRange, logs.data ?? [], today)
  const byDate = new Map(cells.map((cell) => [cell.date, cell]))
  const [year, monthNumber] = month.split('-').map(Number)
  const todayDate = parseDate(today)

  return (
    <div className="plate cal">
      <I18nProvider locale="zh-CN">
        <Calendar
          aria-label="经期月历"
          value={null}
          onChange={(date) => onPick(date.toString())}
          focusedValue={parseDate(focused)}
          onFocusChange={(date) => setFocused(date.toString())}
          minValue={range ? parseDate(range.start) : undefined}
          isDateUnavailable={(date) => date.compare(todayDate) > 0}
          firstDayOfWeek="mon"
        >
          <div className="cal-h">
            <AriaButton slot="previous" className="ibtn" aria-label="上个月"><Icon name="back" /></AriaButton>
            <b className="ns">{year} 年 {monthNumber} 月</b>
            <AriaButton slot="next" className="ibtn" aria-label="下个月"><Icon name="right" /></AriaButton>
          </div>
          <CalendarGrid className="cal-g" weekdayStyle="narrow">
            <CalendarGridHeader>{(day) => <CalendarHeaderCell>{day}</CalendarHeaderCell>}</CalendarGridHeader>
            <CalendarGridBody>
              {(date) => (
                <CalendarCell date={date} data-date={date.toString()} className={cellClass(byDate.get(date.toString()), selected, today, range)}>
                  {({ isOutsideMonth }) => <span>{isOutsideMonth ? null : date.day}</span>}
                </CalendarCell>
              )}
            </CalendarGridBody>
          </CalendarGrid>
        </Calendar>
      </I18nProvider>
      <p className="sr-only">{summary(cells)}</p>
      <div className="cal-leg" aria-hidden="true">
        <span><i className="l-rec" />已记录经期</span>
        <span><i className="l-prd" />预计经期</span>
        <span><i className="l-win" />预计开始范围</span>
        <span><i className="l-log" />有当天记录</span>
      </div>
    </div>
  )
}
