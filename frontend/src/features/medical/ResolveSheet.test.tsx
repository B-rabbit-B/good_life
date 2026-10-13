import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { formatMonthDay, todayISO } from '../../lib/dates'
import {
  activeItem, dueItem, order, proposalItem, proposedEvent, REVIEW_REASON, reviewDueEvent,
} from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'
import { gate } from '../../test/chat'

function renderActive(opts: MedicalOptions) {
  const result = renderRoute('/health/medical?tab=active')
  const medical = medicalHandlers({ orders: [order()], ...opts })
  server.use(...medical.handlers)
  return { ...result, medical }
}

const rowOf = async (content: string) => (await screen.findByText(content, { selector: '.mo-c' })).closest('.mo') as HTMLElement

async function openResolve(user: ReturnType<typeof userEvent.setup>, content: string) {
  await user.click(within(await rowOf(content)).getByRole('button', { name: '确认解除' }))
  return screen.findByRole('dialog', { name: '确认解除这条医嘱' })
}

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
}, 60_000)

describe('resolve sheet', { timeout: 15_000 }, () => {
  it('requires the acknowledgement before resolving', async () => {
    const user = userEvent.setup()
    const item = activeItem()
    const { medical } = renderActive({ items: [item] })
    const sheet = await openResolve(user, item.content)
    const quote = sheet.querySelector('.quote') as HTMLElement
    expect(within(quote).getByText('饮食禁忌')).toBeInTheDocument()
    expect(within(quote).getByText(item.content)).toBeInTheDocument()
    expect(within(quote).getByText('来源：2026-10-11 出院小结.jpg')).toBeInTheDocument()
    expect(Array.from(sheet.querySelectorAll('.will li')).map((li) => [li.textContent, li.className])).toEqual([
      ['这条医嘱从“生效中”变为“已解除”。', ''],
      ['之后的训练与饮食建议不再按它约束。', ''],
      ['记一条审计：时间、由你本人确认。', ''],
      ['解除不能撤销。以后需要时，请重新录入。', 'irrev'],
    ])
    const confirm = within(sheet).getByRole('button', { name: '确认解除' })
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    expect(medical.resolves).toEqual([])
    await user.click(within(sheet).getByRole('checkbox', { name: '我知道解除后不能撤销，需要重新录入才能恢复这条约束' }))
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    await waitFor(() => expect(medical.resolves).toEqual([{ id: item.id, body: '' }]))
  })

  it('switches the secondary button by item state', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const proposal = proposalItem()
    const plain = activeItem()
    const { medical } = renderActive({
      items: [due, proposal, plain],
      events: { [due.id]: [reviewDueEvent()], [proposal.id]: [proposedEvent('agent')] },
    })

    // 待复核：次按钮是“继续遵守”，关闭解除面板、打开继续遵守面板
    let sheet = await openResolve(user, due.content)
    expect(within(sheet).getByText('这条医嘱从“待复核”变为“已解除”。')).toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    const continueSheet = await screen.findByRole('dialog', { name: '继续遵守这条医嘱' })
    expect(within(continueSheet).getByText(REVIEW_REASON)).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '确认解除这条医嘱' })).not.toBeInTheDocument()
    await user.click(within(continueSheet).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    // 带解除建议：次按钮撤销这条建议
    const day = formatMonthDay(todayISO(new Date(proposal.resolution_proposed_at ?? '')))
    sheet = await openResolve(user, proposal.content)
    expect(within(sheet).getByText(`记一条审计：时间、由你本人确认，依据是 ${day} 的解除建议。`)).toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '不解除，撤销这条建议' }))
    await waitFor(() => expect(medical.cancels).toEqual([proposal.id]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    // 没有建议：次按钮只关闭
    sheet = await openResolve(user, plain.content)
    await user.click(within(sheet).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.resolves).toEqual([])
    expect(medical.continues).toEqual([])
    expect(medical.cancels).toEqual([proposal.id])
  })

  it('blocks the secondary button and closing while resolving', async () => {
    const user = userEvent.setup()
    const item = proposalItem()
    const held = gate()
    const { medical } = renderActive({ items: [item], events: { [item.id]: [proposedEvent('agent')] }, hold: { resolve: held.promise } })
    const sheet = await openResolve(user, item.content)
    await user.click(within(sheet).getByRole('checkbox'))
    await user.click(within(sheet).getByRole('button', { name: '确认解除' }))
    await waitFor(() => expect(medical.resolves).toHaveLength(1))
    // 解除请求挂着：次按钮停用，按了也不发撤销建议；Esc 不关面板
    const keep = within(sheet).getByRole('button', { name: '不解除，撤销这条建议' })
    expect(keep).toBeDisabled()
    await user.click(keep)
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '确认解除这条医嘱' })).toBeInTheDocument()
    expect(medical.cancels).toEqual([])
    held.open()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.resolves).toHaveLength(1)
    expect(medical.cancels).toEqual([])
  })

  it('blocks resolving and closing while the proposal is being withdrawn', async () => {
    const user = userEvent.setup()
    const item = proposalItem()
    const held = gate()
    const { medical } = renderActive({ items: [item], events: { [item.id]: [proposedEvent('agent')] }, hold: { cancel: held.promise } })
    const sheet = await openResolve(user, item.content)
    await user.click(within(sheet).getByRole('checkbox'))
    await user.click(within(sheet).getByRole('button', { name: '不解除，撤销这条建议' }))
    await waitFor(() => expect(medical.cancels).toHaveLength(1))
    const confirm = within(sheet).getByRole('button', { name: '确认解除' })
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: '确认解除这条医嘱' })).toBeInTheDocument()
    held.open()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.resolves).toEqual([])
    expect(medical.cancels).toHaveLength(1)
  })

  it('starts unticked every time the sheet opens', async () => {
    const user = userEvent.setup()
    const item = activeItem()
    renderActive({ items: [item] })
    let sheet = await openResolve(user, item.content)
    await user.click(within(sheet).getByRole('checkbox'))
    expect(within(sheet).getByRole('checkbox')).toBeChecked()
    await user.click(within(sheet).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    sheet = await openResolve(user, item.content)
    expect(within(sheet).getByRole('checkbox')).not.toBeChecked()
    expect(within(sheet).getByRole('button', { name: '确认解除' })).toBeDisabled()
  })

  it('keeps the content out of the result line while covered', async () => {
    const user = userEvent.setup()
    const item = activeItem()
    const held = gate()
    renderActive({ items: [item], hold: { resolve: held.promise } })
    const sheet = await openResolve(user, item.content)
    await user.click(within(sheet).getByRole('checkbox'))
    await user.click(within(sheet).getByRole('button', { name: '确认解除' }))
    // 切到后台再回来时默认遮盖（面板开着时用户点不到遮盖按钮）
    act(() => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
      document.dispatchEvent(new Event('visibilitychange'))
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    held.open()
    const live = sheet.querySelector('[aria-live="assertive"]') as HTMLElement
    await waitFor(() => expect(live).toHaveTextContent('已解除这条医嘱。审计已记录。'))
    expect(live).not.toHaveTextContent(item.content)
  })

  it('announces the result and moves the item to history', async () => {
    const user = userEvent.setup()
    const item = activeItem()
    renderActive({ items: [item] })
    const sheet = await openResolve(user, item.content)
    await user.click(within(sheet).getByRole('checkbox'))
    await user.click(within(sheet).getByRole('button', { name: '确认解除' }))
    const live = sheet.querySelector('[aria-live="assertive"]') as HTMLElement
    await waitFor(() => expect(live).toHaveTextContent(`已解除：${item.content}。审计已记录。`))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.queryByText(item.content, { selector: '.mo-c' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '历史与审计' }))
    const closed = (await screen.findByText(item.content, { selector: '.closed .mo-c' })).closest('.closed') as HTMLElement
    expect(within(closed).getByText(`已解除 ${todayISO()}`)).toBeInTheDocument()
    expect(within(closed).getByText('由你本人确认解除')).toBeInTheDocument()
  })
})
