import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { networkError } from '../../api/client'
import { asApiError } from '../../api/errors'
import { useConversation, useConversations, useCreateConversation, useOpening } from '../../api/hooks/agent'
import { useAssignments } from '../../api/hooks/llm'
import { useMedicalReviews } from '../../api/hooks/medical'
import { useCapabilities } from '../../api/hooks/profile'
import type { MessageOut } from '../../api/types'
import { useScroller, useSensitivePage } from '../../app/AppShell'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { AGENT_MODEL_NOT_CONFIGURED } from '../../lib/contract'
import { formatMonthDay, formatWeekday, todayISO } from '../../lib/dates'
import '../../styles/components/chat.css'
import { riskCategory } from './agentText'
import { ChatDock, COMPOSER_ID } from './ChatDock'
import { MessageList } from './MessageList'
import { NoModelPrompt } from './NoModelPrompt'
import { OpeningCard } from './OpeningCard'
import { PendingStrip, STRIP_TOGGLE_ID } from './PendingStrip'
import { useChatStream } from './useChatStream'

const NO_CAPS = { cycle: false, medical: false, nutrition: false, fitness: false }
const NO_MESSAGES: MessageOut[] = []
// 离底部这么近时算“在看最新的”，新内容到了就跟着滚到底
const NEAR_BOTTOM = 80

/** 最后一条助手消息（流式这一轮优先）是不是就医提示 */
function lastIsRisk(messages: MessageOut[], liveFlags: string[] | undefined): boolean {
  if (liveFlags) return riskCategory(liveFlags) !== null
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i]
    if (message?.role === 'assistant') return riskCategory(message.flags) !== null
  }
  return false
}

/**
 * 对话页：页头（对话、今天的日期与星期、待处理条），消息流（历史、开场卡片、本次的流式回答、没有模型时的提示），
 * 对话底座。会话取最近的一个；会话列表取到之前不能发送，列表取到且为空时第一次发送前新建。
 * 首屏不跳动：会话与待处理列表都到了才画消息流；开场（可能要等模型改写措辞）不挡历史，还没到时在它的位置预留高度；
 * 待处理列表不空而开场还没到时，待处理条先只占住收起时的高度（开场问的那一条要从条里拿掉）。
 * 后台重新请求失败时缓存里的会话照常显示，只有一条数据都没有时才显示失败。
 */
export default function ChatPage() {
  useSensitivePage('chat')
  const caps = useCapabilities().data ?? NO_CAPS
  const conversations = useConversations()
  const [createdId, setCreatedId] = useState<string | null>(null)
  const conversationId = conversations.data?.[0]?.id ?? createdId
  const conversation = useConversation(conversationId)
  const create = useCreateConversation()
  const reviews = useMedicalReviews()
  const opening = useOpening()
  const assignments = useAssignments()
  const scroller = useScroller()

  const listed = conversations.data
  const ensureConversation = useCallback(async () => {
    if (conversationId) return conversationId
    // 只有取到了会话列表、并且确实是空的，才新建（列表没取到时新建会把已有的历史挡掉）
    if (listed === undefined) throw networkError()
    const created = await create.mutateAsync()
    setCreatedId(created.id)
    return created.id
  }, [conversationId, listed, create])
  const { live, send, retry, toolsByMessage, userKeyByAnswer } = useChatStream(conversationId, ensureConversation)

  const messages = conversation.data?.messages ?? NO_MESSAGES
  const reviewItems = caps.medical ? (reviews.data ?? []) : []
  const reviewsSettled = !caps.medical || reviews.isSuccess || reviews.isError
  const openingSettled = opening.isSuccess || opening.isError
  const conversationReady = conversations.data !== undefined && (conversationId === null || conversation.data !== undefined)
  const ready = conversationReady && reviewsSettled

  // 打开页面时已有几条消息：开场卡片接在它们后面，之后的消息再往后（列表只在末尾追加）
  const [anchorCount, setAnchorCount] = useState<number | null>(null)
  if (ready && anchorCount === null) setAnchorCount(messages.length)

  const shownOpening = opening.data?.opening ?? null
  const target = shownOpening?.kind === 'review_due' ? reviewItems[0] : undefined
  const stripItems = target ? reviewItems.filter((item) => item.id !== target.id) : reviewItems
  const noModel = (assignments.isSuccess && !assignments.data.some((a) => a.purpose === 'chat'))
    || live?.error?.code === AGENT_MODEL_NOT_CONFIGURED

  // 开场卡片收起后焦点落在页头的待处理条上（没有时回到输入框）
  const onCollapsed = useCallback(() => {
    requestAnimationFrame(() => (document.getElementById(STRIP_TOGGLE_ID) ?? document.getElementById(COMPOSER_ID))?.focus())
  }, [])

  // 新内容到了：在看最新的（离底部不远）时跟着滚到底；第一次画出消息流时直接到底
  const nearBottom = useRef(true)
  useLayoutEffect(() => {
    const el = scroller.current
    if (!el) return undefined
    const onScroll = () => {
      nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [scroller])
  useLayoutEffect(() => {
    const el = scroller.current
    if (ready && el && nearBottom.current) el.scrollTo({ top: el.scrollHeight })
  }, [scroller, ready, messages, live, shownOpening, openingSettled, noModel])

  const onSend = (text: string) => {
    nearBottom.current = true
    void send(text)
  }

  let body
  const listFailed = conversations.isError && conversations.data === undefined
  const detailFailed = conversationId !== null && conversation.isError && conversation.data === undefined
  if (listFailed || detailFailed) {
    const failed = listFailed ? conversations.error : conversation.error
    const error = asApiError(failed)
    body = (
      <ErrorState error={error} onRetry={() => void (listFailed ? conversations.refetch() : conversation.refetch())} />
    )
  } else if (!ready) {
    body = <LoadingState variant="list" text="正在读取对话" />
  } else {
    let slot = null
    if (!openingSettled) slot = <div className="open-slot" aria-hidden="true" />
    else if (shownOpening) slot = <OpeningCard key={shownOpening.id} opening={shownOpening} target={target} onCollapsed={onCollapsed} />
    body = (
      <MessageList
        messages={messages} anchorCount={anchorCount ?? messages.length} slot={slot} live={live} caps={caps}
        toolsByMessage={toolsByMessage} userKeyByAnswer={userKeyByAnswer} onRetry={() => void retry()}
        tail={openingSettled && noModel ? <NoModelPrompt /> : null}
      />
    )
  }

  const today = todayISO()
  return (
    <>
      <PageHeader titleKey="chat" variant="chat" caption={`${formatMonthDay(today)} ${formatWeekday(today)}`}>
        {ready && reviewItems.length > 0 && !openingSettled && <div className="rv1-hold" aria-hidden="true" />}
        {ready && openingSettled && stripItems.length > 0 && <PendingStrip items={stripItems} />}
      </PageHeader>
      {body}
      <ChatDock
        caps={caps} onSend={onSend} busy={live?.phase === 'waiting' || live?.phase === 'streaming'}
        ready={conversations.data !== undefined}
        hideQuickActions={lastIsRisk(messages, live?.phase === 'done' ? live.turn?.flags : undefined)}
      />
    </>
  )
}
