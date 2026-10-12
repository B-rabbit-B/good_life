import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { HEALTH_DISCLAIMER } from '../../lib/contract'
import { takePendingPhoto } from '../../lib/photoHandoff'
import { gate, renderChat, sendText } from '../../test/chat'
import {
  assistantMessage, assistantText, conversation, noticeLines, opening, SEVERE_REPLY, userMessage,
} from '../../test/fixtures/agent'
import { dueItem, proposalItem, proposedEvent, reviewDueEvent } from '../../test/fixtures/medical'

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
    const care = await screen.findByRole('alert')
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
    const { router } = renderChat()
    await screen.findByRole('button', { name: '从相册选图' })
    const gallery = document.querySelectorAll<HTMLInputElement>('.slab input[type="file"]')[1] as HTMLInputElement
    const photo = new File(['jpeg'], 'dinner.jpg', { type: 'image/jpeg' })
    await user.upload(gallery, photo)
    await waitFor(() => expect(router.state.location.pathname).toBe('/photos/new'))
    expect(takePendingPhoto()).toBe(photo)
    expect(takePendingPhoto()).toBeNull()
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
})
