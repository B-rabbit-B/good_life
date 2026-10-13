import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { addDays, todayISO } from '../../lib/dates'
import { renderChat } from '../../test/chat'
import { capabilities } from '../../test/fixtures/core'
import { opening } from '../../test/fixtures/agent'
import { dueItem, proposalItem, reviewDueEvent } from '../../test/fixtures/medical'
import { openingActionsFor } from './openingActions'

const card = () => screen.findByRole('group', { name: /你有一条医嘱|今天还没有记录饮食/ })
const labels = (el: HTMLElement) => within(el).getAllByRole('button').map((button) => button.textContent)

describe('opening card', () => {
  it('offers continue, go to medical and later for a due item', async () => {
    const due = dueItem()
    renderChat({ opening: opening(), reviews: [due], events: { [due.id]: [reviewDueEvent()] } })
    const group = await card()
    expect(within(group).getByText('今天想问你')).toBeInTheDocument()
    expect(within(group).getByText(opening().question)).toBeInTheDocument()
    expect(labels(group)).toEqual(['继续遵守', '去医嘱页处理', '稍后'])
    // 这一条正在作为开场卡片显示，页头里不再有待处理条
    expect(screen.queryByRole('button', { name: /待复核|医嘱待处理/ })).not.toBeInTheDocument()
  })

  it('drops continue when the first review only has a proposal', async () => {
    renderChat({ opening: opening(), reviews: [proposalItem()] })
    expect(labels(await card())).toEqual(['去医嘱页处理', '稍后'])
    expect(openingActionsFor(opening(), undefined, capabilities()).map((a) => a.label)).toEqual(['去医嘱页处理', '稍后'])
  })

  it('declines on later and collapses into the strip', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const { chat } = renderChat({ opening: opening(), reviews: [due], events: { [due.id]: [reviewDueEvent()] } })
    await user.click(within(await card()).getByRole('button', { name: '稍后' }))
    await waitFor(() => expect(screen.queryByRole('group', { name: /你有一条医嘱/ })).not.toBeInTheDocument())
    expect(chat.openingCalls).toEqual(['decline'])
    const strip = screen.getByRole('button', { name: '饮食要求 待复核' })
    await waitFor(() => expect(strip).toHaveFocus())
  })

  it('answers after continuing in the sheet', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const { chat, medical } = renderChat({ opening: opening(), reviews: [due], events: { [due.id]: [reviewDueEvent()] } })
    await user.click(within(await card()).getByRole('button', { name: '继续遵守' }))
    const sheet = await screen.findByRole('dialog', { name: '继续遵守这条医嘱' })
    expect(chat.openingCalls).toEqual([])
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    await waitFor(() => expect(chat.openingCalls).toEqual(['answer']))
    expect(medical.continues).toHaveLength(1)
    await waitFor(() => expect(screen.queryByRole('group', { name: /你有一条医嘱/ })).not.toBeInTheDocument())
    expect(await screen.findByText('已继续遵守')).toBeInTheDocument()
    // 条目回到生效中，不再进待处理条
    expect(screen.queryByRole('button', { name: '饮食要求 待复核' })).not.toBeInTheDocument()
  })

  it('maps other kinds to their jump actions', async () => {
    const all = capabilities()
    const actions = (kind: string, caps = all) => openingActionsFor(opening({ kind }), undefined, caps)
    expect(actions('period_soon')).toEqual([
      { label: '看看安排', kind: 'navigate', to: '/health/cycle' }, { label: '不用了', kind: 'decline' },
    ])
    expect(actions('trained_no_meal_yesterday')).toEqual([
      { label: '去补记', kind: 'navigate', to: `/records/meals/new?date=${addDays(todayISO(), -1)}` },
      { label: '不用了', kind: 'decline' },
    ])
    expect(actions('no_meal_today')).toEqual([
      { label: '拍一张', kind: 'navigate', to: '/photos/new' },
      { label: '手动记', kind: 'navigate', to: '/records/meals/new' },
      { label: '不用了', kind: 'decline' },
    ])
    expect(actions('profile_stale')).toEqual([
      { label: '更新档案', kind: 'navigate', to: '/me/profile' }, { label: '不用了', kind: 'decline' },
    ])
    expect(actions('something_new')).toEqual([{ label: '不用了', kind: 'decline' }])
    expect(actions('period_soon', capabilities({ cycle: false })).map((a) => a.label)).toEqual(['不用了'])

    // 点跳转：先把开场标为已回答，再去对应的页面
    const user = userEvent.setup()
    const { chat, router } = renderChat({
      opening: opening({ kind: 'no_meal_today', question: '你今天还没有记录饮食，要不要现在记一下？' }),
    })
    const group = await card()
    expect(labels(group)).toEqual(['拍一张', '手动记', '不用了'])
    await user.click(within(group).getByRole('button', { name: '手动记' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/records/meals/new'))
    await waitFor(() => expect(chat.openingCalls).toEqual(['answer']))
  })
})
