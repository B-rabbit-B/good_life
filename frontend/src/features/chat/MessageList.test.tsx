import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Capabilities } from '../../api/types'
import { CoverProvider } from '../../components/cover'
import { assistantMessage, assistantText, userMessage } from '../../test/fixtures/agent'
import { splitAssistantText } from './agentText'
import { MessageList } from './MessageList'
import type { LiveTurn } from './useChatStream'

// 数一数存好的回答被拆分（也就是重新渲染）了几次
vi.mock('./agentText', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./agentText')>()
  return { ...actual, splitAssistantText: vi.fn(actual.splitAssistantText) }
})

const CAPS: Capabilities = { cycle: true, medical: true, nutrition: true, fitness: true }
const SAVED = assistantText('昨天晚上可以喝点小米粥。')
const MESSAGES = [userMessage('昨天晚饭吃什么'), assistantMessage(SAVED)]
const TOOLS: Record<string, string[]> = {}
const onRetry = () => {}

const list = (live: LiveTurn) => (
  <CoverProvider>
    <MessageList
      messages={MESSAGES} anchorCount={MESSAGES.length} slot={null} live={live} caps={CAPS} toolsByMessage={TOOLS} onRetry={onRetry}
    />
  </CoverProvider>
)

describe('message list', () => {
  it('does not rerender the saved messages while a reply streams', () => {
    const renders = () => vi.mocked(splitAssistantText).mock.calls.filter(([text]) => text === SAVED).length
    const turn = (text: string): LiveTurn => ({ key: 'turn-1', userText: '今晚吃什么', text, phase: 'streaming' })
    const { rerender } = render(list(turn('')) as ReactElement)
    expect(screen.getByText('昨天晚上可以喝点小米粥。')).toBeInTheDocument()
    const before = renders()
    expect(before).toBeGreaterThan(0)
    rerender(list(turn('今晚')))
    rerender(list(turn('今晚可以换成')))
    rerender(list(turn('今晚可以换成清蒸鱼')))
    expect(renders()).toBe(before)
  })
})
