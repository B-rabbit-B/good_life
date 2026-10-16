import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { MAX_PERIOD_DAYS } from '../../lib/contract'
import { addDays, todayISO } from '../../lib/dates'
import { gate } from '../../test/chat'
import { deckPeriods, phase, prediction, stats, tips } from '../../test/fixtures/cycle'
import { cycleHandlers, type CycleOptions } from '../../test/msw/handlers/cycle'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()
const HINT = '补记以前的经期，请同时填写结束日期'
const END = '结束日期（还没结束可以留空）'

function renderCycle(overrides: CycleOptions = {}) {
  const result = renderRoute('/health/cycle')
  const cycle = cycleHandlers({
    periods: deckPeriods(today), prediction: prediction(today), phase: phase(today), tips: tips(today), stats: stats(),
    ...overrides,
  })
  server.use(...cycle.handlers)
  return { ...result, cycle }
}

async function openStart(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: '记录经期开始' }))
  return screen.findByRole('dialog', { name: '记录经期开始' })
}

const setDate = (sheet: HTMLElement, label: string, value: string) =>
  fireEvent.change(within(sheet).getByLabelText(label), { target: { value } })

beforeAll(async () => {
  await import('../health/HealthPage')
  await import('./CycleView')
}, 60_000)

describe('period sheet', { timeout: 15_000 }, () => {
  it('asks for a start date and an optional end date inside the sensitive region', async () => {
    const user = userEvent.setup()
    renderCycle({ periods: [] })
    const sheet = await openStart(user)
    const start = within(sheet).getByLabelText('开始日期')
    const end = within(sheet).getByLabelText(END)
    expect(start).toHaveValue(today)
    expect(start).toHaveAttribute('max', today)
    expect(end).toHaveValue('')
    expect(end).toHaveAttribute('max', today)
    expect(end).toHaveAttribute('min', today)
    setDate(sheet, '开始日期', addDays(today, -3))
    expect(end).toHaveAttribute('min', addDays(today, -3))
    expect(start.closest('[data-sensitive]')).not.toBeNull()
    expect(end.closest('[data-sensitive]')).not.toBeNull()
    expect(within(sheet).getByRole('button', { name: '保存' }).closest('[data-sensitive]')).toBeNull()
  })

  it('sends no end date when it is left empty', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle({ periods: [] })
    const sheet = await openStart(user)
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: today }]))
  })

  it('sends the end date when it is filled in', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle({ periods: [] })
    const sheet = await openStart(user)
    setDate(sheet, '开始日期', addDays(today, -20))
    setDate(sheet, END, addDays(today, -15))
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: addDays(today, -20), end_date: addDays(today, -15) }]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('does not send an end date that was cleared again', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle({ periods: [] })
    const sheet = await openStart(user)
    setDate(sheet, END, today)
    setDate(sheet, END, '')
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: today }]))
  })

  it('hints to fill the end date for a start 15 days or more ago, without blocking', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle({ periods: [] })
    const sheet = await openStart(user)
    setDate(sheet, '开始日期', addDays(today, -(MAX_PERIOD_DAYS - 2)))
    expect(within(sheet).queryByText(HINT)).not.toBeInTheDocument()
    setDate(sheet, '开始日期', addDays(today, -MAX_PERIOD_DAYS))
    expect(within(sheet).getByText(HINT)).toBeInTheDocument()
    expect(within(sheet).queryByRole('alert')).not.toBeInTheDocument()
    setDate(sheet, END, addDays(today, -10))
    expect(within(sheet).queryByText(HINT)).not.toBeInTheDocument()
    setDate(sheet, END, '')
    expect(within(sheet).getByText(HINT)).toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toEqual([{ start_date: addDays(today, -MAX_PERIOD_DAYS) }]))
  })

  it('shows period_too_long verbatim with its code and frees the save button', async () => {
    const user = userEvent.setup()
    const message = '这次经期已超过 15 天还没有填写结束日期，请补全结束日期'
    const { cycle } = renderCycle({
      periods: [], errors: { createPeriod: { status: 422, code: 'period_too_long', message } },
    })
    const sheet = await openStart(user)
    setDate(sheet, '开始日期', addDays(today, -19))
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 period_too_long')
    await waitFor(() => expect(within(sheet).getByRole('button', { name: '保存' })).toBeEnabled())
    setDate(sheet, END, addDays(today, -15))
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.created).toHaveLength(2))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('shows a field error under the end date', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle({
      periods: [], errors: { createPeriod: {
        status: 422, code: 'validation_error', message: '请求参数有误',
        details: [{ field: 'end_date', message: '结束日期不能早于开始日期' }],
      } },
    })
    const sheet = await openStart(user)
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    const end = within(sheet).getByLabelText(END)
    await waitFor(() => expect(end).toHaveAttribute('aria-invalid', 'true'))
    expect(within(sheet).getByText('结束日期不能早于开始日期')).toBeInTheDocument()
    expect(within(sheet).getByLabelText('开始日期')).not.toHaveAttribute('aria-invalid')
    expect(cycle.record.created).toHaveLength(1)
  })

  it('keeps both dates read-only while saving', async () => {
    const user = userEvent.setup()
    const held = gate()
    renderCycle({ periods: [], hold: { createPeriod: held.promise } })
    const sheet = await openStart(user)
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(within(sheet).getByLabelText('开始日期')).toHaveAttribute('readonly'))
    expect(within(sheet).getByLabelText(END)).toHaveAttribute('readonly')
    held.open()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('keeps the end mode to a single end date field without the hint', async () => {
    const user = userEvent.setup()
    renderCycle({ periods: deckPeriods(today, { open: true }) })
    await user.click(await screen.findByRole('button', { name: '记录经期结束' }))
    const sheet = await screen.findByRole('dialog', { name: '记录经期结束' })
    expect(within(sheet).getAllByLabelText(/日期/)).toHaveLength(1)
    expect(within(sheet).getByLabelText('结束日期')).toHaveValue(today)
    expect(within(sheet).queryByText(HINT)).not.toBeInTheDocument()
  })
})
