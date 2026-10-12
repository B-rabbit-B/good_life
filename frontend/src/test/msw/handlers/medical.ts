// 医嘱的接口（对话页用到的部分）：待处理列表、条目、事件、继续遵守、不解除。
// continue 与 cancel-proposal 按后端的规则改动内存里的条目，并记下请求体，供测试核对。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { EventOut, MedicalItemOut } from '../../../api/types'

export interface MedicalOptions {
  reviews?: MedicalItemOut[]
  /** 每个条目的事件 */
  events?: Record<string, EventOut[]>
  /** continue 的错误（例如 422 still_due）；只对第一次请求生效 */
  continueError?: { status: number; code: string; message: string }
}

export function medicalHandlers(opts: MedicalOptions = {}) {
  let reviews = [...(opts.reviews ?? [])]
  const continues: { id: string; body: unknown }[] = []
  const cancels: string[] = []
  let continueError = opts.continueError
  const items = () => reviews
  const handlers: HttpHandler[] = [
    http.get('/api/medical/reviews', () => HttpResponse.json(reviews)),
    http.get('/api/medical/items', () => HttpResponse.json(items())),
    http.get('/api/medical/items/:id/events', ({ params }) => HttpResponse.json(opts.events?.[String(params.id)] ?? [])),
    http.post('/api/medical/items/:id/continue', async ({ params, request }) => {
      const id = String(params.id)
      continues.push({ id, body: await request.json() })
      if (continueError) {
        const { status, code, message } = continueError
        continueError = undefined
        return HttpResponse.json({ error: { code, message } }, { status })
      }
      const item = reviews.find((i) => i.id === id)
      reviews = reviews.filter((i) => i.id !== id)
      return HttpResponse.json({ ...item, status: 'active' })
    }),
    http.post('/api/medical/items/:id/cancel-proposal', ({ params }) => {
      const id = String(params.id)
      cancels.push(id)
      const item = reviews.find((i) => i.id === id)
      reviews = reviews.filter((i) => i.id !== id || i.status === 'pending_review')
      return HttpResponse.json({ ...item, resolution_proposed_at: null, resolution_reason: null })
    }),
    http.get('/api/medical/constraints', () => HttpResponse.json({ constraints: [], reminder: '' })),
  ]
  return { handlers, continues, cancels }
}
