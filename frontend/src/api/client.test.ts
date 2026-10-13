import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../test/msw/server'
import { api, apiBlob, ApiError, handleErrorResponse, isSessionEnded, networkError, onUnauthorized } from './client'
import { getToken, setToken, TOKEN_KEY } from './token'

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('expected the request to fail')
}

describe('api client', () => {
  it('sends the bearer token', async () => {
    setToken('tok-1')
    let seen: string | null = null
    server.use(http.get('/api/auth/me', ({ request }) => {
      seen = request.headers.get('Authorization')
      return HttpResponse.json({ id: 'u1' })
    }))
    await expect(api('/api/auth/me')).resolves.toEqual({ id: 'u1' })
    expect(seen).toBe('Bearer tok-1')
  })

  it('sends json bodies with the json content type', async () => {
    let seen: { type: string | null; body: unknown } | null = null
    server.use(http.post('/api/disclaimer/accept', async ({ request }) => {
      seen = { type: request.headers.get('Content-Type'), body: await request.json() }
      return HttpResponse.json({ accepted: true })
    }))
    await api('/api/disclaimer/accept', { method: 'POST', json: { version: 'v1' } })
    expect(seen).toEqual({ type: 'application/json', body: { version: 'v1' } })
  })

  it('parses the unified error body with details', async () => {
    server.use(http.patch('/api/profile', () => HttpResponse.json({
      error: { code: 'validation_error', message: '请求参数不合法', details: [{ field: 'height_cm', message: '太高了' }] },
    }, { status: 422 })))
    const error = await caught(api('/api/profile', { method: 'PATCH', json: { height_cm: 400 } }))
    expect(error.status).toBe(422)
    expect(error.code).toBe('validation_error')
    expect(error.message).toBe('请求参数不合法')
    expect(error.details).toEqual([{ field: 'height_cm', message: '太高了' }])
  })

  it('maps a non json error to http_error', async () => {
    server.use(http.get('/api/auth/me', () => new HttpResponse('<html>bad gateway</html>', {
      status: 502, headers: { 'Content-Type': 'text/html' },
    })))
    const error = await caught(api('/api/auth/me'))
    expect(error.status).toBe(502)
    expect(error.code).toBe('http_error')
    expect(error.message).toBe('服务暂时不可用，请稍后再试（HTTP 502）')
  })

  it('maps a network failure to network_error', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.error()))
    const error = await caught(api('/api/auth/me'))
    expect(error.status).toBe(0)
    expect(error.code).toBe('network_error')
    expect(error.message).toBe('网络连接失败，请检查网络后重试')
  })

  it('clears the token and notifies on invalid_token', async () => {
    setToken('stale')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.get('/api/profile', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    const error = await caught(api('/api/profile'))
    stop()
    expect(error.code).toBe('invalid_token')
    expect(getToken()).toBeNull()
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('clears the token and notifies on not_authenticated', async () => {
    setToken('stale')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.get('/api/auth/me', () => HttpResponse.json(
      { error: { code: 'not_authenticated', message: '请先登录' } }, { status: 401 },
    )))
    const error = await caught(api('/api/auth/me'))
    stop()
    expect(error.code).toBe('not_authenticated')
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('can clear the token without notifying', async () => {
    setToken('revoked')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.post('/api/auth/logout', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    const error = await caught(api('/api/auth/logout', { method: 'POST', notifyUnauthorized: false }))
    stop()
    expect(error.code).toBe('invalid_token')
    expect(getToken()).toBeNull()
    expect(listener).not.toHaveBeenCalled()
  })

  it('shares the error rules with modules that fetch by themselves', async () => {
    expect(isSessionEnded('invalid_token')).toBe(true)
    expect(isSessionEnded('not_authenticated')).toBe(true)
    expect(isSessionEnded('invalid_credentials')).toBe(false)
    expect(networkError()).toMatchObject({ status: 0, code: 'network_error', message: '网络连接失败，请检查网络后重试' })

    setToken('stale')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    const expired = new Response(JSON.stringify({ error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }),
      { status: 401, headers: { 'Content-Type': 'application/json' } })
    const error = await caught(handleErrorResponse(expired))
    expect(error.code).toBe('invalid_token')
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
    stop()

    const html = await caught(handleErrorResponse(new Response('<html></html>', { status: 503 })))
    expect([html.status, html.code, html.message]).toEqual([503, 'http_error', '服务暂时不可用，请稍后再试（HTTP 503）'])
  })

  it('does not clear the token on invalid_credentials', async () => {
    setToken('keep-me')
    const listener = vi.fn()
    const stop = onUnauthorized(listener)
    server.use(http.post('/api/auth/login', () => HttpResponse.json(
      { error: { code: 'invalid_credentials', message: '用户名或密码错误' } }, { status: 401 },
    )))
    const error = await caught(api('/api/auth/login', { method: 'POST', json: { username: 'a', password: 'b' } }))
    stop()
    expect(error.code).toBe('invalid_credentials')
    expect(getToken()).toBe('keep-me')
    expect(listener).not.toHaveBeenCalled()
  })

  it('returns undefined for 204', async () => {
    server.use(http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })))
    await expect(api('/api/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('serialises query parameters and skips undefined', async () => {
    let query = ''
    server.use(http.get('/api/medical/events', ({ request }) => {
      query = new URL(request.url).search
      return HttpResponse.json([])
    }))
    await api('/api/medical/events', { query: { limit: 50, client_name: undefined, all: true, q: '低盐 饮食' } })
    const params = new URLSearchParams(query)
    expect([...params.keys()]).toEqual(['limit', 'all', 'q'])
    expect(params.get('limit')).toBe('50')
    expect(params.get('all')).toBe('true')
    expect(params.get('q')).toBe('低盐 饮食')
  })

  it('keeps an aborted request as an abort', async () => {
    server.use(http.get('/api/auth/me', async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
      return HttpResponse.json({})
    }))
    const controller = new AbortController()
    const request = api('/api/auth/me', { signal: controller.signal })
    controller.abort()
    await expect(request).rejects.not.toBeInstanceOf(ApiError)
  })
})

describe('token storage', () => {
  it('survives a storage that throws', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(getToken()).toBeNull()
    spy.mockRestore()
  })
})

describe('api blob', () => {
  it('fetches bytes with the bearer token', async () => {
    setToken('tok-blob')
    let seen: string | null = null
    server.use(http.get('/api/photos/recognitions/r1/image', ({ request }) => {
      seen = request.headers.get('Authorization')
      return new HttpResponse(new Uint8Array([1, 2, 3]), { headers: { 'Content-Type': 'image/jpeg' } })
    }))
    const blob = await apiBlob('/api/photos/recognitions/r1/image', new AbortController().signal)
    expect(seen).toBe('Bearer tok-blob')
    expect(blob.size).toBe(3)
  })

  it('parses the unified error body and clears an ended session', async () => {
    setToken('tok-old')
    const listener = vi.fn()
    const off = onUnauthorized(listener)
    server.use(http.get('/api/medical/evidence/e1', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效' } }, { status: 401 },
    )))
    const error = await caught(apiBlob('/api/medical/evidence/e1', new AbortController().signal))
    off()
    expect(error).toMatchObject({ status: 401, code: 'invalid_token' })
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('gives the network error when fetch is rejected and rethrows an abort', async () => {
    server.use(http.get('/api/medical/evidence/e2', () => HttpResponse.error()))
    expect(await caught(apiBlob('/api/medical/evidence/e2', new AbortController().signal))).toMatchObject({ code: 'network_error' })
    const controller = new AbortController()
    controller.abort()
    await expect(apiBlob('/api/medical/evidence/e2', controller.signal)).rejects.not.toBeInstanceOf(ApiError)
  })
})
