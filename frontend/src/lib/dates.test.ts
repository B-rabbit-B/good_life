import { describe, expect, it } from 'vitest'
import {
  addDays, addMonths, dayLabel, defaultMealType, formatMonthDay, formatStamp, formatTime, formatWeekday, mondayOf, todayISO,
} from './dates'

// 本地时间的时刻（测试不依赖运行机器的时区）
const at = (y: number, m: number, d: number, hh = 0, mm = 0) => new Date(y, m - 1, d, hh, mm)
const iso = (date: Date) => date.toISOString()

describe('dates', () => {
  it('gives today as a local date', () => {
    expect(todayISO(at(2026, 10, 12, 0, 5))).toBe('2026-10-12')
    expect(todayISO(at(2026, 1, 3, 23, 59))).toBe('2026-01-03')
  })

  it('adds days across months and leap days', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29')
    expect(addDays('2026-02-28', 1)).toBe('2026-03-01')
  })

  it('adds months and clamps to the month end', () => {
    expect(addMonths('2026-10-12', 1)).toBe('2026-11-12')
    expect(addMonths('2026-10-12', 3)).toBe('2027-01-12')
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-28')
    expect(addMonths('2028-01-31', 1)).toBe('2028-02-29')
    expect(addMonths('2026-03-31', -1)).toBe('2026-02-28')
  })

  it('finds the monday of a week', () => {
    expect(mondayOf('2026-10-12')).toBe('2026-10-12')
    expect(mondayOf('2026-10-18')).toBe('2026-10-12')
    expect(mondayOf('2026-11-01')).toBe('2026-10-26')
  })

  it('formats month and day', () => {
    expect(formatMonthDay('2026-10-12')).toBe('10月12日')
    expect(formatMonthDay('2026-01-05')).toBe('1月5日')
  })

  it('formats the weekday', () => {
    expect(formatWeekday('2026-10-12')).toBe('周一')
    expect(formatWeekday('2026-10-18')).toBe('周日')
  })

  it('formats a local time', () => {
    expect(formatTime(iso(at(2026, 10, 12, 18, 40)))).toBe('18:40')
    expect(formatTime(iso(at(2026, 10, 12, 7, 5)))).toBe('07:05')
  })

  it('labels a moment relative to now', () => {
    const now = at(2026, 10, 12, 20, 0)
    expect(dayLabel(iso(at(2026, 10, 12, 18, 40)), now)).toBe('今天 18:40')
    expect(dayLabel(iso(at(2026, 10, 11, 19, 2)), now)).toBe('昨天 19:02')
    expect(dayLabel(iso(at(2026, 10, 9, 8, 0)), now)).toBe('10月9日')
    expect(dayLabel(iso(at(2026, 11, 30, 23, 0)), at(2026, 12, 1, 9, 0))).toBe('昨天 23:00')
    expect(dayLabel(iso(at(2025, 10, 9, 8, 0)), now)).toBe('2025年10月9日')
  })

  it('formats a short stamp', () => {
    expect(formatStamp(iso(at(2026, 10, 12, 18, 40)))).toBe('10-12 18:40')
    expect(formatStamp(iso(at(2026, 1, 3, 9, 7)))).toBe('01-03 09:07')
  })

  it('suggests a meal type by the hour', () => {
    expect(defaultMealType(at(2026, 10, 12, 7, 30))).toBe('breakfast')
    expect(defaultMealType(at(2026, 10, 12, 10, 0))).toBe('lunch')
    expect(defaultMealType(at(2026, 10, 12, 13, 59))).toBe('lunch')
    expect(defaultMealType(at(2026, 10, 12, 15, 0))).toBe('snack')
    expect(defaultMealType(at(2026, 10, 12, 17, 0))).toBe('dinner')
    expect(defaultMealType(at(2026, 10, 12, 23, 30))).toBe('dinner')
  })
})
