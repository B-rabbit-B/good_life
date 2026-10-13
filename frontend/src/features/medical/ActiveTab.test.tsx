import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { PENDING_REVIEW_NOTE } from '../../lib/contract'
import { formatMonthDay, todayISO } from '../../lib/dates'
import {
  activeItem, dueItem, END_SOON_REASON, order, proposalItem, proposedEvent, REVIEW_REASON, reviewDueEvent,
} from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderActive(opts: MedicalOptions) {
  const result = renderRoute('/health/medical?tab=active')
  const medical = medicalHandlers({ orders: [order()], ...opts })
  server.use(...medical.handlers)
  return { ...result, medical }
}

const rowOf = async (content: string) => (await screen.findByText(content, { selector: '.mo-c' })).closest('.mo') as HTMLElement

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
}, 60_000)

describe('active tab', { timeout: 15_000 }, () => {
  it('shows due items with the backend reason and the pending review note', async () => {
    const due = dueItem()
    const ending = dueItem({ id: '00000000-0000-4000-8000-0000000000d9', content: '一周内忌食辛辣', review_date: null, end_date: '2026-10-13' })
    renderActive({
      items: [activeItem(), due, ending],
      events: { [due.id]: [reviewDueEvent(REVIEW_REASON)], [ending.id]: [reviewDueEvent(END_SOON_REASON)] },
    })
    const row = await rowOf(due.content)
    expect(await within(row).findByText('待复核，已到复查日期')).toHaveClass('due')
    expect(within(row).getByText(PENDING_REVIEW_NOTE)).toBeInTheDocument()
    expect(within(row).getByText('2026-07-12')).toBeInTheDocument()
    expect(within(row).getByText('2026-10-12')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '继续遵守' })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '确认解除' })).toBeInTheDocument()
    expect(await within(await rowOf('一周内忌食辛辣')).findByText('待复核，即将到预计结束日期')).toBeInTheDocument()

    // 待复核的排在前面；没有建议的生效条目写“生效中”，动作是修改与确认解除
    const plain = await rowOf(activeItem().content)
    expect(within(plain).getByText('生效中')).toBeInTheDocument()
    expect(within(plain).getAllByRole('button').map((button) => button.textContent)).toEqual(['修改', '确认解除'])
    const rows = Array.from(document.querySelectorAll('.mo .mo-c')).map((el) => el.textContent)
    expect(rows).toEqual([due.content, '一周内忌食辛辣', activeItem().content])
    expect(screen.getByRole('tab', { name: /^生效中/ })).toHaveTextContent('生效中 3')
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'medical', missing: [], unexpected: [] })
  })

  it('shows who proposed a resolution with a reference tag', async () => {
    const byAgent = proposalItem()
    const byUser = proposalItem({ id: '00000000-0000-4000-8000-0000000000d8', content: '一周内忌食辛辣', resolution_reason: '医生说可以恢复了' })
    renderActive({
      items: [byAgent, byUser],
      events: { [byAgent.id]: [proposedEvent('agent')], [byUser.id]: [proposedEvent('user')] },
    })
    const day = formatMonthDay(todayISO(new Date(byAgent.resolution_proposed_at ?? '')))
    const agentBlock = (await within(await rowOf(byAgent.content)).findByText(`助手在 ${day} 提出了一条解除建议`)).closest('.prop') as HTMLElement
    expect(within(agentBlock).getByText('仅供参考')).toBeInTheDocument()
    // 理由是助手写的：写“助手给出的理由：”，不当作你的原话
    expect(within(agentBlock).getByText('助手给出的理由：')).toBeInTheDocument()
    expect(within(agentBlock).queryByText(/依据是你在/)).not.toBeInTheDocument()
    expect(within(agentBlock).getByText('用户转述医生说已经好了')).toBeInTheDocument()
    expect(within(agentBlock).getByText('建议不会改变约束，只有你在这里确认后才会解除。')).toBeInTheDocument()
    expect(within(agentBlock).getAllByRole('button').map((button) => button.textContent)).toEqual(['不解除', '确认解除'])
    // 带建议的条目仍写“生效中”，不写“待复核”，也没有“继续遵守”
    const row = await rowOf(byAgent.content)
    expect(within(row).getByText('生效中')).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: '继续遵守' })).not.toBeInTheDocument()

    const userBlock = (await within(await rowOf('一周内忌食辛辣')).findByText('你提出了一条解除建议')).closest('.prop') as HTMLElement
    expect(within(userBlock).getByText('理由：')).toBeInTheDocument()
    expect(within(userBlock).queryByText('助手给出的理由：')).not.toBeInTheDocument()
    expect(within(userBlock).getByText('医生说可以恢复了')).toBeInTheDocument()
    expect(within(userBlock).getByText('仅供参考')).toBeInTheDocument()
  })

  it('keeps a proposal without resolving it', async () => {
    const user = userEvent.setup()
    const item = proposalItem()
    const { medical } = renderActive({ items: [item], events: { [item.id]: [proposedEvent('agent')] } })
    const row = await rowOf(item.content)
    await user.click(within(row).getByRole('button', { name: '不解除' }))
    await waitFor(() => expect(medical.cancels).toEqual([item.id]))
    expect(await screen.findByText('已撤销解除建议')).toBeInTheDocument()
    await waitFor(() => expect(within(row).queryByText(/提出了一条解除建议/)).not.toBeInTheDocument())
    expect(medical.resolves).toEqual([])
    expect(within(await rowOf(item.content)).getByText('生效中')).toBeInTheDocument()
  })

  it('opens the continue sheet for a due item', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const { medical } = renderActive({ items: [due], events: { [due.id]: [reviewDueEvent()] } })
    const row = await rowOf(due.content)
    await within(row).findByText('待复核，已到复查日期')
    await user.click(within(row).getByRole('button', { name: '继续遵守' }))
    const sheet = await screen.findByRole('dialog', { name: '继续遵守这条医嘱' })
    expect(within(sheet).getByText(REVIEW_REASON)).toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    await waitFor(() => expect(medical.continues).toHaveLength(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.resolves).toEqual([])
  })

  it('never truncates contents with numbers', async () => {
    const content = '低盐饮食，每日钠不超过 2000 毫克，每日食盐不超过 5 克，每周至少 3 次复测血压并记录 120/80 以下的读数'
    renderActive({ items: [activeItem({ content })] })
    const el = await screen.findByText(content, { selector: '.mo-c' })
    expect(el.textContent).toBe(content)
    expect(document.body.textContent).not.toContain('…')
    expect(el.closest('[style*="ellipsis"]')).toBeNull()
  })
})
