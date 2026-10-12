import { afterEach, describe, expect, it, vi } from 'vitest'
import { onUnauthorized } from './client'
import { ApiError } from './errors'
import { getToken, setToken } from './token'
import { uploadRecognition } from './upload'
import { recognition } from '../test/fixtures/photos'

/** 假的 XMLHttpRequest：记下请求，测试再手动触发进度、完成与取消 */
class FakeXhr {
  static last: FakeXhr | null = null
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: unknown = null
  status = 0
  responseText = ''
  responseType = ''
  aborted = false
  upload: { onprogress: ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
    onprogress: null,
  }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null

  constructor() {
    FakeXhr.last = this
  }

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }

  send(body: unknown) {
    this.body = body
  }

  abort() {
    this.aborted = true
    this.onabort?.()
  }

  respond(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

function useFakeXhr(): () => FakeXhr {
  FakeXhr.last = null
  vi.stubGlobal('XMLHttpRequest', FakeXhr)
  return () => {
    if (!FakeXhr.last) throw new Error('没有发出请求')
    return FakeXhr.last
  }
}

const photo = () => new Blob(['jpeg-bytes'], { type: 'image/jpeg' })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('upload recognition', () => {
  it('sends file and keep_image as multipart with the token', async () => {
    const xhr = useFakeXhr()
    setToken('upload-token')
    const pending = uploadRecognition(photo(), true, () => {})
    const request = xhr()
    expect(request.method).toBe('POST')
    expect(request.url).toBe('/api/photos/recognitions')
    expect(request.headers.Authorization).toBe('Bearer upload-token')
    // FormData 由浏览器自己写 multipart 的 Content-Type 与边界
    expect(Object.keys(request.headers).map((name) => name.toLowerCase())).not.toContain('content-type')
    expect(request.body).toBeInstanceOf(FormData)
    const form = request.body as FormData
    expect(form.get('keep_image')).toBe('true')
    const file = form.get('file')
    expect(file).toBeInstanceOf(Blob)
    expect(await (file as Blob).text()).toBe('jpeg-bytes')
    const body = recognition()
    request.respond(201, body)
    await expect(pending).resolves.toEqual(body)
  })

  it('sends keep_image false when the photo is not kept', async () => {
    const xhr = useFakeXhr()
    const pending = uploadRecognition(photo(), false, () => {})
    expect((xhr().body as FormData).get('keep_image')).toBe('false')
    xhr().respond(201, recognition())
    await pending
  })

  it('reports upload progress', async () => {
    const xhr = useFakeXhr()
    const progress: [number, number][] = []
    const pending = uploadRecognition(photo(), false, (sent, total) => progress.push([sent, total]))
    xhr().upload.onprogress?.({ lengthComputable: true, loaded: 300, total: 1200 })
    xhr().upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 })
    xhr().upload.onprogress?.({ lengthComputable: true, loaded: 1200, total: 1200 })
    xhr().respond(201, recognition())
    await pending
    expect(progress).toEqual([[300, 1200], [1200, 1200]])
  })

  it('maps a 422 error body to an api error', async () => {
    const xhr = useFakeXhr()
    const pending = uploadRecognition(photo(), false, () => {})
    xhr().respond(422, { error: { code: 'photo_not_food', message: '没有识别到食物，请对准饭菜重拍' } })
    const error = await pending.catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, code: 'photo_not_food', message: '没有识别到食物，请对准饭菜重拍' })
  })

  it('clears the token and notifies on an expired session', async () => {
    const xhr = useFakeXhr()
    setToken('old-token')
    const listener = vi.fn()
    const off = onUnauthorized(listener)
    const pending = uploadRecognition(photo(), false, () => {})
    xhr().respond(401, { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } })
    await expect(pending).rejects.toMatchObject({ status: 401, code: 'invalid_token' })
    expect(getToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
    off()
  })

  it('turns a body that is not the error shape into an http error', async () => {
    const xhr = useFakeXhr()
    const pending = uploadRecognition(photo(), false, () => {})
    const request = xhr()
    request.status = 502
    request.responseText = '<html>bad gateway</html>'
    request.onload?.()
    await expect(pending).rejects.toMatchObject({ status: 502, code: 'http_error' })
  })

  it('turns a failed connection into a network error', async () => {
    const xhr = useFakeXhr()
    const pending = uploadRecognition(photo(), false, () => {})
    xhr().onerror?.()
    await expect(pending).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('rejects with an abort error when cancelled', async () => {
    const xhr = useFakeXhr()
    const controller = new AbortController()
    const pending = uploadRecognition(photo(), false, () => {}, controller.signal)
    controller.abort()
    expect(xhr().aborted).toBe(true)
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not send when the signal is already aborted', async () => {
    const xhr = useFakeXhr()
    const controller = new AbortController()
    controller.abort()
    await expect(uploadRecognition(photo(), false, () => {}, controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
    expect(() => xhr()).toThrow('没有发出请求')
  })
})
