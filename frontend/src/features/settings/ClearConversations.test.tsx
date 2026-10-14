import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { qk } from '../../api/keys'
import type { ConversationDetailOut, ConversationOut, OpeningResponse } from '../../api/types'
import { assistantMessage, conversation, opening, userMessage } from '../../test/fixtures/agent'
import { accountHandlers } from '../../test/msw/handlers/account'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const DETAIL = conversation([userMessage('午饭吃什么'), assistantMessage('清淡一些的就好。')])
const CONVERSATION: ConversationOut = {
  id: DETAIL.id, title: DETAIL.title, created_at: DETAIL.created_at, updated_at: DETAIL.updated_at,
}

beforeAll(async () => {
  await import('./PrivacyPage')
}, 60_000)

describe('clear conversations', { timeout: 15_000 }, () => {
  it('clears every conversation after confirming and refreshes chat', async () => {
    const user = userEvent.setup()
    const account = accountHandlers()
    server.use(...account.handlers)
    const { queryClient } = renderRoute('/settings/privacy')
    // 对话页留下的缓存：会话列表、一个会话的消息与今天的开场
    queryClient.setQueryData<ConversationOut[]>(qk.conversations, [CONVERSATION])
    queryClient.setQueryData<ConversationDetailOut>(qk.conversation(CONVERSATION.id), DETAIL)
    queryClient.setQueryData<OpeningResponse>(qk.opening, { opening: opening() })

    const section = (await screen.findByRole('heading', { name: '清空对话历史' })).closest('section') as HTMLElement
    await user.click(within(section).getByRole('button', { name: '清空对话历史' }))
    const dialog = await screen.findByRole('dialog', { name: '清空对话历史' })
    expect(within(dialog).getByText('开场问候', { exact: false })).toBeInTheDocument()
    expect(within(dialog).getByText('不受影响', { exact: false })).toBeInTheDocument()
    const confirm = within(dialog).getByRole('button', { name: '清空' })
    expect(confirm).toBeDisabled()
    await user.click(within(dialog).getByRole('checkbox', { name: '我知道清空后不能恢复' }))
    expect(account.record.clears).toBe(0)
    await user.click(confirm)

    await waitFor(() => expect(account.record.clears).toBe(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('已清空')).toBeInTheDocument()
    expect(queryClient.getQueryData(qk.conversations)).toBeUndefined()
    expect(queryClient.getQueryData(qk.conversation(CONVERSATION.id))).toBeUndefined()
    expect(queryClient.getQueryData(qk.opening)).toEqual({ opening: null })
  })
})
