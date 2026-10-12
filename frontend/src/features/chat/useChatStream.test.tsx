import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { gate, renderChat, sendText } from '../../test/chat'
import { assistantText } from '../../test/fixtures/agent'
import { setMediaMatches } from '../../test/setup'
import { THINKING_TEXT } from './AssistantMessage'

const ANSWER = '今晚可以换成清蒸鱼或鸡胸肉，配一碗杂粮粥，蛋白质够，也清淡。'

const bubbles = (selector: string) => Array.from(document.querySelectorAll<HTMLElement>(selector))

describe('chat stream', () => {
  it('shows the user text and a thinking line at once', async () => {
    const user = userEvent.setup()
    const start = gate()
    renderChat({ reply: () => ({ text: assistantText(ANSWER), start: start.promise }) })
    await sendText(user, '晚饭吃什么')
    const userBubble = await screen.findByText('晚饭吃什么')
    expect(userBubble.closest('.msg-u')).not.toBeNull()
    const thinking = await screen.findByText(THINKING_TEXT)
    expect(thinking).toHaveAttribute('role', 'status')
    expect(thinking.closest('.msg-a')).not.toBeNull()
    expect(document.querySelector('[data-sensitive-area="messages"]')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('textbox', { name: '给助手发消息' })).toHaveValue('')
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
    start.open()
    await screen.findByText(ANSWER)
  })

  it('appends deltas and replaces the live bubble with the saved message by id', async () => {
    const user = userEvent.setup()
    const hold = gate()
    const { chat } = renderChat({ reply: () => ({ text: assistantText(ANSWER), chunk: 8, hold: hold.promise }) })
    await sendText(user, '晚饭吃什么')
    // 第一段到了：气泡里只有这一段，光标在末尾，免责句还没出现
    await waitFor(() => expect(bubbles('.msg-a')[0]).toHaveTextContent(ANSWER.slice(0, 8)))
    const live = bubbles('.msg-a')[0] as HTMLElement
    expect(live.querySelector('.ans')?.textContent).toBe(ANSWER.slice(0, 8))
    expect(live.querySelector('.caret')).not.toBeNull()
    hold.open()
    await screen.findByText(ANSWER)
    // 会话里有了编号相同的助手消息：临时的这一轮交给列表，只剩一条用户消息与一条回答
    await waitFor(() => expect(chat.conversations[0]?.messages).toHaveLength(2))
    const saved = chat.conversations[0]?.messages[1]
    await waitFor(() => expect(bubbles('.msg-a')).toHaveLength(1))
    expect(bubbles('.msg-u')).toHaveLength(1)
    expect(within(bubbles('.msg-a')[0] as HTMLElement).getByText('仅供参考')).toBeInTheDocument()
    expect(saved?.role).toBe('assistant')
    expect(chat.posts.map((post) => post.body)).toEqual([{ text: '晚饭吃什么', stream: true }])
  })

  it('shows the whole answer at once when motion is reduced', async () => {
    setMediaMatches((query) => query.includes('prefers-reduced-motion'))
    const user = userEvent.setup()
    const hold = gate()
    renderChat({ reply: () => ({ text: assistantText(ANSWER), chunk: 8, hold: hold.promise }) })
    await sendText(user, '晚饭吃什么')
    await screen.findByText(THINKING_TEXT)
    // 第一段已经推过来了，但减弱动效时攒着，仍是“正在查询……”
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getByText(THINKING_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(ANSWER.slice(0, 8), { exact: false })).not.toBeInTheDocument()
    hold.open()
    expect(await screen.findByText(ANSWER)).toBeInTheDocument()
    expect(screen.queryByText(THINKING_TEXT)).not.toBeInTheDocument()
  })

  it('keeps the text and retries with it after an error', async () => {
    const user = userEvent.setup()
    const { chat } = renderChat({
      reply: (_text, attempt) => attempt === 1
        ? { error: { status: 502, code: 'agent_model_error', message: '模型服务暂时不可用，请稍后再试' } }
        : { text: assistantText(ANSWER) },
    })
    await sendText(user, '晚饭吃什么')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('模型服务暂时不可用，请稍后再试')
    expect(alert).toHaveTextContent('错误码 agent_model_error')
    expect(screen.getByText('晚饭吃什么').closest('.msg-u')).not.toBeNull()

    await user.click(within(alert).getByRole('button', { name: '重试' }))
    await screen.findByText(ANSWER)
    const sent = chat.posts.map((post) => (post.body as { text: string }).text)
    expect(sent).toEqual(['晚饭吃什么', '晚饭吃什么'])
    // 后端存了两遍同一句话：列表里只显示一次
    await waitFor(() => expect(chat.conversations[0]?.messages).toHaveLength(3))
    await waitFor(() => expect(bubbles('.msg-u')).toHaveLength(1))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the no model prompt on agent_model_not_configured', async () => {
    const user = userEvent.setup()
    renderChat({
      reply: () => ({ error: {
        status: 409, code: 'agent_model_not_configured',
        message: '还没有选择对话模型：请先到设置页的“模型服务”里，为“日常对话”选择一个模型，再来和助手聊天。',
      } }),
    })
    await screen.findByRole('textbox', { name: '给助手发消息' })
    expect(screen.queryByRole('heading', { name: '还没有可用的对话模型' })).not.toBeInTheDocument()
    await sendText(user, '晚饭吃什么')
    expect(await screen.findByRole('heading', { name: '还没有可用的对话模型' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去添加模型服务' })).toHaveAttribute('href', '/settings/models/new')
    expect(screen.getByText('晚饭吃什么').closest('.msg-u')).not.toBeNull()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
