import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../test/msw/server'
import { ApiError, onUnauthorized } from './client'
import { createSseParser, streamMessage, type StreamEvent } from './sse'
import { getToken, setToken } from './token'

const URL = '/api/agent/conversations/c1/messages'
const encoder = new TextEncoder()

/** 按给定的分块（字符串或字节）返回事件流 */
function sse(chunks: (string | Uint8Array)[], init: { status?: number; type?: string } = {}) {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk)
      controller.close()
    },
  })
  return new HttpResponse(body, {
    status: init.status ?? 200, headers: { 'Content-Type': init.type ?? 'text/event-stream; charset=utf-8' },
  })
}

function parse(chunks: string[]): [string, string][] {
  const seen: [string, string][] = []
  const parser = createSseParser((name, data) => seen.push([name, data]))
  for (const chunk of chunks) parser.push(chunk)
  parser.end()
  return seen
}

async function collect(opts: { signal?: AbortSignal } = {}): Promise<StreamEvent[]> {
  const events: StreamEvent[] = []
  await streamMessage('c1', '晚饭吃什么', { ...opts, onEvent: (event) => events.push(event) })
  return events
}

async function caught(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise
  } catch (error) {
    return error
  }
  throw new Error('expected the stream to fail')
}

const DONE = { message_id: 'm1', evidence: '', flags: [], tools_used: [] }

describe('sse parser', () => {
  it('parses events split across chunks', () => {
    expect(parse(['ev', 'ent: del', 'ta\ndata: {"te', 'xt":"今晚"}\n', '\nevent: done\ndata: {}\n\n'])).toEqual([
      ['delta', '{"text":"今晚"}'],
      ['done', '{}'],
    ])
  })

  it('handles crlf and multi line data', () => {
    expect(parse(['event: delta\r\ndata: 第一行\r', '\ndata: 第二行\r\n\r\n', 'data:无空格\r\rdata: x\n\n'])).toEqual([
      ['delta', '第一行\n第二行'],
      ['message', '无空格'],
      ['message', 'x'],
    ])
  })

  it('ignores comments and unknown events', async () => {
    expect(parse([': keep-alive\n\n', 'event: delta\n: 注释\nid: 7\ndata: a\n\n'])).toEqual([['delta', 'a']])
    server.use(http.post(URL, () => sse([
      ': ping\n\n', 'event: progress\ndata: {"step":1}\n\n',
      'event: delta\ndata: {"text":"好"}\n\n', `event: done\ndata: ${JSON.stringify(DONE)}\n\n`,
    ])))
    expect(await collect()).toEqual([{ type: 'delta', text: '好' }, { type: 'done', turn: DONE }])
  })

  it('dispatches a final event without a trailing blank line', () => {
    expect(parse(['event: done\ndata: {}'])).toEqual([['done', '{}']])
    expect(parse(['event: done\ndata: {}\n'])).toEqual([['done', '{}']])
  })

  it('decodes a multi byte character split between chunks', async () => {
    const bytes = encoder.encode('event: delta\ndata: {"text":"清蒸鱼"}\n\n')
    const cut = bytes.indexOf(0xe6) + 1 // “清”的第一个字节之后切开
    server.use(http.post(URL, () => sse([
      bytes.slice(0, cut), bytes.slice(cut), `event: done\ndata: ${JSON.stringify(DONE)}\n\n`,
    ])))
    expect(await collect()).toEqual([{ type: 'delta', text: '清蒸鱼' }, { type: 'done', turn: DONE }])
  })
})

describe('stream message', () => {
  it('posts the text with stream true and the token', async () => {
    setToken('tok-1')
    let seen: { body: unknown; auth: string | null; accept: string | null } | null = null
    server.use(http.post(URL, async ({ request }) => {
      seen = { body: await request.json(), auth: request.headers.get('Authorization'), accept: request.headers.get('Accept') }
      return sse([`event: done\ndata: ${JSON.stringify(DONE)}\n\n`])
    }))
    await collect()
    expect(seen).toEqual({ body: { text: '晚饭吃什么', stream: true }, auth: 'Bearer tok-1', accept: 'text/event-stream' })
  })

  it('reports an error event from a non 200 event stream with its status', async () => {
    server.use(http.post(URL, () => sse(
      ['event: error\ndata: {"code": "agent_model_error", "message": "模型服务暂时不可用"}\n\n'], { status: 502 },
    )))
    expect(await collect()).toEqual([
      { type: 'error', code: 'agent_model_error', message: '模型服务暂时不可用', status: 502 },
    ])
  })

  it('reports a stream error mid way', async () => {
    server.use(http.post(URL, () => sse([
      'event: delta\ndata: {"text":"今晚"}\n\n', 'event: error\ndata: {"code":"x_failed","message":"出错了"}\n\n',
    ])))
    expect(await collect()).toEqual([
      { type: 'delta', text: '今晚' },
      { type: 'error', code: 'x_failed', message: '出错了', status: 200 },
    ])
  })

  it('throws an api error for a non 200 json response', async () => {
    server.use(http.post(URL, () => HttpResponse.json(
      { error: { code: 'not_found', message: '会话不存在' } }, { status: 404 },
    )))
    const error = await caught(collect())
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'not_found', message: '会话不存在' })
  })

  it('clears the token on a 401 json response', async () => {
    setToken('stale')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.post(URL, () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    const error = await caught(collect())
    stop()
    expect(error).toMatchObject({ status: 401, code: 'invalid_token' })
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('clears the token on a 401 inside a non 200 event stream', async () => {
    setToken('stale')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.post(URL, () => sse(
      ['event: error\ndata: {"code":"invalid_token","message":"登录已失效，请重新登录"}\n\n'], { status: 401 },
    )))
    const events: StreamEvent[] = []
    const error = await caught(streamMessage('c1', '晚饭吃什么', { onEvent: (event) => events.push(event) }))
    stop()
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 401, code: 'invalid_token', message: '登录已失效，请重新登录' })
    expect(events).toEqual([])
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('maps a network failure to network_error', async () => {
    server.use(http.post(URL, () => HttpResponse.error()))
    expect(await caught(collect())).toMatchObject({ status: 0, code: 'network_error' })
  })

  it('maps a stream cut off before done to network_error', async () => {
    server.use(http.post(URL, () => sse(['event: delta\ndata: {"text":"今晚"}\n\n'])))
    const events: StreamEvent[] = []
    const error = await caught(streamMessage('c1', '晚饭吃什么', { onEvent: (event) => events.push(event) }))
    expect(events).toEqual([{ type: 'delta', text: '今晚' }])
    expect(error).toMatchObject({ code: 'network_error' })
  })

  it('stops quietly with an abort error when the caller aborts', async () => {
    const stream: { push?: (text: string) => void } = {}
    server.use(http.post(URL, () => new HttpResponse(new ReadableStream<Uint8Array>({
      start(controller) {
        stream.push = (text) => controller.enqueue(encoder.encode(text))
      },
    }), { headers: { 'Content-Type': 'text/event-stream' } })))
    const controller = new AbortController()
    const events: StreamEvent[] = []
    const running = streamMessage('c1', '晚饭吃什么', { signal: controller.signal, onEvent: (event) => events.push(event) })
    await vi.waitFor(() => expect(stream.push).toBeDefined())
    stream.push?.('event: delta\ndata: {"text":"今晚"}\n\n')
    await vi.waitFor(() => expect(events).toHaveLength(1))
    controller.abort()
    const error = await caught(running)
    expect(error).toMatchObject({ name: 'AbortError' })
    expect(events).toEqual([{ type: 'delta', text: '今晚' }])
  })
})
