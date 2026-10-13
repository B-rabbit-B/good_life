/** 后端返回的错误：状态码、错误码、说明原文与字段级说明。界面只原样显示 message 与 code，不做判断。 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, details?: { field: string; message: string }[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    if (details !== undefined) this.details = details
  }
}

const NETWORK_MESSAGE = '网络连接失败，请检查网络后重试'
const UNKNOWN_MESSAGE = '出了点问题，请稍后再试'

/** 网络失败（fetch 本身被拒绝、且不是主动取消）时的统一错误 */
export function networkError(): ApiError {
  return new ApiError(0, 'network_error', NETWORK_MESSAGE)
}

/**
 * 把捕获到的任何东西变成 ApiError 交给界面：ApiError 原样返回；fetch 被拒绝（TypeError）给网络错误；
 * 其余给 unknown_error（说明用中文，不显示原始异常文字）。
 */
export function asApiError(caught: unknown): ApiError {
  if (caught instanceof ApiError) return caught
  if (caught instanceof TypeError) return networkError()
  return new ApiError(0, 'unknown_error', UNKNOWN_MESSAGE)
}
