import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderChat } from '../../test/chat'
import { opening } from '../../test/fixtures/agent'
import { dueItem, proposalItem, proposedEvent, reviewDueEvent } from '../../test/fixtures/medical'

const item = (content: string) => screen.getByText(content).closest('.rvx-i') as HTMLElement

describe('pending strip', () => {
  it('describes a single item by category and state', async () => {
    const first = renderChat({ reviews: [dueItem()] })
    // 文件里的第一个测试：冷启动时模块转换慢，等久一点
    const due = await screen.findByRole('button', { name: '饮食要求 待复核' }, { timeout: 3000 })
    expect(due).toHaveAttribute('aria-expanded', 'false')
    expect(due.closest('header')).not.toBeNull()
    expect(screen.queryByText('低盐饮食，每日钠不超过 2000 毫克')).not.toBeInTheDocument()
    first.unmount()

    renderChat({ reviews: [proposalItem()] })
    expect(await screen.findByRole('button', { name: '运动限制 有解除建议' })).toHaveClass('is-prop')
    expect(screen.queryByText('膝关节术后六周内避免跑跳')).not.toBeInTheDocument()
  })

  it('counts several items', async () => {
    renderChat({ reviews: [dueItem(), proposalItem()] })
    const strip = await screen.findByRole('button', { name: '医嘱待处理 2 条' })
    expect(strip).toHaveTextContent('医嘱待处理2 条')
  })

  it('never truncates text with numbers', async () => {
    const user = userEvent.setup()
    const content = '低盐饮食，每日钠不超过 2000 毫克，每周复查血压 2 次，持续到 2026 年 12 月 31 日之后再由医生决定'
    renderChat({ reviews: [dueItem({ content }), proposalItem()] })
    await user.click(await screen.findByRole('button', { name: '医嘱待处理 2 条' }))
    const text = screen.getByText(content)
    expect(text.textContent).toBe(content)
    expect(document.querySelector('.rvx')?.textContent).not.toContain('…')
  })

  it('offers continue for a due item and keep for a proposal', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const proposal = proposalItem()
    const { medical } = renderChat({
      reviews: [due, proposal], events: { [due.id]: [reviewDueEvent()], [proposal.id]: [proposedEvent()] },
    })
    await user.click(await screen.findByRole('button', { name: '医嘱待处理 2 条' }))
    const dueRow = item(due.content)
    expect(await within(dueRow).findByText('待复核，已到复查日期')).toBeInTheDocument()
    expect(within(dueRow).getAllByRole('button').map((b) => b.textContent)).toEqual(['继续遵守'])
    expect(within(dueRow).getByRole('link', { name: '去医嘱页处理' })).toHaveAttribute('href', '/health/medical?tab=active')

    const proposalRow = item(proposal.content)
    expect(within(proposalRow).getByText('有解除建议')).toBeInTheDocument()
    expect(within(proposalRow).queryByText(/待复核/)).not.toBeInTheDocument()
    expect(within(proposalRow).queryByRole('button', { name: '继续遵守' })).not.toBeInTheDocument()
    expect(within(proposalRow).getByRole('link', { name: '去医嘱页处理' })).toBeInTheDocument()
    await user.click(within(proposalRow).getByRole('button', { name: '不解除' }))
    await waitFor(() => expect(medical.cancels).toEqual([proposal.id]))
    expect(await screen.findByText('已撤销解除建议')).toBeInTheDocument()
    // 撤销后它不再待处理，条子只剩待复核的那一条
    expect(await screen.findByRole('button', { name: '饮食要求 待复核' })).toBeInTheDocument()

    await user.click(within(item(due.content)).getByRole('button', { name: '继续遵守' }))
    expect(await screen.findByRole('dialog', { name: '继续遵守这条医嘱' })).toBeInTheDocument()
  })

  it('names who proposed and marks it for reference', async () => {
    const user = userEvent.setup()
    const proposal = proposalItem()
    renderChat({ reviews: [dueItem(), proposal], events: { [proposal.id]: [proposedEvent('agent')] } })
    await user.click(await screen.findByRole('button', { name: '医嘱待处理 2 条' }))
    const row = item(proposal.content)
    const by = await within(row).findByText('助手根据你 10月10日 的话提出，仍在生效')
    expect(within(by).getByText('仅供参考')).toHaveClass('ref')
  })

  it('excludes the item shown as the opening card', async () => {
    const due = dueItem()
    renderChat({ opening: opening(), reviews: [due, proposalItem()], events: { [due.id]: [reviewDueEvent()] } })
    await screen.findByRole('group', { name: /你有一条医嘱/ })
    expect(screen.getByRole('button', { name: '运动限制 有解除建议' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /医嘱待处理/ })).not.toBeInTheDocument()
  })
})
