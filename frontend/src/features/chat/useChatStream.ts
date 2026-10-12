import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, networkError } from '../../api/client'
import { useConversation } from '../../api/hooks/agent'
import { qk } from '../../api/keys'
import { streamMessage, type TurnDone } from '../../api/sse'
import { usePrefersReducedMotion } from '../../lib/motion'

export interface LiveTurn {
  userText: string
  /** 已经流入的整段文字（按动画帧合批更新） */
  text: string
  phase: 'waiting' | 'streaming' | 'done' | 'error'
  turn?: TurnDone
  error?: ApiError
}

const nextFrame = (callback: () => void): (() => void) => {
  if (typeof requestAnimationFrame === 'function') {
    const id = requestAnimationFrame(callback)
    return () => cancelAnimationFrame(id)
  }
  const id = setTimeout(callback, 16)
  return () => clearTimeout(id)
}

/**
 * 发消息与流式回答。发送后立刻有用户气泡与“正在查询……”；delta 按动画帧合批（减弱动效时攒到 done 一次显示）；
 * done 后刷新会话，会话里出现编号相同的助手消息时临时的这一轮就不再返回（列表里那条接上，不闪、不重复）；
 * 出错时保留用户原话，retry 用同一句话重发。toolsByMessage 记下本次打开页面以来每条流式回答用过的工具。
 */
export function useChatStream(conversationId: string | null, ensureConversation: () => Promise<string>) {
  const queryClient = useQueryClient()
  const reduced = usePrefersReducedMotion()
  const reducedRef = useRef(reduced)
  const [live, setLive] = useState<LiveTurn | null>(null)
  const [toolsByMessage, setToolsByMessage] = useState<Record<string, string[]>>({})
  const turnRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const conversation = useConversation(conversationId)

  useEffect(() => {
    reducedRef.current = reduced
  }, [reduced])
  useEffect(() => () => abortRef.current?.abort(), [])

  const send = useCallback(async (text: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    turnRef.current += 1
    const turn = turnRef.current
    const current = () => turnRef.current === turn
    setLive({ userText: text, text: '', phase: 'waiting' })

    let acc = ''
    let cancelFrame: (() => void) | null = null
    const flush = () => {
      cancelFrame = null
      if (!current() || reducedRef.current) return
      const snapshot = acc
      setLive({ userText: text, text: snapshot, phase: 'streaming' })
    }
    const fail = (error: ApiError) => {
      cancelFrame?.()
      if (current()) setLive({ userText: text, text: '', phase: 'error', error })
    }

    try {
      const id = await ensureConversation()
      await streamMessage(id, text, {
        signal: controller.signal,
        onEvent: (event) => {
          if (!current()) return
          if (event.type === 'delta') {
            acc += event.text
            cancelFrame ??= nextFrame(flush)
          } else if (event.type === 'done') {
            cancelFrame?.()
            const done = event.turn
            setToolsByMessage((tools) => ({ ...tools, [done.message_id]: done.tools_used }))
            setLive({ userText: text, text: acc, phase: 'done', turn: done })
            void queryClient.invalidateQueries({ queryKey: qk.conversation(id) })
            void queryClient.invalidateQueries({ queryKey: qk.conversations, exact: true })
          } else {
            fail(new ApiError(event.status, event.code, event.message))
          }
        },
      })
    } catch (error) {
      if (controller.signal.aborted) return
      fail(error instanceof ApiError ? error : networkError())
    }
  }, [ensureConversation, queryClient])

  const retry = useCallback(async () => {
    if (live) await send(live.userText)
  }, [live, send])

  // 会话里已经有这条助手消息了：临时的这一轮交给列表
  const saved = live?.turn ? conversation.data?.messages.some((m) => m.id === live.turn?.message_id) : false
  return { live: saved ? null : live, send, retry, toolsByMessage }
}
