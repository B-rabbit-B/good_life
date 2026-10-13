import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { addDays, todayISO } from '../../lib/dates'
import { gate } from '../../test/chat'
import { dayLog, deckPeriods, phase, prediction, stats, tips } from '../../test/fixtures/cycle'
import { cycleHandlers, type CycleOptions } from '../../test/msw/handlers/cycle'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()

function renderCycle(overrides: CycleOptions = {}) {
  const result = renderRoute('/health/cycle')
  const cycle = cycleHandlers({
    periods: deckPeriods(today), prediction: prediction(today), phase: phase(today), tips: tips(today), stats: stats(),
    ...overrides,
  })
  server.use(...cycle.handlers)
  return { ...result, cycle }
}

async function openDayLog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: '记录今天' }))
  return screen.findByRole('dialog', { name: '记录今天' })
}

const options = (group: HTMLElement) => within(group).getAllByRole('radio').map((radio) => radio.closest('label')?.textContent)

beforeAll(async () => {
  await import('../health/HealthPage')
  await import('./CycleView')
}, 60_000)

describe('day log sheet', { timeout: 15_000 }, () => {
  it('offers five flow and five mood options', async () => {
    const user = userEvent.setup()
    renderCycle()
    const sheet = await openDayLog(user)
    expect(options(await within(sheet).findByRole('radiogroup', { name: '流量' }))).toEqual(['无', '点滴', '少', '中', '多'])
    expect(options(within(sheet).getByRole('radiogroup', { name: '心情' }))).toEqual(['好', '一般', '低落', '烦躁', '焦虑'])
    expect(within(sheet).getByLabelText('日期')).toHaveValue(today)
    expect(within(sheet).getByLabelText('日期')).toHaveAttribute('max', today)
    expect(within(sheet).getByLabelText('备注')).toHaveAttribute('maxlength', '500')
  })

  it('puts the log for the chosen date with the request body', async () => {
    const user = userEvent.setup()
    const { cycle } = renderCycle()
    const sheet = await openDayLog(user)
    await user.click(await within(sheet).findByRole('radio', { name: '中' }))
    await user.click(within(sheet).getByRole('radio', { name: '烦躁' }))
    await user.type(within(sheet).getByLabelText('备注'), '下午有点累')
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.putLogs).toEqual([{
      date: today, body: { flow: 'medium', mood: 'irritable', note: '下午有点累', pain: null, symptoms: [] },
    }]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('fills in the saved log and keeps the fields it does not edit', async () => {
    const user = userEvent.setup()
    const yesterday = addDays(today, -1)
    const { cycle } = renderCycle({
      dayLogs: [dayLog(yesterday, { flow: 'light', mood: 'low', pain: 2, symptoms: ['头痛'], note: '睡得晚' })],
    })
    const sheet = await openDayLog(user)
    fireEvent.change(within(sheet).getByLabelText('日期'), { target: { value: yesterday } })
    expect(await within(sheet).findByRole('radio', { name: '少' })).toBeChecked()
    expect(within(sheet).getByRole('radio', { name: '低落' })).toBeChecked()
    expect(within(sheet).getByLabelText('备注')).toHaveValue('睡得晚')
    await user.click(within(sheet).getByRole('radio', { name: '一般' }))
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(cycle.record.putLogs).toEqual([{
      date: yesterday, body: { flow: 'light', mood: 'normal', note: '睡得晚', pain: 2, symptoms: ['头痛'] },
    }]))
  })

  it('shows a backend error verbatim', async () => {
    const user = userEvent.setup()
    renderCycle({ errors: { putDayLog: { status: 422, code: 'log_in_future', message: '不能记录未来日期' } } })
    const sheet = await openDayLog(user)
    await within(sheet).findByRole('radiogroup', { name: '流量' })
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    const alert = await within(sheet).findByRole('alert')
    expect(alert).toHaveTextContent('不能记录未来日期')
    expect(alert).toHaveTextContent('错误码 log_in_future')
  })

  it('locks closing while saving and frees it after a failure', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { cycle } = renderCycle({
      hold: { putDayLog: held.promise }, errors: { putDayLog: { status: 500, code: 'internal_error', message: '服务出了点问题，请稍后再试' } },
    })
    const sheet = await openDayLog(user)
    await within(sheet).findByRole('radiogroup', { name: '流量' })
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await waitFor(() => expect(within(sheet).getByRole('button', { name: '取消' })).toBeDisabled())
    await user.click(within(sheet).getByRole('button', { name: '保存' }))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '记录今天' })).toBeInTheDocument()
    held.open()
    expect(await within(sheet).findByRole('alert')).toHaveTextContent('服务出了点问题，请稍后再试')
    expect(cycle.record.putLogs).toHaveLength(1)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
