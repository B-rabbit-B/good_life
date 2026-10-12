// 日期工具：日期一律是本地日历上的 YYYY-MM-DD 字符串（与后端的 date 字段一致）；时刻是后端的 ISO 时间，按本地时区显示。
// 日期运算用 UTC 的年月日做，避开夏令时与时区。
import type { MealType } from './labels'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const
const pad = (n: number) => String(n).padStart(2, '0')

function parts(iso: string): [number, number, number] {
  const [y = 'NaN', m = 'NaN', d = 'NaN'] = iso.slice(0, 10).split('-')
  return [Number(y), Number(m), Number(d)]
}

const fromUtc = (date: Date) => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
const toUtc = (iso: string) => {
  const [y, m, d] = parts(iso)
  return new Date(Date.UTC(y, m - 1, d))
}
const localISO = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

/** 今天（本地日期） */
export function todayISO(now: Date = new Date()): string {
  return localISO(now)
}

export function addDays(iso: string, n: number): string {
  const date = toUtc(iso)
  date.setUTCDate(date.getUTCDate() + n)
  return fromUtc(date)
}

/** 加 n 个月；目标月没有这一天时落在月末（1月31日加一个月是2月28日或29日） */
export function addMonths(iso: string, n: number): string {
  const [y, m, d] = parts(iso)
  const monthIndex = m - 1 + n
  const lastDay = new Date(Date.UTC(y, monthIndex + 1, 0)).getUTCDate()
  return fromUtc(new Date(Date.UTC(y, monthIndex, Math.min(d, lastDay))))
}

/** 这一周的星期一 */
export function mondayOf(iso: string): string {
  const weekday = toUtc(iso).getUTCDay()
  return addDays(iso, weekday === 0 ? -6 : 1 - weekday)
}

/** “10月12日” */
export function formatMonthDay(iso: string): string {
  const [, m, d] = parts(iso)
  return `${m}月${d}日`
}

/** “周一” */
export function formatWeekday(iso: string): string {
  return WEEKDAYS[toUtc(iso).getUTCDay()] ?? ''
}

/** 本地时间“18:40” */
export function formatTime(isoDateTime: string): string {
  const date = new Date(isoDateTime)
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** “今天 18:40”“昨天 19:02”，更早的是“10月9日”，不在今年的带年份 */
export function dayLabel(isoDateTime: string, now: Date = new Date()): string {
  const date = new Date(isoDateTime)
  const day = localISO(date)
  const today = localISO(now)
  if (day === today) return `今天 ${formatTime(isoDateTime)}`
  if (day === addDays(today, -1)) return `昨天 ${formatTime(isoDateTime)}`
  const monthDay = formatMonthDay(day)
  return date.getFullYear() === now.getFullYear() ? monthDay : `${date.getFullYear()}年${monthDay}`
}

/** “10-12 18:40”（审计与调用记录） */
export function formatStamp(isoDateTime: string): string {
  const date = new Date(isoDateTime)
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${formatTime(isoDateTime)}`
}

/** 手动记一餐的餐次默认值（只是表单默认值）：10 点前早餐、14 点前午餐、17 点前加餐、其余晚餐 */
export function defaultMealType(now: Date): MealType {
  const hour = now.getHours()
  if (hour < 10) return 'breakfast'
  if (hour < 14) return 'lunch'
  if (hour < 17) return 'snack'
  return 'dinner'
}
