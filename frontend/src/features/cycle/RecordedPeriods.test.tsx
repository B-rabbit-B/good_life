import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { addDays, todayISO } from '../../lib/dates'
import { gate } from '../../test/chat'
import { dayLog, deckPeriods, latestStart, period, phase, prediction, stats, tips } from '../../test/fixtures/cycle'
import { cycleHandlers, type CycleOptions } from '../../test/msw/handlers/cycle'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'
import { MAX_LISTED_PERIODS } from './RecordedPeriods'

const today = todayISO()
const full = (iso: string) => iso.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y: string, m: string, d: string) => `${y}年${Number(m)}月${Number(d)}日`)
const WILL = '这次经期记录会被删除，这段时间的预测与统计会重新计算。'
const KEEP = '这次经期当天的每日记录不会被删除。'

function renderCycle(overrides: CycleOptions = {}) {
  const result = renderRoute('/health/cycle')
  const cycle = cycleHandlers({
    periods: deckPeriods(today), prediction: prediction(today), phase: phase(today), tips: tips(today), stats: stats(),
    dayLogs: [dayLog(today)], ...overrides,
  })
  server.use(...cycle.handlers)
  return { ...result, cycle }
}

const panel = async () => (await screen.findByRole('heading', { name: '已记录的经期' })).closest('section') as HTMLElement
const deleteButton = (start: string) => screen.getByRole('button', { name: `删除 ${full(start)} 开始的经期` })

beforeAll(async () => {
  await import('../health/HealthPage')
  await import('./CycleView')
}, 60_000)

describe('recorded periods', { timeout: 15_000 }, () => {
  it('lists the periods from the newest with their dates and length inside the sensitive region', async () => {
    renderCycle()
    const section = await panel()
    expect(section.closest('[data-sensitive]')).not.toBeNull()
    expect(section.querySelector('.plate')).not.toBeNull()
    const s = latestStart(today)
    const rows = within(section).getAllByRole('listitem').map((li) => li.textContent)
    expect(rows).toEqual([
      `${full(s)} 至 ${full(addDays(s, 4))}（共 5 天）删除`,
      `${full(addDays(s, -29))} 至 ${full(addDays(s, -25))}（共 5 天）删除`,
      `${full(addDays(s, -58))} 至 ${full(addDays(s, -54))}（共 5 天）删除`,
      `${full(addDays(s, -88))} 至 ${full(addDays(s, -84))}（共 5 天）删除`,
    ])
    expect(deleteButton(s)).toHaveTextContent('删除')
  })

  it('sorts by start date whatever the backend order and writes an open period as still going', async () => {
    renderCycle({ periods: [period('2026-01-03', '2026-01-05'), period(latestStart(today), null), period('2026-03-01', '2026-03-01')] })
    const section = await panel()
    expect(within(section).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      `${full(latestStart(today))} 至 今（还没结束）删除`,
      '2026年3月1日 至 2026年3月1日（共 1 天）删除',
      '2026年1月3日 至 2026年1月5日（共 3 天）删除',
    ])
  })

  it('shows nothing when there are no periods', async () => {
    renderCycle({ periods: [] })
    await screen.findByRole('grid')
    expect(screen.queryByRole('heading', { name: '已记录的经期' })).not.toBeInTheDocument()
  })

  it('lists at most twelve periods and says the earlier ones are left out', async () => {
    const many = Array.from({ length: MAX_LISTED_PERIODS + 2 }, (_, i) => period(addDays('2025-01-01', i * 30), addDays('2025-01-01', i * 30 + 3)))
    renderCycle({ periods: many })
    const section = await panel()
    expect(within(section).getAllByRole('listitem')).toHaveLength(MAX_LISTED_PERIODS)
    expect(within(section).getByText('只列出最近 12 次，更早的不在这里显示。')).toBeInTheDocument()
    expect(within(section).queryByText(/^2025年1月1日 至/)).not.toBeInTheDocument()
  })

  it('asks before deleting, then deletes, closes the sheet, toasts without a date and refreshes', async () => {
    const user = userEvent.setup()
    const periods = deckPeriods(today)
    const { cycle } = renderCycle({ periods })
    await panel()
    await user.click(deleteButton(latestStart(today)))
    const sheet = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    expect(sheet).toHaveTextContent(WILL)
    expect(sheet).toHaveTextContent(KEEP)
    expect(sheet).not.toHaveTextContent(/\d{4}年/)
    expect(cycle.record.deleted).toEqual([])
    expect(within(sheet).getByRole('button', { name: '取消' })).toBeEnabled()
    await user.click(within(sheet).getByRole('button', { name: '删除这次经期' }))
    await waitFor(() => expect(cycle.record.deleted).toEqual([periods[0]?.id]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const live = document.querySelector('.toast-region') as HTMLElement
    await waitFor(() => expect(live).toHaveTextContent('已删除'))
    expect(live.textContent).not.toMatch(/\d/)
    await waitFor(() => expect(within(document.querySelector('.cyc-list') as HTMLElement).getAllByRole('listitem')).toHaveLength(3))
  })

  it('cancel leaves the period alone', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle()
    await panel()
    await user.click(deleteButton(latestStart(today)))
    const sheet = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    await user.click(within(sheet).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(cycle.record.deleted).toEqual([])
  })

  it('locks the sheet and sends one request while deleting', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { cycle } = renderCycle({ hold: { deletePeriod: held.promise } })
    await panel()
    await user.click(deleteButton(latestStart(today)))
    const sheet = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    await user.dblClick(within(sheet).getByRole('button', { name: '删除这次经期' }))
    await waitFor(() => expect(within(sheet).getByRole('button', { name: '取消' })).toBeDisabled())
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '删除这次经期记录' })).toBeInTheDocument()
    expect(cycle.record.deleted).toHaveLength(1)
    held.open()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(cycle.record.deleted).toHaveLength(1)
  })

  it('shows a failure verbatim, frees the sheet and lets the user retry', async () => {
    const user = userEvent.setup()
    const message = '这条经期记录暂时无法删除'
    const { cycle } = renderCycle({ errors: { deletePeriod: { status: 409, code: 'period_locked', message } } })
    await panel()
    await user.click(deleteButton(latestStart(today)))
    const sheet = await screen.findByRole('dialog', { name: '删除这次经期记录' })
    await user.click(within(sheet).getByRole('button', { name: '删除这次经期' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 period_locked')
    expect(within(sheet).getByRole('button', { name: '取消' })).toBeEnabled()
    expect(within(sheet).getByRole('button', { name: '删除这次经期' })).toBeEnabled()
    expect(screen.getByRole('dialog', { name: '删除这次经期记录' })).toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '删除这次经期' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(cycle.record.deleted).toHaveLength(2)
  })

  it('cannot be reached while the content is covered', async () => {
    const user = userEvent.setup()
    renderCycle()
    const section = await panel()
    await user.click(screen.getByRole('button', { name: '遮盖敏感内容' }))
    const region = section.closest('[data-sensitive]') as HTMLElement
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('button', { name: /^删除 .* 开始的经期$/ })).not.toBeInTheDocument()
    expect(section.closest('[inert]')).not.toBeNull()
  })
})
