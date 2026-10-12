// 对话的流式读取：fetch 加 ReadableStream 自己解析 text/event-stream（不用 EventSource：它只能 GET、不能带令牌，
// 也读不出非 200 的错误响应）。后端先跑完一轮再按段推送若干 delta，最后是 done；出错时整个响应是非 200 的事件流，
// 里面只有一个 error 事件。请求本身的错误（未登录、会话不存在、参数不合法）是普通的 JSON 错误体。
import { handleErrorResponse, networkError } from './client'
import { getToken } from './token'

export interface TurnDone {
  message_id: string
  evidence: string
  flags: string[]
  tools_used: string[]
}

export type StreamEvent =
  | { type: 'delta'; text: string }
  | { type: 'done'; turn: TurnDone }
  | { type: 'error'; code: string; message: string; status: number }

/**
 * 事件流解析器：统一 CRLF 与单独的 CR，按空行分事件；data 多行用换行连接；忽略冒号开头的注释行与 event、data 以外的字段；
 * 字段与事件可以跨块；end() 时把没有空行收尾的最后一个事件也交出去。没有 event 字段的事件名是 message。
 */
export function createSseParser(onEvent: (name: string, data: string) => void): { push(text: string): void; end(): void } {
  let buffer = ''
  let name = ''
  let data: string[] = []

  const dispatch = () => {
    if (data.length > 0) onEvent(name || 'message', data.join('\n'))
    name = ''
    data = []
  }

  const line = (text: string) => {
    if (text === '') {
      dispatch()
      return
    }
    if (text.startsWith(':')) return
    const colon = text.indexOf(':')
    const field = colon === -1 ? text : text.slice(0, colon)
    let value = colon === -1 ? '' : text.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') name = value
    else if (field === 'data') data.push(value)
  }

  return {
    push(text: string) {
      buffer += text
      // 块末尾的 CR 可能是 CRLF 的前一半：留到下一块再判断
      const keep = buffer.endsWith('\r') ? 1 : 0
      const ready = buffer.slice(0, buffer.length - keep).replace(/\r\n?/g, '\n')
      const lines = ready.split('\n')
      buffer = (lines.pop() ?? '') + buffer.slice(buffer.length - keep)
      for (const text of lines) line(text)
    },
    end() {
      const rest = buffer.replace(/\r\n?/g, '\n')
      buffer = ''
      for (const text of rest.split('\n')) if (text !== '') line(text)
      dispatch()
    },
  }
}

function parseJson(data: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(data) as unknown
    return value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : null
  } catch {
    return null
  }
}

const asString = (value: unknown) => (typeof value === 'string' ? value : '')
const asStrings = (value: unknown) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [])

function errorEvent(data: string, status: number): StreamEvent {
  const body = parseJson(data)
  return {
    type: 'error',
    code: asString(body?.code) || 'http_error',
    message: asString(body?.message) || `服务暂时不可用，请稍后再试（HTTP ${status}）`,
    status,
  }
}

/** 把一个事件交给调用方；返回 true 表示这一轮已经结束（done 或 error） */
function deliver(name: string, data: string, status: number, onEvent: (event: StreamEvent) => void): boolean {
  if (name === 'delta') {
    onEvent({ type: 'delta', text: asString(parseJson(data)?.text) })
    return false
  }
  if (name === 'done') {
    const body = parseJson(data) ?? {}
    onEvent({ type: 'done', turn: {
      message_id: asString(body.message_id), evidence: asString(body.evidence),
      flags: asStrings(body.flags), tools_used: asStrings(body.tools_used),
    } })
    return true
  }
  if (name === 'error') {
    onEvent(errorEvent(data, status))
    return true
  }
  return false
}

function aborted(signal: AbortSignal): Error {
  return (signal.reason as Error | undefined) ?? new DOMException('已取消', 'AbortError')
}

/** 读完响应体，逐块解码（多字节字符可能跨块）并解析；返回是否收到了 done 或 error */
async function readEvents(response: Response, onEvent: (event: StreamEvent) => void, signal?: AbortSignal): Promise<boolean> {
  let finished = false
  const parser = createSseParser((name, data) => {
    if (!finished) finished = deliver(name, data, response.status, onEvent)
  })
  const body = response.body
  if (!body) return finished
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  // 有的实现取消请求后读取不会立刻失败：主动取消读取，读完后按取消处理
  const cancel = () => {
    reader.cancel().catch(() => {})
  }
  signal?.addEventListener('abort', cancel)
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (signal?.aborted) throw aborted(signal)
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
  } catch {
    if (signal?.aborted) throw aborted(signal)
    throw networkError()
  } finally {
    signal?.removeEventListener('abort', cancel)
  }
  parser.push(decoder.decode())
  parser.end()
  return finished
}

/**
 * 发一条消息并流式读取回答：POST /api/agent/conversations/{id}/messages {text, stream: true}。
 * - 200：逐个交出 delta，最后 done（或流中途的 error）；流在 done 之前断开时抛 network_error。
 * - 非 200 的事件流：读完，交出其中的 error 事件（带 HTTP 状态码）。
 * - 非 200 的 JSON：按接口客户端的规则抛 ApiError（401 登录失效时清令牌并通知）。
 * - 网络失败抛 network_error；调用方主动取消时原样抛出 AbortError。
 */
export async function streamMessage(
  conversationId: string,
  text: string,
  opts: { signal?: AbortSignal; onEvent: (event: StreamEvent) => void },
): Promise<void> {
  const headers = new Headers({ 'Content-Type': 'application/json', Accept: 'text/event-stream' })
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const url = new URL(`/api/agent/conversations/${encodeURIComponent(conversationId)}/messages`, window.location.href)

  let response: Response
  try {
    response = await fetch(url, { method: 'POST', headers, body: JSON.stringify({ text, stream: true }), signal: opts.signal })
  } catch (error) {
    if (opts.signal?.aborted) throw error
    throw networkError()
  }

  const eventStream = (response.headers.get('Content-Type') ?? '').includes('text/event-stream')
  if (!response.ok && !eventStream) return handleErrorResponse(response)

  const finished = await readEvents(response, opts.onEvent, opts.signal)
  if (finished) return
  if (response.ok) throw networkError()
  // 非 200 的事件流里没有 error 事件：按 HTTP 状态报错
  opts.onEvent(errorEvent('', response.status))
}
