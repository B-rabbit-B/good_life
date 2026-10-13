import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { qk } from '../../api/keys'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { HEALTH_DISCLAIMER } from '../../lib/contract'
import { takePendingPhoto } from '../../lib/photoHandoff'
import { gate, renderChat, sendText } from '../../test/chat'
import {
  assistantMessage, assistantText, conversation, noticeLines, opening, SEVERE_REPLY, userMessage,
} from '../../test/fixtures/agent'
import { dueItem, proposalItem, proposedEvent, reviewDueEvent } from '../../test/fixtures/medical'
import { recognition } from '../../test/fixtures/photos'
import { photosHandlers } from '../../test/msw/handlers/photos'
import { server } from '../../test/msw/server'

const ANSWER = '今晚可以换成清蒸鱼或鸡胸肉，配一碗杂粮粥，蛋白质够，也清淡。'
const NOTICE = noticeLines([['卤猪肝', '避免动物内脏与浓肉汤（高嘌呤）']])

const answerBubbles = () => Array.from(document.querySelectorAll<HTMLElement>('.msg-a'))

describe('chat page', () => {
  it('shows the reference tag beside every assistant answer', async () => {
    renderChat({ conversations: [conversation([
      userMessage('练完腿，晚饭吃什么好？'),
      assistantMessage(assistantText('可以吃一份鸡胸肉或豆腐。')),
      userMessage('晚饭想吃卤猪肝配白粥，可以吗？'),
      assistantMessage(assistantText(ANSWER, { notice: NOTICE })),
      userMessage('好的'),
      assistantMessage(assistantText('好的。', { disclaimer: false })),
    ])] })
    await screen.findByText(ANSWER)
    const bubbles = answerBubbles()
    expect(bubbles).toHaveLength(3)
    for (const bubble of bubbles) expect(within(bubble).getByText('仅供参考')).toHaveClass('ref')
    expect(within(bubbles[0] as HTMLElement).getByText(HEALTH_DISCLAIMER)).toBeInTheDocument()
  })

  it('renders the medical notice as a system slip outside the answer bubble', async () => {
    renderChat({ conversations: [conversation([
      userMessage('晚饭想吃卤猪肝配白粥，可以吗？'), assistantMessage(assistantText(ANSWER, { notice: NOTICE })),
    ])] })
    const slip = await screen.findByRole('note', { name: '系统附上的医嘱提醒' })
    expect(within(slip).getByText('医嘱提醒')).toBeInTheDocument()
    expect(within(slip).getByText('系统附注')).toBeInTheDocument()
    expect(within(slip).getByText(NOTICE[0] as string)).toBeInTheDocument()
    expect(within(slip).getByText('卤猪肝：避免动物内脏与浓肉汤（高嘌呤）')).toBeInTheDocument()
    expect(slip.closest('.msg-a')).toBeNull()
    expect(slip.closest('[data-sensitive-area="notes"]')).not.toBeNull()
    const bubble = answerBubbles()[0] as HTMLElement
    expect(bubble).toHaveTextContent(ANSWER)
    expect(bubble).not.toHaveTextContent('卤猪肝')
  })

  it('renders a risk reply as a care alert and hides quick actions', async () => {
    renderChat({ conversations: [conversation([
      userMessage('胸口很闷，一直出冷汗'), assistantMessage(SEVERE_REPLY, { flags: ['risk_severe_symptom'] }),
    ])] })
    // 历史里的就医提示是 note（打开页面时不再播报），刚流出来的那一条才是 alert（见 useChatStream.test）
    const care = await screen.findByRole('note', { name: '请尽快就医' })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(within(care).getByRole('heading', { name: '请尽快就医' })).toBeInTheDocument()
    expect(within(care).getByText(SEVERE_REPLY)).toBeInTheDocument()
    expect(within(care).getByRole('link', { name: '拨打 120' })).toHaveAttribute('href', 'tel:120')
    expect(care.closest('.msg-sys')).toHaveTextContent('系统')
    expect(answerBubbles()).toHaveLength(0)
    expect(screen.queryByText('仅供参考')).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: '快捷操作' })).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '给助手发消息' })).toBeInTheDocument()
  })

  it('labels a fixed fallback reply', async () => {
    renderChat({ conversations: [conversation([
      userMessage('推荐川菜'),
      assistantMessage(assistantText('根据你当前生效的医嘱，下面这些食物不建议吃：麻婆豆腐。'), { flags: ['guard_fallback'] }),
      userMessage('那晚饭呢'),
      assistantMessage(assistantText('清蒸鱼配米饭。')),
    ])] })
    const notes = await screen.findAllByText('这是一条固定的安全回答，不是模型生成的。')
    expect(notes).toHaveLength(1)
    expect(notes[0]?.closest('.msg-a')).toBeNull()
  })

  it('shows only a jump to the medical page for a resolution clue', async () => {
    const messages = [userMessage('医生说我好了'), assistantMessage(assistantText('可以到医嘱页确认。'), { flags: ['resolution_clue'] })]
    const first = renderChat({ conversations: [conversation(messages)] })
    const jump = await screen.findByRole('link', { name: '去医嘱页处理' })
    expect(jump).toHaveAttribute('href', '/health/medical?tab=active')
    expect(screen.getAllByRole('link', { name: '去医嘱页处理' })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: /解除|确认/ })).not.toBeInTheDocument()
    first.unmount()

    renderChat({ conversations: [conversation(messages)], capabilities: { medical: false } })
    await screen.findByText('可以到医嘱页确认。')
    expect(screen.queryByRole('link', { name: '去医嘱页处理' })).not.toBeInTheDocument()
  })

  it('offers no confirm or resolve control anywhere in chat', async () => {
    const user = userEvent.setup()
    const due = dueItem()
    const proposal = proposalItem()
    renderChat({
      conversations: [conversation([
        userMessage('医生说我膝盖好了'), assistantMessage(assistantText('可以到医嘱页确认。'), { flags: ['resolution_clue'] }),
      ])],
      opening: opening(),
      reviews: [due, proposal, dueItem({ id: '00000000-0000-4000-8000-0000000000d3', content: '每日饮酒不超过 0 克' })],
      events: { [due.id]: [reviewDueEvent()], [proposal.id]: [proposedEvent()] },
    })
    await screen.findByRole('group', { name: /你有一条医嘱/ })
    await user.click(screen.getByRole('button', { name: '医嘱待处理 2 条' }))
    await screen.findByRole('button', { name: '不解除' })
    for (const name of ['确认生效', '确认解除']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name })).not.toBeInTheDocument()
      expect(screen.queryByText(name)).not.toBeInTheDocument()
    }
  })

  it('folds evidence with its line count', async () => {
    const user = userEvent.setup()
    renderChat({ conversations: [conversation([
      userMessage('晚饭吃什么'),
      assistantMessage(assistantText(ANSWER), {
        evidence: '清蒸鱼：适合。依据：【医嘱】每日钠不超过 2000 毫克\n杂粮粥：适合。依据：【当日摄入】今天已摄入钠 1,640 毫克',
      }),
    ])] })
    const fold = await screen.findByRole('button', { name: /依据/ })
    expect(fold).toHaveTextContent('依据2')
    expect(fold).toHaveAttribute('aria-expanded', 'false')
    await user.click(fold)
    expect(fold).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('杂粮粥：适合。依据：【当日摄入】今天已摄入钠 1,640 毫克')).toBeVisible()
  })

  it('shows the no model prompt when chat is unassigned', async () => {
    const first = renderChat({ assignments: [] })
    expect(await screen.findByRole('heading', { name: '还没有可用的对话模型' })).toBeInTheDocument()
    expect(screen.getByText('对话和拍照识别都需要先添加一个模型服务，填地址与密钥，大约两分钟。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去添加模型服务' })).toHaveAttribute('href', '/settings/models/new')
    first.unmount()

    renderChat()
    await screen.findByRole('textbox', { name: '给助手发消息' })
    await waitFor(() => expect(document.querySelector('.msgs')).not.toBeNull())
    expect(screen.queryByRole('heading', { name: '还没有可用的对话模型' })).not.toBeInTheDocument()
  })

  it('hides the medical quick action without the medical module', async () => {
    const first = renderChat()
    const quick = await screen.findByRole('group', { name: '快捷操作' })
    expect(within(quick).getAllByRole('link').map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['附近吃什么', '/restaurants'], ['记一餐', '/records/meals/new'], ['看医嘱', '/health/medical'],
    ])
    for (const link of within(quick).getAllByRole('link')) expect(link).toHaveAttribute('data-hit44')
    first.unmount()

    renderChat({ capabilities: { medical: false } })
    const without = await screen.findByRole('group', { name: '快捷操作' })
    expect(within(without).getAllByRole('link').map((link) => link.textContent)).toEqual(['附近吃什么', '记一餐'])
  })

  it('offers camera and gallery inputs', async () => {
    renderChat()
    expect(await screen.findByRole('button', { name: '拍照' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '从相册选图' })).toBeInTheDocument()
    const inputs = Array.from(document.querySelectorAll<HTMLInputElement>('.slab input[type="file"]'))
    expect(inputs).toHaveLength(2)
    const [camera, gallery] = inputs
    expect(camera?.getAttribute('capture')).toBe('environment')
    expect(gallery?.hasAttribute('capture')).toBe(false)
    expect(camera?.accept).toBe('image/jpeg,image/png,image/webp')
    expect(gallery?.accept).toBe(camera?.accept)
    const nav = within(document.querySelector('.slab') as HTMLElement).getByRole('navigation', { name: '主导航' })
    expect(within(nav).getByRole('link', { name: '对话' })).toHaveAttribute('aria-current', 'page')
  })

  it('hands a picked photo to the photo page', async () => {
    const user = userEvent.setup()
    const held = gate()
    const { router } = renderChat()
    const photos = photosHandlers({ hold: held.promise, create: recognition() })
    server.use(...photos.handlers)
    await screen.findByRole('button', { name: '从相册选图' })
    const gallery = document.querySelectorAll<HTMLInputElement>('.slab input[type="file"]')[1] as HTMLInputElement
    const photo = new File(['jpeg'], 'dinner.jpg', { type: 'image/jpeg' })
    await user.upload(gallery, photo)
    await waitFor(() => expect(router.state.location.pathname).toBe('/photos/new'))
    // 拍照页接过照片就开始识别：出现识别进度并发出一次识别请求；照片已被取走
    expect(await screen.findByRole('list', { name: '识别进度' })).toBeInTheDocument()
    await waitFor(() => expect(photos.creates).toHaveLength(1))
    expect(takePendingPhoto()).toBeNull()
    held.open()
  })

  it('wraps the stream and the strip in sensitive regions', async () => {
    const due = dueItem()
    const proposal = proposalItem()
    renderChat({
      conversations: [conversation([userMessage('卤猪肝可以吗'), assistantMessage(assistantText(ANSWER, { notice: NOTICE }))])],
      opening: opening(), reviews: [due, proposal],
    })
    await screen.findByRole('group', { name: /你有一条医嘱/ })
    await screen.findByRole('button', { name: '运动限制 有解除建议' })
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'chat', missing: [], unexpected: [] })
    const messages = document.querySelector('[data-sensitive-area="messages"]') as HTMLElement
    expect(messages).toHaveClass('sens-sq')
    expect(messages).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('group', { name: /你有一条医嘱/ }).closest('[data-sensitive-area="opening"]')).not.toBeNull()
    expect(screen.getByRole('button', { name: '运动限制 有解除建议' }).closest('[data-sensitive-area="reviewBar"]'))
      .not.toBeNull()
    expect(document.querySelector('header [data-sensitive-area="reviewBar"]')).not.toBeNull()
  })

  it('marks the answer busy while streaming', async () => {
    const user = userEvent.setup()
    const hold = gate()
    renderChat({ reply: () => ({ text: assistantText('今晚吃清蒸鱼配米饭，清淡又下饭。'), hold: hold.promise }) })
    await sendText(user, '晚饭吃什么')
    const messages = document.querySelector('[data-sensitive-area="messages"]') as HTMLElement
    await waitFor(() => expect(messages).toHaveAttribute('aria-busy', 'true'))
    hold.open()
    await screen.findByText('今晚吃清蒸鱼配米饭，清淡又下饭。')
    await waitFor(() => expect(messages).not.toHaveAttribute('aria-busy'))
  })
  it('waits for the conversation list before sending', async () => {
    const user = userEvent.setup()
    const list = gate()
    const { chat } = renderChat({ conversations: [conversation([userMessage('昨天的话'), assistantMessage(assistantText('昨天的回答。'))])] })
    const summaries = chat.conversations.map(({ id, title, created_at, updated_at }) => ({ id, title, created_at, updated_at }))
    server.use(http.get('/api/agent/conversations', async () => {
      await list.promise
      return HttpResponse.json(summaries)
    }))
    await sendText(user, '晚饭吃什么')
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
    expect(chat.posts).toEqual([])
    list.open()
    await screen.findByText('昨天的回答。')
    await waitFor(() => expect(screen.getByRole('button', { name: '发送' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: '发送' }))
    await screen.findByText('好的。')
    // 发进了已有的会话，没有新建一个把历史挡掉
    expect(chat.posts.map((post) => post.conversationId)).toEqual([chat.conversations[0]?.id])
    expect(chat.conversations).toHaveLength(1)
    expect(screen.getByText('昨天的回答。')).toBeInTheDocument()
  })

  it('does not start a conversation when the list fails', async () => {
    const user = userEvent.setup()
    const { chat } = renderChat({ conversations: [conversation([userMessage('昨天的话')])] })
    server.use(http.get('/api/agent/conversations', () =>
      HttpResponse.json({ error: { code: 'internal_error', message: '服务器内部错误' } }, { status: 500 })))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务器内部错误')
    await sendText(user, '晚饭吃什么')
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
    expect(chat.posts).toEqual([])
    expect(chat.conversations).toHaveLength(1)
  })

  it('does not send while the conversation itself failed to load', async () => {
    const user = userEvent.setup()
    const { chat } = renderChat({ conversations: [conversation([userMessage('昨天的话')])] })
    server.use(http.get('/api/agent/conversations/:id', () =>
      HttpResponse.json({ error: { code: 'internal_error', message: '服务器内部错误' } }, { status: 500 })))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务器内部错误')
    await sendText(user, '晚饭吃什么')
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
    expect(chat.posts).toEqual([])
  })

  it('shows the history while the opening is still loading', async () => {
    const slow = gate()
    const due = dueItem()
    renderChat({
      conversations: [conversation([userMessage('昨天的话'), assistantMessage(assistantText('昨天的回答。'))])],
      reviews: [due, proposalItem()], events: { [due.id]: [reviewDueEvent()] },
    })
    server.use(http.get('/api/agent/opening', async () => {
      await slow.promise
      return HttpResponse.json({ opening: opening() })
    }))
    // 历史马上出来，开场的位置预留着；待处理条先只占住收起时的高度
    expect(await screen.findByText('昨天的回答。')).toBeInTheDocument()
    expect(document.querySelector('.open-slot')).not.toBeNull()
    expect(document.querySelector('header .rv1-hold')).not.toBeNull()
    expect(screen.queryByRole('button', { name: /医嘱待处理|有解除建议|待复核/ })).not.toBeInTheDocument()
    slow.open()
    expect(await screen.findByRole('group', { name: /你有一条医嘱/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '运动限制 有解除建议' })).toBeInTheDocument()
    expect(document.querySelector('.rv1-hold')).toBeNull()
    expect(document.querySelector('.open-slot')).toBeNull()
  })

  it('keeps the chat when a background refetch fails', async () => {
    const { queryClient } = renderChat({
      conversations: [conversation([userMessage('昨天的话'), assistantMessage(assistantText('昨天的回答。'))])],
    })
    await screen.findByText('昨天的回答。')
    server.use(
      http.get('/api/agent/conversations', () => new HttpResponse('bad gateway', { status: 502 })),
      http.get('/api/agent/conversations/:id', () => new HttpResponse('bad gateway', { status: 502 })),
    )
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: qk.conversations })
    })
    await waitFor(() => expect(queryClient.getQueryState(qk.conversations)?.status).toBe('error'))
    expect(screen.getByText('昨天的回答。')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument()
  })

  it('keeps focus in the input after sending with the button', async () => {
    const user = userEvent.setup()
    renderChat()
    const input = await screen.findByRole('textbox', { name: '给助手发消息' })
    await waitFor(() => expect(document.querySelector('.msgs')).not.toBeNull())
    await user.type(input, '晚饭吃什么')
    await user.click(screen.getByRole('button', { name: '发送' }))
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
    expect(input).toHaveFocus()
    await screen.findByText('好的。')
  })
})
