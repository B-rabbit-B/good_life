// 接口客户端：每个请求带令牌；统一把后端的 {"error": {"code", "message", "details"}} 解析成 ApiError；
// 401 且错误码是 not_authenticated 或 invalid_token 时清令牌并通知监听者（外壳据此回登录页并清缓存）。
// 登录接口的 401 invalid_credentials 不在此列，只由表单提示。
// 自己发 fetch 的模块（流式对话 sse.ts、上传 upload.ts）用 handleErrorResponse 与 networkError 套用同样的规则。
import { ApiError, networkError } from './errors'
import { clearToken, getToken } from './token'

export { ApiError, networkError }

export type ApiMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
export type ApiQuery = Record<string, string | number | boolean | undefined>

export interface ApiInit {
  method?: ApiMethod
  /** 以 JSON 发送（设 Content-Type: application/json） */
  json?: unknown
  /** 原样发送（例如 FormData） */
  body?: BodyInit
  /** 查询参数；值为 undefined 的项不发送 */
  query?: ApiQuery
  signal?: AbortSignal
  /** 默认 true；false 时 401 仍清令牌，但不通知监听者（退出登录用：令牌早已失效也不该显示“登录已过期”） */
  notifyUnauthorized?: boolean
}

const SESSION_ENDED = new Set(['not_authenticated', 'invalid_token'])
const httpMessage = (status: number) => `服务暂时不可用，请稍后再试（HTTP ${status}）`

const unauthorizedListeners = new Set<() => void>()

/** 这个错误码表示登录已失效（not_authenticated 或 invalid_token），应回登录页 */
export function isSessionEnded(code: string): boolean {
  return SESSION_ENDED.has(code)
}

/** 登录失效（401 not_authenticated 或 invalid_token）时调用 listener；返回取消函数。 */
export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener)
  return () => {
    unauthorizedListeners.delete(listener)
  }
}

function buildUrl(path: string, query?: ApiQuery): string {
  const url = new URL(path, window.location.href)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.append(key, String(value))
  }
  return url.toString()
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown
  } catch {
    return undefined
  }
}

function toApiError(status: number, body: unknown): ApiError {
  const error = (body as { error?: unknown } | undefined)?.error as
    | { code?: unknown; message?: unknown; details?: unknown }
    | undefined
  if (error && typeof error.code === 'string' && typeof error.message === 'string') {
    const details = Array.isArray(error.details) ? (error.details as { field: string; message: string }[]) : undefined
    return new ApiError(status, error.code, error.message, details)
  }
  return new ApiError(status, 'http_error', httpMessage(status))
}

function authHeaders(): Headers {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return headers
}

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const headers = authHeaders()
  let body = init.body
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(init.json)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, init.query), {
      method: init.method ?? 'GET', headers, body, signal: init.signal,
    })
  } catch (error) {
    // 主动取消（换页、查询被取消）原样抛出，交给调用方忽略
    if (init.signal?.aborted) throw error
    throw networkError()
  }

  if (response.status === 204) return undefined as T
  if (!response.ok) return handleErrorResponse(response, { notifyUnauthorized: init.notifyUnauthorized })
  const data = await readJson(response)
  if (data === undefined) throw new ApiError(response.status, 'http_error', httpMessage(response.status))
  return data as T
}

/** 取一个文件的字节（照片、医嘱原件）：与 api() 一样带令牌、解析错误、统一网络错误；主动取消原样抛出 */
export async function apiBlob(path: string, signal: AbortSignal): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(buildUrl(path), { headers: authHeaders(), signal })
  } catch (error) {
    if (signal.aborted) throw error
    throw networkError()
  }
  if (!response.ok) return handleErrorResponse(response)
  return response.blob()
}

/**
 * 处理一个非 2xx 的响应：读出后端的统一错误体（读不出时是 http_error），401 登录失效时清令牌并通知监听者，
 * 然后抛出 ApiError。只读一次响应体。
 */
export async function handleErrorResponse(
  response: Response,
  { notifyUnauthorized = true }: { notifyUnauthorized?: boolean } = {},
): Promise<never> {
  const error = toApiError(response.status, await readJson(response))
  if (response.status === 401 && isSessionEnded(error.code)) {
    clearToken()
    if (notifyUnauthorized) for (const listener of [...unauthorizedListeners]) listener()
  }
  throw error
}
