import { describe, expect, it } from 'vitest'
import { dayLog, period } from '../../test/fixtures/cycle'
import { calendarCells } from './calendarCells'

// 设计稿 06：2026 年 10 月，1 日是周四；9月29日至10月3日已记录，预计 10月28日起 5 天，预计开始范围 10月26日至30日，
// 2、5、8、10、11 日有当天记录，今天 12 日
const PERIODS = [period('2026-09-29', '2026-10-03')]
const PREDICTED = ['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01']
const RANGE = { earliest: '2026-10-26', latest: '2026-10-30' }
const LOGS = ['02', '05', '08', '10', '11'].map((d) => dayLog(`2026-10-${d}`))
const TODAY = '2026-10-12'

const pick = (cells: ReturnType<typeof calendarCells>, flag: 'recorded' | 'predicted' | 'inWindow' | 'logged' | 'today') =>
  cells.filter((cell) => cell[flag]).map((cell) => cell.date)

describe('calendar cells', () => {
  it('starts october 2026 on monday and pads both ends', () => {
    const cells = calendarCells('2026-10', PERIODS, PREDICTED, RANGE, LOGS, TODAY)
    expect(cells).toHaveLength(35)
    expect(cells[0]?.date).toBe('2026-09-28')
    expect(cells.at(-1)?.date).toBe('2026-11-01')
    expect(cells.filter((cell) => !cell.inMonth).map((cell) => cell.date))
      .toEqual(['2026-09-28', '2026-09-29', '2026-09-30', '2026-11-01'])
  })

  it('needs no padding before a month that starts on monday', () => {
    const cells = calendarCells('2026-06', [], [], null, [], '2026-06-10')
    expect(cells[0]).toMatchObject({ date: '2026-06-01', inMonth: true })
    expect(cells).toHaveLength(35)
    expect(cells.at(-1)?.date).toBe('2026-07-05')
  })

  it('marks recorded, predicted, range, logged days and today', () => {
    const cells = calendarCells('2026-10', PERIODS, PREDICTED, RANGE, LOGS, TODAY)
    expect(pick(cells, 'recorded')).toEqual(['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'])
    expect(pick(cells, 'predicted')).toEqual(PREDICTED)
    expect(pick(cells, 'inWindow')).toEqual(['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'])
    expect(pick(cells, 'logged')).toEqual(['2026-10-02', '2026-10-05', '2026-10-08', '2026-10-10', '2026-10-11'])
    expect(pick(cells, 'today')).toEqual([TODAY])
  })

  it('records an open period through today', () => {
    const cells = calendarCells('2026-10', [period('2026-10-10', null)], [], null, [], TODAY)
    expect(pick(cells, 'recorded')).toEqual(['2026-10-10', '2026-10-11', '2026-10-12'])
  })

  it('does not mark a recorded day as predicted', () => {
    const cells = calendarCells('2026-10', [period('2026-10-27', null)], PREDICTED, RANGE, [], '2026-10-28')
    expect(pick(cells, 'recorded')).toEqual(['2026-10-27', '2026-10-28'])
    expect(pick(cells, 'predicted')).toEqual(['2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01'])
  })
})
