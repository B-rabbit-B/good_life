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
