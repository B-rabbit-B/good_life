import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { addDays, formatMonthDay, todayISO } from '../../lib/dates'
import { gate } from '../../test/chat'
import {
  dayLog, deckPeriods, FEW_CYCLES_NOTE, FOLLICULAR_TIP, INSUFFICIENT_DATA_NOTE, insufficientPrediction, latestStart,
  period, phase, PREDICTION_DISCLAIMER, prediction, stats, tips,
} from '../../test/fixtures/cycle'
import { cycleHandlers, type CycleOptions } from '../../test/msw/handlers/cycle'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()

const deck = (overrides: CycleOptions = {}): CycleOptions => ({
  periods: deckPeriods(today), prediction: prediction(today), phase: phase(today), tips: tips(today), stats: stats(),
  dayLogs: [dayLog(today)], ...overrides,
})

function renderCycle(opts: CycleOptions = deck()) {
  const result = renderRoute('/health/cycle')
  const cycle = cycleHandlers(opts)
  server.use(...cycle.handlers)
  return { ...result, cycle }
}

const cellOf = (date: string) => document.querySelector(`[data-date="${date}"]`) as HTMLElement

// 页面是按路由按需加载的大块（经期内容又是健康页里按需加载的一块）：先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
  await import('./CycleView')
}, 60_000)

describe('cycle view', { timeout: 15_000 }, () => {
  it('shows the phase with a reference tag and the backend tip', async () => {
    renderCycle()
    const title = await screen.findByRole('heading', { name: '卵泡期' })
    const block = title.closest('.phase') as HTMLElement
    expect(within(block).getByText('仅供参考')).toHaveClass('ref')
    expect(block).toHaveTextContent('本周期第 14 天。')
    expect(within(block).getByText(FOLLICULAR_TIP.title)).toBeInTheDocument()
    expect(within(block).getByText(FOLLICULAR_TIP.content)).toBeInTheDocument()
  })

  it('shows the prediction range and its disclaimer', async () => {
    renderCycle()
    const next = addDays(latestStart(today), 29)
    const ticks = await screen.findByRole('img', { name: /^周期刻度/ })
    expect(ticks).toHaveAccessibleName('周期刻度：共约 32 天，第 1 到 5 天为经期，今天第 14 天，下次预计在第 28 到 32 天之间开始')
    const pred = document.querySelector('.pred') as HTMLElement
    expect(pred.querySelector('.ns')).toHaveTextContent(formatMonthDay(next))
    expect(pred).toHaveTextContent(`预计下次开始。把握范围 ${formatMonthDay(addDays(next, -2))} 至 ${formatMonthDay(addDays(next, 2))}。`)
    expect(within(pred).getByText('仅供参考')).toBeInTheDocument()
    expect(within(pred).getByText('基于最近 3 个周期，周期长度在 29 到 30 天之间。')).toBeInTheDocument()
    expect(within(pred).getByText(FEW_CYCLES_NOTE)).toBeInTheDocument()
    expect(within(pred).getByText(PREDICTION_DISCLAIMER)).toBeInTheDocument()
  })

  it('shows insufficient data with the backend notes and the cycle count', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle(deck({
      periods: [period(latestStart(today), addDays(latestStart(today), 4)), period(addDays(latestStart(today), -29), addDays(latestStart(today), -25))],
      prediction: insufficientPrediction(),
      stats: stats({ cycle_count: 1 }),
    }))
    const state = (await screen.findByRole('heading', { name: '还不能预测下次经期' })).closest('.state') as HTMLElement
    expect(within(state).getByText(INSUFFICIENT_DATA_NOTE)).toBeInTheDocument()
    expect(within(state).getByText('已记录 1 个完整周期')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /^周期刻度/ })).not.toBeInTheDocument()
    expect(document.querySelector('.pred')).toBeNull()
    await user.click(within(state).getByRole('button', { name: '记录经期开始' }))
    const sheet = await screen.findByRole('dialog', { name: '记录经期开始' })
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: today }]))
  })

  it('keeps the two record buttons outside the sensitive region', async () => {
    const user = userEvent.setup()
    renderCycle()
    const title = await screen.findByRole('heading', { name: '卵泡期' })
    const regions = document.querySelectorAll('[data-sensitive]')
    expect(regions).toHaveLength(1)
    const region = regions[0] as HTMLElement
    expect(region).toContainElement(title)
    expect(region).toContainElement(await screen.findByRole('grid'))
    expect(region).toContainElement(screen.getByRole('img', { name: /^周期刻度/ }))
    const start = screen.getByRole('button', { name: '记录经期开始' })
    const log = screen.getByRole('button', { name: '记录今天' })
    expect(start.closest('[data-sensitive]')).toBeNull()
    expect(log.closest('[data-sensitive]')).toBeNull()
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'cycle', missing: [], unexpected: [] })

    await user.click(screen.getByRole('button', { name: '遮盖敏感内容' }))
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('heading', { name: '卵泡期' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '记录经期' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '记录今天' })).toBeEnabled()
  })

  it('offers ending an open period', async () => {
    const user = userEvent.setup()
    const periods = deckPeriods(today, { open: true })
    const { cycle } = renderCycle(deck({ periods }))
    await user.click(await screen.findByRole('button', { name: '记录经期结束' }))
    expect(screen.queryByRole('button', { name: '记录经期开始' })).not.toBeInTheDocument()
    const sheet = await screen.findByRole('dialog', { name: '记录经期结束' })
    expect(within(sheet).getByLabelText('结束日期')).toHaveValue(today)
    expect(within(sheet).getByLabelText('结束日期')).toHaveAttribute('max', today)
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.updated).toEqual([{ id: periods[0]?.id, body: { end_date: today } }]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByRole('button', { name: '记录经期开始' })).toBeInTheDocument()
  })

  it('keeps the period button neutral while covered', async () => {
    const user = userEvent.setup()
    renderCycle(deck({ periods: deckPeriods(today, { open: true }) }))
    expect(await screen.findByRole('button', { name: '记录经期结束' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '遮盖敏感内容' }))
    expect(screen.getByRole('button', { name: '记录经期' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '记录今天' })).toBeInTheDocument()
    const covered = Array.from(document.querySelectorAll('button'))
      .filter((button) => !button.closest('[data-sensitive]') && !button.closest('.top') && !button.closest('nav'))
      .map((button) => button.textContent)
    expect(covered).toEqual(['记录经期', '记录今天'])
    await user.click(screen.getByRole('button', { name: '记录经期' }))
    expect(await screen.findByRole('dialog', { name: '记录经期结束' })).toBeInTheDocument()
  })

  it('shows a period error verbatim and keeps the sheet open', async () => {
    const user = userEvent.setup()
    const message = '与已有的经期记录日期重叠'
    renderCycle(deck({ errors: { createPeriod: { status: 409, code: 'period_overlap', message } } }))
    await user.click(await screen.findByRole('button', { name: '记录经期开始' }))
    const sheet = await screen.findByRole('dialog', { name: '记录经期开始' })
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 period_overlap')
    expect(screen.getByRole('dialog', { name: '记录经期开始' })).toBeInTheDocument()
  })

  it('locks the period sheet while saving and frees it after a network error', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { cycle } = renderCycle(deck({ hold: { createPeriod: held.promise }, networkFail: { createPeriod: true } }))
    await user.click(await screen.findByRole('button', { name: '记录经期开始' }))
    const sheet = await screen.findByRole('dialog', { name: '记录经期开始' })
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(within(sheet).getByRole('button', { name: '取消' })).toBeDisabled())
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '记录经期开始' })).toBeInTheDocument()
    held.open()
    expect(await within(sheet).findByRole('alert')).toHaveTextContent('网络连接失败，请检查网络后重试')
    expect(cycle.record.created).toHaveLength(1)
    const cancel = within(sheet).getByRole('button', { name: '取消' })
    expect(cancel).toBeEnabled()
    await user.click(cancel)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('marks the calendar days and opens a day log from a cell', async () => {
    const user = userEvent.setup()
    renderCycle(deck({ periods: [period(today, null)], dayLogs: [dayLog(today)] }))
    const grid = await screen.findByRole('grid')
    expect(grid.querySelectorAll('thead th')).toHaveLength(7)
    expect(Array.from(grid.querySelectorAll('thead th')).map((th) => th.textContent)).toEqual(['一', '二', '三', '四', '五', '六', '日'])
    await waitFor(() => expect(cellOf(today)).toHaveClass('d', 'rec', 'today', 'log'))
    expect(screen.getByText('已记录经期')).toBeInTheDocument()
    expect(screen.getByText('预计经期')).toBeInTheDocument()
    expect(screen.getByText('预计开始范围')).toBeInTheDocument()
    expect(screen.getByText('有当天记录')).toBeInTheDocument()
    await user.click(cellOf(today))
    expect(await screen.findByRole('dialog', { name: '记录今天' })).toBeInTheDocument()
  })

  it('uses no pink colour tokens', async () => {
    renderCycle()
    await screen.findByRole('img', { name: /^周期刻度/ })
    await screen.findByRole('grid')
    for (const el of Array.from(document.body.querySelectorAll('*'))) {
      expect(el.getAttribute('class') ?? '').not.toMatch(/pink|danger/)
      expect(el.getAttribute('style') ?? '').not.toMatch(/--danger|pink/)
    }
  })
})
