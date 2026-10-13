// 上传照片识别：用 XMLHttpRequest 发 multipart（fetch 拿不到上传进度）。令牌、错误解析与 401 的处理与 api() 相同
// （用 client.ts 的 handleErrorResponse 与 networkError）；不设 Content-Type，由浏览器写 multipart 的边界。
// 取消时以 AbortError 拒绝。
import { handleErrorResponse, networkError } from './client'
import { getToken } from './token'
import type { RecognitionOut } from './types'

const URL_PATH = '/api/photos/recognitions'
// 压缩失败时原样上传的文件保留自己的名字；压缩后的是 JPEG
const COMPRESSED_NAME = 'photo.jpg'

/** 上传加识别的整体时限：超过就放弃并按网络失败处理（请求挂住时不让页面一直停在识别中） */
export const UPLOAD_TIMEOUT_MS = 120_000
// 这些状态码的响应不能带响应体（new Response 带了会抛错）
const NULL_BODY_STATUS = new Set([204, 205, 304])

const abortError = () => new DOMException('识别已取消', 'AbortError')

export function uploadRecognition(
  file: Blob,
  keepImage: boolean,
  onProgress: (sent: number, total: number) => void,
  signal?: AbortSignal,
): Promise<RecognitionOut> {
  return new Promise<RecognitionOut>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    const xhr = new XMLHttpRequest()
    const onAbortSignal = () => xhr.abort()
    const done = () => signal?.removeEventListener('abort', onAbortSignal)

    xhr.open('POST', URL_PATH)
    xhr.responseType = 'text'
    xhr.timeout = UPLOAD_TIMEOUT_MS
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded, event.total)
    }
    xhr.onload = () => {
      done()
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as RecognitionOut)
          return
        } catch {
          // 2xx 却不是 JSON：与 api() 一样当作 http_error（handleErrorResponse 读不出错误体时就是它）
        }
      }
      const body = NULL_BODY_STATUS.has(xhr.status) ? null : xhr.responseText
      handleErrorResponse(new Response(body, { status: xhr.status })).catch(reject)
    }
    xhr.onerror = () => {
      done()
      reject(networkError())
    }
    xhr.ontimeout = () => {
      done()
      reject(networkError())
    }
    xhr.onabort = () => {
      done()
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbortSignal, { once: true })

    const form = new FormData()
    form.append('file', file, file instanceof File ? file.name : COMPRESSED_NAME)
    form.append('keep_image', keepImage ? 'true' : 'false')
    xhr.send(form)
  })
}
