// 智能体的接口：设置、会话与消息（流式）、开场。会话按后端的做法模拟：先存用户消息再回答，
// 成功时存一条带编号的助手消息并以事件流推送（每段几个字，最后 done）；出错时用户消息照样留着，返回非 200 的事件流。
import { delay, http, HttpResponse, type HttpHandler } from 'msw'
import type {
  AgentSettingsOut, AgentSettingsUpdate, ConversationDetailOut, ConversationOut, OpeningOut,
} from '../../../api/types'
import { assistantText, CONVERSATION_ID, newId } from '../../fixtures/agent'
import { agentSettings } from '../../fixtures/profile'

/** 每次调用各有一份设置；会改设置的测试在 renderRoute 之后 server.use(...agentHandlers())，免得改动留给下一个测试。 */
export function agentHandlers(initial: AgentSettingsOut = agentSettings()): HttpHandler[] {
  let settings = initial
  return [
    http.get('/api/agent/settings', () => HttpResponse.json(settings)),
    http.put('/api/agent/settings', async ({ request }) => {
      settings = { ...settings, ...((await request.json()) as AgentSettingsUpdate) }
      return HttpResponse.json(settings)
    }),
  ]
}

/** 一轮回答怎么推：成功时的整段文字、依据、标记与用过的工具；或者一个错误 */
export interface ReplyScript {
  text?: string
  evidence?: string
  flags?: string[]
  tools_used?: string[]
  /** 每段的字数（默认 6） */
  chunk?: number
  /** 推第一段之前等它（测试刚发出时的样子） */
  start?: Promise<void>
  /** 推完第一段后等它，再推其余的（测试流式中途的样子） */
  hold?: Promise<void>
  /** 事件流错误（后端的 AppError）：用户消息照样保存 */
  error?: { status: number; code: string; message: string }
}

export interface ChatOptions {
  /** 已有的会话（第一个是最近的）；默认没有会话 */
  conversations?: ConversationDetailOut[]
  opening?: OpeningOut | null
  reply?: (text: string, attempt: number) => ReplyScript
}

const encoder = new TextEncoder()
const event = (name: string, data: unknown) => encoder.encode(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`)

function eventStream(write: (push: (chunk: Uint8Array) => void) => Promise<void>, status = 200) {
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      await write((chunk) => controller.enqueue(chunk))
      controller.close()
    },
  })
  return new HttpResponse(body, { status, headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

const summary = ({ id, title, created_at, updated_at }: ConversationDetailOut): ConversationOut =>
  ({ id, title, created_at, updated_at })

/** 会话的内存仓库：posts 是每次发消息的请求体，openingCalls 是对开场做过的动作 */
export function chatHandlers(opts: ChatOptions = {}) {
  const conversations = (opts.conversations ?? []).map((c) => ({ ...c, messages: [...c.messages] }))
  const posts: { conversationId: string; body: unknown }[] = []
  const openingCalls: string[] = []
  const reply: NonNullable<ChatOptions['reply']> = opts.reply ?? (() => ({ text: assistantText('好的。') }))
  const find = (id: string) => conversations.find((c) => c.id === id)

  const handlers: HttpHandler[] = [
    http.get('/api/agent/conversations', () => HttpResponse.json(conversations.map(summary))),
    http.post('/api/agent/conversations', () => {
      const id = conversations.length === 0 ? CONVERSATION_ID : newId()
      const created: ConversationDetailOut = {
        id, title: null, created_at: '2026-10-12T10:00:00Z', updated_at: '2026-10-12T10:00:00Z', messages: [],
      }
      conversations.unshift(created)
      return HttpResponse.json(summary(created), { status: 201 })
    }),
    http.get('/api/agent/conversations/:id', ({ params }) => {
      const found = find(String(params.id))
      return found
        ? HttpResponse.json(found)
        : HttpResponse.json({ error: { code: 'not_found', message: '会话不存在' } }, { status: 404 })
    }),
    http.post('/api/agent/conversations/:id/messages', async ({ params, request }) => {
      const found = find(String(params.id))
      if (!found) return HttpResponse.json({ error: { code: 'not_found', message: '会话不存在' } }, { status: 404 })
      const body = (await request.json()) as { text: string }
      posts.push({ conversationId: found.id, body })
      found.messages.push({
        id: newId(), role: 'user', text: body.text, evidence: '', flags: [], created_at: new Date().toISOString(),
      })
      const script = reply(body.text, posts.length)
      if (script.error) {
        const { status, code, message } = script.error
        return eventStream(async (push) => {
          push(event('error', { code, message }))
          await Promise.resolve()
        }, status)
      }
      const text = script.text ?? ''
      const turn = {
        message_id: newId(), evidence: script.evidence ?? '', flags: script.flags ?? [], tools_used: script.tools_used ?? [],
      }
      const size = script.chunk ?? 6
      return eventStream(async (push) => {
        if (script.start) await script.start
        for (let start = 0; start < text.length; start += size) {
          push(event('delta', { text: text.slice(start, start + size) }))
          if (start === 0 && script.hold) await script.hold
          else await delay(1)
        }
        // 先存好再推 done，和后端一样：收到 done 时会话里已经有这条助手消息
        found.messages.push({
          id: turn.message_id, role: 'assistant', text, evidence: turn.evidence, flags: turn.flags,
          created_at: new Date().toISOString(),
        })
        push(event('done', turn))
      })
    }),
    http.get('/api/agent/opening', () => HttpResponse.json({ opening: opts.opening ?? null })),
    http.post('/api/agent/opening/:id/:action', ({ params }) => {
      openingCalls.push(String(params.action))
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers, posts, openingCalls, conversations }
}
