import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { addDays, formatFullDate, formatMonthDay, todayISO } from '../../lib/dates'
import { gate } from '../../test/chat'
import { dayLog, deckPeriods, latestStart, period, phase, prediction, stats, tips } from '../../test/fixtures/cycle'
import { cycleHandlers, type CycleOptions } from '../../test/msw/handlers/cycle'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

type User = ReturnType<typeof userEvent.setup>

const today = todayISO()
const START_ASK = '再点一个日期作为结束日，只能点这天之后的日子。'

function renderCycle(overrides: CycleOptions = {}) {
  const result = renderRoute('/health/cycle')
  const cycle = cycleHandlers({
    periods: deckPeriods(today), prediction: prediction(today), phase: phase(today), tips: tips(today), stats: stats(),
    dayLogs: [dayLog(today)], ...overrides,
  })
  server.use(...cycle.handlers)
  return { ...result, cycle }
}

const cellOf = (date: string) => document.querySelector<HTMLElement>(`.cal-g .d:not(.out)[data-date="${date}"]`)
const panel = () => screen.queryByRole('region', { name: '选中日期' })
const inPanel = () => within(panel() as HTMLElement)
const statusTexts = () => screen.getAllByRole('status').map((s) => s.textContent ?? '')
const shownMonth = () => {
  const [y = 0, m = 0] = (document.querySelector('.cal-h b')?.textContent ?? '').match(/\d+/g)?.map(Number) ?? []
  return y * 12 + m
}

/** 点某一天：先把月历翻到那个月 */
async function pick(user: User, date: string) {
  await screen.findByRole('grid')
  const [y = 0, m = 0] = date.split('-').map(Number)
  for (let i = 0; i < 6 && !cellOf(date); i += 1) {
    await user.click(screen.getByRole('button', { name: shownMonth() > y * 12 + m ? '上个月' : '下个月' }))
  }
  await user.click(cellOf(date) as HTMLElement)
}

beforeAll(async () => {
  await import('../health/HealthPage')
  await import('./CycleView')
}, 60_000)

describe('picking a period on the calendar', { timeout: 20_000 }, () => {
  it('starts a selection on a plain day: panel under the calendar, no day log, date-free announcement', async () => {
    const user = userEvent.setup()
    renderCycle()
    expect(panel()).toBeNull()
    await pick(user, today)
    const box = panel() as HTMLElement
    expect(box).toHaveClass('plate')
    expect(box.closest('[data-sensitive]')).not.toBeNull()
    expect(box).toHaveTextContent(`经期从 ${formatMonthDay(today)} 开始。${START_ASK}`)
    expect(inPanel().getByRole('button', { name: '还没结束，只记开始' })).toBeInTheDocument()
    expect(inPanel().getByRole('button', { name: '取消' })).toBeInTheDocument()
    expect(inPanel().getByRole('button', { name: '只记录这一天的流量、心情、备注' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(statusTexts()).toContain('已选择开始日，请再选结束日')
    expect(statusTexts().join('')).not.toMatch(/\d/)
    const calendar = document.querySelector('.cal') as HTMLElement
    const list = (await screen.findByRole('heading', { name: '已记录的经期' })).closest('section') as HTMLElement
    expect(calendar.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(box.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(cellOf(today)).toHaveClass('ss')
  })

  it('makes the days before the start and after today unpickable and keeps the later days pickable', async () => {
    const user = userEvent.setup()
    renderCycle()
    const start = addDays(today, -3)
    await pick(user, start)
    const before = cellOf(addDays(start, -1)) as HTMLElement
    expect(before).toHaveClass('dim')
    expect(before).toHaveAttribute('aria-disabled', 'true')
    expect(before).not.toHaveAttribute('tabindex')
    await user.click(before)
    expect(panel()).toHaveTextContent(`经期从 ${formatMonthDay(start)} 开始`)
    expect(cellOf(start)).not.toHaveClass('dim')
    expect(cellOf(addDays(start, 1))).not.toHaveAttribute('aria-disabled', 'true')
    expect(cellOf(today)).not.toHaveClass('dim')
    await user.click(screen.getByRole('button', { name: '下个月' }))
    const future = document.querySelector('.cal-g .d:not(.out)') as HTMLElement
    expect(future).toHaveClass('dim')
    expect(future).toHaveAttribute('aria-disabled', 'true')
  })

  it('saves only the start without an end date', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle()
    await pick(user, today)
    await user.click(inPanel().getByRole('button', { name: '还没结束，只记开始' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: today }]))
    expect(await screen.findByText('已记下')).toBeInTheDocument()
    await waitFor(() => expect(panel()).toBeNull())
    await waitFor(() => expect(cellOf(today)).toHaveClass('rec'))
    expect(cellOf(today)).not.toHaveClass('ss')
  })

  it('shades the days from the start to the chosen end and saves both dates', async () => {
    const user = userEvent.setup()
    const start = addDays(today, -4)
    const end = addDays(today, -1)
    const { cycle } = renderCycle()
    await pick(user, start)
    await pick(user, end)
    expect(panel()).toHaveTextContent(`${formatMonthDay(start)} 至 ${formatMonthDay(end)}，共 4 天`)
    expect(statusTexts().join('')).not.toMatch(/\d/)
    for (const date of [start, addDays(start, 1), addDays(start, 2), end]) {
      expect(cellOf(date), date).toHaveClass('sb')
    }
    expect(cellOf(start)).toHaveClass('ss')
    expect(cellOf(end)).toHaveClass('se')
    expect(cellOf(addDays(start, 1))).not.toHaveClass('ss', 'se')
    expect(cellOf(today)).not.toHaveClass('sb')
    await user.click(inPanel().getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: start, end_date: end }]))
    expect(await screen.findByText('已记下')).toBeInTheDocument()
    await waitFor(() => expect(panel()).toBeNull())
    expect(document.querySelectorAll('.cal-g .sb')).toHaveLength(0)
    await waitFor(() => expect(cellOf(end)).toHaveClass('rec'))
  })

  it('keeps the band across a month boundary', async () => {
    const user = userEvent.setup()
    const first = `${today.slice(0, 7)}-01`
    const start = addDays(first, -2)
    renderCycle({ periods: [] })
    await pick(user, start)
    await pick(user, today)
    const inBand = (dates: string[]) => dates.map((d) => cellOf(d)?.classList.contains('sb'))
    expect(inBand([first, today])).toEqual([true, true])
    await user.click(screen.getByRole('button', { name: '上个月' }))
    expect(inBand([start, addDays(start, 1)])).toEqual([true, true])
    expect(cellOf(addDays(start, -1))).not.toHaveClass('sb')
  })

  it('takes a second tap on the start as a single day', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle()
    await pick(user, today)
    await user.click(cellOf(today) as HTMLElement)
    expect(panel()).toHaveTextContent(`${formatMonthDay(today)} 至 ${formatMonthDay(today)}，共 1 天`)
    await user.click(inPanel().getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: today, end_date: today }]))
  })

  it('lets the end day be changed before saving and starts over with the choose-again button', async () => {
    const user = userEvent.setup()
    const start = addDays(today, -3)
    renderCycle()
    await pick(user, start)
    await pick(user, addDays(start, 2))
    await pick(user, addDays(start, 1))
    expect(panel()).toHaveTextContent(`${formatMonthDay(start)} 至 ${formatMonthDay(addDays(start, 1))}，共 2 天`)
    expect(cellOf(addDays(start, 2))).not.toHaveClass('sb')
    await user.click(inPanel().getByRole('button', { name: '重新选择' }))
    expect(panel()).toBeNull()
    expect(document.querySelectorAll('.cal-g .sb, .cal-g .ss')).toHaveLength(0)
    expect(cellOf(addDays(start, -1))).not.toHaveClass('dim')
    await pick(user, addDays(start, -1))
    expect(panel()).toHaveTextContent(`经期从 ${formatMonthDay(addDays(start, -1))} 开始`)
  })

  it('cancels with the button and with Escape', async () => {
    const user = userEvent.setup()
    renderCycle()
    await pick(user, today)
    await user.click(inPanel().getByRole('button', { name: '取消' }))
    expect(panel()).toBeNull()
    expect(cellOf(today)).not.toHaveClass('ss')
    await pick(user, today)
    expect(panel()).not.toBeNull()
    await user.keyboard('{Escape}')
    expect(panel()).toBeNull()
  })

  it('selects with Enter on a focused day', async () => {
    const user = userEvent.setup()
    renderCycle()
    await screen.findByRole('grid')
    ;(cellOf(today) as HTMLElement).focus()
    await user.keyboard('{Enter}')
    expect(panel()).toHaveTextContent(`经期从 ${formatMonthDay(today)} 开始`)
  })

  it('shows a day inside a recorded period with a delete button that asks first', async () => {
    const user = userEvent.setup()
    const periods = deckPeriods(today)
    const start = latestStart(today)
    const { cycle } = renderCycle({ periods })
    await pick(user, addDays(start, 2))
    expect(panel()).toHaveTextContent(`这一天在 ${formatFullDate(start)} 至 ${formatFullDate(addDays(start, 4))} 的经期内`)
    expect(inPanel().queryByRole('button', { name: '还没结束，只记开始' })).not.toBeInTheDocument()
    expect(inPanel().getByRole('button', { name: '只记录这一天的流量、心情、备注' })).toBeInTheDocument()
    expect(document.querySelectorAll('.cal-g .dim:not(.out)')).toHaveLength(0)
    await user.click(inPanel().getByRole('button', { name: '删除这次经期' }))
    const sheet = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    expect(cycle.record.deleted).toEqual([])
    await user.click(within(sheet).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(cycle.record.deleted).toEqual([])
    expect(panel()).not.toBeNull()

    await user.click(inPanel().getByRole('button', { name: '删除这次经期' }))
    const again = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    await user.click(within(again).getByRole('button', { name: '删除这次经期' }))
    await waitFor(() => expect(cycle.record.deleted).toEqual([periods[0]?.id]))
    expect(await screen.findByText('已删除')).toBeInTheDocument()
    await waitFor(() => expect(panel()).toBeNull())
    await waitFor(() => expect(cellOf(addDays(start, 2))).not.toHaveClass('rec'))
  })

  it('writes an open period as still going and collapses', async () => {
    const user = userEvent.setup()
    const start = latestStart(today)
    renderCycle({ periods: [period(start, null)] })
    await pick(user, addDays(start, 1))
    expect(panel()).toHaveTextContent(`这一天在 ${formatFullDate(start)} 至 今（还没结束） 的经期内`)
    await user.click(inPanel().getByRole('button', { name: '收起' }))
    expect(panel()).toBeNull()
  })

  it('opens the day log for the picked day from either panel', async () => {
    const user = userEvent.setup()
    renderCycle()
    await pick(user, today)
    await user.click(inPanel().getByRole('button', { name: '只记录这一天的流量、心情、备注' }))
    expect(await screen.findByRole('dialog', { name: '记录今天' })).toBeInTheDocument()
    expect(screen.getByLabelText('日期')).toHaveValue(today)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    await user.click(inPanel().getByRole('button', { name: '取消' }))
    const inside = addDays(latestStart(today), 1)
    await pick(user, inside)
    await user.click(inPanel().getByRole('button', { name: '只记录这一天的流量、心情、备注' }))
    expect(await screen.findByRole('dialog', { name: `记录 ${formatMonthDay(inside)}` })).toBeInTheDocument()
  })

  it('shows a save error verbatim, keeps the selection and allows a retry', async () => {
    const user = userEvent.setup()
    const message = '与已有的经期记录日期重叠'
    const start = addDays(today, -3)
    const end = addDays(today, -2)
    const { cycle } = renderCycle({ errors: { createPeriod: { status: 409, code: 'period_overlap', message } } })
    await pick(user, start)
    await pick(user, end)
    await user.click(inPanel().getByRole('button', { name: '保存' }))
    const alert = await inPanel().findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 period_overlap')
    expect(cellOf(start)).toHaveClass('ss')
    expect(cellOf(end)).toHaveClass('se')
    expect(inPanel().getByRole('button', { name: '保存' })).toBeEnabled()
    await user.click(inPanel().getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toHaveLength(2))
    await waitFor(() => expect(panel()).toBeNull())
  })

  it('locks the panel while saving and takes one request for a double press', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { cycle } = renderCycle({ hold: { createPeriod: held.promise } })
    await pick(user, today)
    const save = inPanel().getByRole('button', { name: '还没结束，只记开始' })
    await user.click(save)
    await user.click(save)
    await waitFor(() => expect(inPanel().getByRole('button', { name: '取消' })).toBeDisabled())
    expect(inPanel().getByRole('button', { name: '只记录这一天的流量、心情、备注' })).toBeDisabled()
    held.open()
    await waitFor(() => expect(cycle.record.created).toHaveLength(1))
    await waitFor(() => expect(panel()).toBeNull())
  })

  it('does not start on a later day', async () => {
    const user = userEvent.setup()
    renderCycle()
    await screen.findByRole('grid')
    await user.click(screen.getByRole('button', { name: '下个月' }))
    const future = document.querySelector('.cal-g .d:not(.out)') as HTMLElement
    expect(future).toHaveAttribute('aria-disabled', 'true')
    await user.click(future)
    expect(panel()).toBeNull()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('covers the panel and the calendar selection and stops announcing', async () => {
    const user = userEvent.setup()
    renderCycle()
    await pick(user, today)
    const region = (panel() as HTMLElement).closest('[data-sensitive]')
    await user.click(screen.getByRole('button', { name: '遮盖敏感内容' }))
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(region).toHaveAttribute('data-covered')
    expect(screen.queryByRole('region', { name: '选中日期' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '取消' })).not.toBeInTheDocument()
    expect(screen.queryByRole('grid')).not.toBeInTheDocument()
    expect(statusTexts().join('')).not.toContain('已选择')
  })
})
