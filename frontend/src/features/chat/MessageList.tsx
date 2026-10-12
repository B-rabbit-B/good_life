import type { ReactNode } from 'react'
import type { ApiError } from '../../api/errors'
import type { Capabilities, MessageOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { dayLabel, todayISO } from '../../lib/dates'
import '../../styles/components/chat.css'
import { collapseRetriedUserMessages } from './agentText'
import { AssistantMessage, PendingAnswer } from './AssistantMessage'
import { UserMessage } from './UserMessage'
import type { LiveTurn } from './useChatStream'

/** 没有对话模型时发消息得到的错误码：页面改显示“去添加模型服务”，不在气泡里重复 */
export const MODEL_NOT_CONFIGURED = 'agent_model_not_configured'

function SendError({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="chat-err" role="alert">
      <Icon name="alert" size={18} />
      <div>
        <p>{error.message}</p>
        <small>错误码 {error.code}</small>
      </div>
      <Button variant="quiet" size="sm" onPress={onRetry}>重试</Button>
    </div>
  )
}

/**
 * 消息流：整段包在一个直角的敏感区里（就医提示左右出血到屏幕边，圆角遮盖会在四角漏出朱色），aria-live="polite"，
 * 流式进行中 aria-busy。日期变了插一条日期分隔。只在末尾追加：打开页面时已有的消息在前，开场卡片（slot）接在它们后面，
 * 之后新发的消息与正在流入的这一轮再往后，最后是 tail（例如“去添加模型服务”）。
 */
export function MessageList({ messages, anchorCount, slot, live, caps, toolsByMessage, userKeyByAnswer = {}, onRetry, tail }: {
  /** 会话里的全部消息（重试留下的重复用户消息在这里合并） */
  messages: MessageOut[]
  /** 打开页面时已有的消息条数：开场卡片放在它们后面 */
  anchorCount: number
  slot: ReactNode
  live: LiveTurn | null
  caps: Capabilities
  toolsByMessage: Record<string, string[]>
  /** 流式回答的编号到它前面那个用户气泡的键：存好的用户消息沿用流式时的键 */
  userKeyByAnswer?: Record<string, string>
  onRetry: () => void
  tail?: ReactNode
}) {
  // 后端先存用户消息再回答：流式这一轮还没结束时会话若被重新取过，末尾那条就是正在显示的这句话，不重复画
  const last = messages[messages.length - 1]
  const list = live && last?.role === 'user' && last.text === live.userText ? messages.slice(0, -1) : messages
  const keptList = collapseRetriedUserMessages(list)
  const kept = new Set(keptList.map((m) => m.id))
  // 用户消息的键：后面紧跟的是本次打开页面后流式出来的回答时，沿用流式时那个用户气泡的键
  const userKey = new Map<string, string>()
  keptList.forEach((message, i) => {
    const next = keptList[i + 1]
    const key = next?.role === 'assistant' ? userKeyByAnswer[next.id] : undefined
    if (message.role === 'user' && key) userKey.set(message.id, key)
  })
  const rows: ReactNode[] = []
  let lastDay: string | null = null
  // 日期分隔以日期为键：流式这一轮存好后分隔不换节点
  const separate = (iso: string) => {
    const day = todayISO(new Date(iso))
    if (day === lastDay) return
    lastDay = day
    rows.push(<div key={`day-${day}`} className="day">{dayLabel(iso)}</div>)
  }
  const pushSlot = () => {
    if (slot) rows.push(<div key="opening">{slot}</div>)
  }

  if (anchorCount === 0) pushSlot()
  list.forEach((message, i) => {
    if (kept.has(message.id)) {
      separate(message.created_at)
      rows.push(message.role === 'user'
        ? <UserMessage key={userKey.get(message.id) ?? message.id} text={message.text} />
        : (
          <AssistantMessage
            key={message.id} message={message} caps={caps} toolsUsed={toolsByMessage[message.id]}
            streamed={message.id in userKeyByAnswer}
          />
        ))
    }
    if (i === anchorCount - 1) pushSlot()
  })

  if (live) {
    separate(new Date().toISOString())
    rows.push(<UserMessage key={live.key} text={live.userText} />)
    if (live.phase === 'waiting' || live.phase === 'streaming') {
      rows.push(<PendingAnswer key="live-answer" text={live.phase === 'streaming' ? live.text : ''} />)
    } else if (live.phase === 'done' && live.turn) {
      const { message_id: id, evidence, flags, tools_used: toolsUsed } = live.turn
      rows.push(
        <AssistantMessage key={id} message={{ id, text: live.text, evidence, flags }} caps={caps} live toolsUsed={toolsUsed} />,
      )
    } else if (live.error && live.error.code !== MODEL_NOT_CONFIGURED) {
      rows.push(<SendError key="live-error" error={live.error} onRetry={onRetry} />)
    }
  }

  const busy = live?.phase === 'waiting' || live?.phase === 'streaming'
  return (
    <Sensitive square area="messages" className="msgs" aria-live="polite" aria-busy={busy || undefined}>
      {rows}
      {tail}
    </Sensitive>
  )
}
