// 医嘱的接口：一个内存里的条目、医嘱单与事件仓库，按后端（app/medical/items.py、orders.py）的规则改动条目，
// 并记下每个请求，供测试核对。errors 里的错误只对那个动作的第一次请求生效。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type {
  EventOut, EvidenceOut, ItemUpdate, ManualItemCreate, MedicalEventOut, MedicalItemOut, OrderCreate, OrderOut,
} from '../../../api/types'

export interface MedicalError {
  status: number
  code: string
  message: string
  details?: { field: string; message: string }[]
}

type Action = 'continue' | 'cancel' | 'confirm' | 'void' | 'resolve' | 'update' | 'addItem' | 'createOrder'

export interface MedicalOptions {
  /** 待处理列表里的条目（只给它时，它们就是全部条目） */
  reviews?: MedicalItemOut[]
  /** 全部条目（给了它时待处理列表按后端规则从这里算出） */
  items?: MedicalItemOut[]
  orders?: OrderOut[]
  /** 每个条目的事件 */
  events?: Record<string, EventOut[]>
  /** 跨条目的审计事件（新的在前） */
  userEvents?: MedicalEventOut[]
  /** continue 的错误（例如 422 still_due）；只对第一次请求生效 */
  continueError?: MedicalError
  /** 各个动作的错误；只对第一次请求生效 */
  errors?: Partial<Record<Action, MedicalError>>
  /** 上传这些文件名的证据时失败一次 */
  uploadErrors?: Record<string, MedicalError>
  /** 录入医嘱时提取出的条目 */
  extract?: (body: OrderCreate) => Partial<MedicalItemOut>[]
}

const HARD = ['active', 'pending_review']
const CLOSED = ['resolved', 'voided']
const errorResponse = ({ status, code, message, details }: MedicalError) =>
  HttpResponse.json({ error: { code, message, ...(details ? { details } : {}) } }, { status })
const notFound = () => errorResponse({ status: 404, code: 'not_found', message: '没有找到' })

export function medicalHandlers(opts: MedicalOptions = {}) {
  let items: MedicalItemOut[] = [...(opts.items ?? opts.reviews ?? [])]
  let orders: OrderOut[] = [...(opts.orders ?? [])]
  const itemEvents: Record<string, EventOut[]> = Object.fromEntries(
    Object.entries(opts.events ?? {}).map(([id, list]) => [id, [...list]]),
  )
  const userEvents: MedicalEventOut[] = [...(opts.userEvents ?? [])]
  const errors: Partial<Record<Action, MedicalError>> = { ...opts.errors, ...(opts.continueError ? { continue: opts.continueError } : {}) }
  const uploadErrors: Record<string, MedicalError> = { ...opts.uploadErrors }
  const evidenceBytes: Record<string, { bytes: ArrayBuffer; type: string }> = {}
  let counter = 0
  const nextId = (prefix: string) => {
    counter += 1
    return `${prefix}-0000-4000-8000-${String(counter).padStart(12, '0')}`
  }

  const record = {
    continues: [] as { id: string; body: unknown }[],
    cancels: [] as string[],
    confirms: [] as { id: string; body: string }[],
    voids: [] as { id: string; body: unknown }[],
    resolves: [] as { id: string; body: string }[],
    updates: [] as { id: string; body: ItemUpdate }[],
    added: [] as { orderId: string; body: ManualItemCreate }[],
    createdOrders: [] as OrderCreate[],
    uploads: [] as { orderId: string; name: string; size: number }[],
    evidenceRequests: [] as string[],
  }

  const take = (action: Action) => {
    const error = errors[action]
    delete errors[action]
    return error
  }
  const find = (id: string) => items.find((item) => item.id === id)
  const replace = (next: MedicalItemOut) => {
    items = items.map((item) => (item.id === next.id ? next : item))
    return next
  }
  const now = () => new Date().toISOString()
  const addEvent = (item: MedicalItemOut, action: string, fromStatus: MedicalItemOut['status'] | null, source: EventOut['source'], detail: EventOut['detail'] = null) => {
    counter += 1
    const event: EventOut = {
      id: nextId('00000000'), seq: 1000 + counter, occurred_at: now(), action, from_status: fromStatus,
      to_status: item.status, source, detail,
    }
    itemEvents[item.id] = [...(itemEvents[item.id] ?? []), event]
    userEvents.unshift({ ...event, item_id: item.id, item_category: item.category, item_content: item.content })
  }
  const reviews = () => items.filter((item) =>
    HARD.includes(item.status) && (item.status === 'pending_review' || item.resolution_proposed_at !== null))
  const orderOut = (o: OrderOut): OrderOut => ({ ...o, items: items.filter((item) => item.order_id === o.id) })
  const readJson = async (request: Request): Promise<unknown> => {
    const text = await request.text()
    return text ? JSON.parse(text) as unknown : undefined
  }

  const handlers: HttpHandler[] = [
    http.get('/api/medical/reviews', () => HttpResponse.json(reviews())),
    http.get('/api/medical/items', () => HttpResponse.json(items)),
    http.get('/api/medical/items/:id/events', ({ params }) => HttpResponse.json(itemEvents[String(params.id)] ?? [])),
    http.get('/api/medical/events', ({ request }) => {
      const limit = Number(new URL(request.url).searchParams.get('limit') ?? 50)
      return HttpResponse.json(userEvents.slice(0, limit))
    }),
    http.get('/api/medical/orders', () => HttpResponse.json(orders.map(orderOut))),
    http.get('/api/medical/constraints', () => HttpResponse.json({ constraints: [], reminder: '' })),

    http.post('/api/medical/orders', async ({ request }) => {
      const body = await request.json() as OrderCreate
      record.createdOrders.push(body)
      const error = take('createOrder')
      if (error) return errorResponse(error)
      const id = nextId('00000000')
      const created: OrderOut = {
        id, order_date: body.order_date ?? new Date().toISOString().slice(0, 10), source_text: body.text,
        extractor: 'rule-based-v1', created_at: now(), ignored: [], notes: [], items: [], evidence: [],
      }
      orders = [created, ...orders]
      for (const fields of opts.extract?.(body) ?? []) {
        const item: MedicalItemOut = {
          id: nextId('00000000'), order_id: id, category: 'diet_avoid', status: 'pending_confirmation', origin: 'extracted',
          confidence: 'high', content: '', subjects: [], source_excerpt: null, start_date: created.order_date, end_date: null,
          review_date: null, missing_fields: [], notes: [], resolution_proposed_at: null, resolution_reason: null,
          confirmed_at: null, closed_at: null, created_at: now(), updated_at: now(), low_confidence: false, ...fields,
        }
        items = [...items, item]
        addEvent(item, 'created', null, 'extractor')
      }
      return HttpResponse.json(orderOut(created), { status: 201 })
    }),
    http.post('/api/medical/orders/:id/evidence', async ({ params, request }) => {
      const orderId = String(params.id)
      const form = await request.formData()
      const file = form.get('file')
      // 请求体由 Node 解析，File 与 jsdom 的不是同一个类：按形状判断
      if (file === null || typeof file === 'string') return errorResponse({ status: 422, code: 'validation_error', message: '请求参数不合法' })
      // 测试环境的 fetch（undici）把 jsdom 的 File 的文件名写成 blob（浏览器不会）：测试文件的内容就是文件名，按内容认
      const name = file.name === 'blob' ? await file.text() : file.name
      record.uploads.push({ orderId, name, size: file.size })
      const error = uploadErrors[name]
      if (error) {
        delete uploadErrors[name]
        return errorResponse(error)
      }
      const target = orders.find((o) => o.id === orderId)
      if (!target) return notFound()
      const created: EvidenceOut = {
        id: nextId('00000000'), filename: name, content_type: file.type || 'image/jpeg', size_bytes: file.size, created_at: now(),
      }
      evidenceBytes[created.id] = { bytes: await file.arrayBuffer(), type: created.content_type }
      orders = orders.map((o) => (o.id === orderId ? { ...o, evidence: [...o.evidence, created] } : o))
      return HttpResponse.json(created, { status: 201 })
    }),
    http.get('/api/medical/evidence/:id', ({ params }) => {
      const id = String(params.id)
      record.evidenceRequests.push(id)
      const stored = evidenceBytes[id] ?? { bytes: new Uint8Array([0xff, 0xd8, 0xff, 0xe0]).buffer, type: 'image/jpeg' }
      return new HttpResponse(stored.bytes, { headers: { 'Content-Type': stored.type } })
    }),
    http.post('/api/medical/orders/:id/items', async ({ params, request }) => {
      const orderId = String(params.id)
      const body = await request.json() as ManualItemCreate
      record.added.push({ orderId, body })
      const error = take('addItem')
      if (error) return errorResponse(error)
      const target = orders.find((o) => o.id === orderId)
      if (!target) return notFound()
      const item: MedicalItemOut = {
        id: nextId('00000000'), order_id: orderId, category: body.category, status: 'pending_confirmation', origin: 'manual',
        confidence: null, content: body.content, subjects: body.subjects ?? [], source_excerpt: null,
        start_date: body.start_date ?? target.order_date, end_date: body.end_date ?? null, review_date: body.review_date ?? null,
        missing_fields: [], notes: [], resolution_proposed_at: null, resolution_reason: null, confirmed_at: null, closed_at: null,
        created_at: now(), updated_at: now(), low_confidence: false,
      }
      items = [...items, item]
      addEvent(item, 'created', null, 'user')
      return HttpResponse.json(item, { status: 201 })
    }),

    http.patch('/api/medical/items/:id', async ({ params, request }) => {
      const id = String(params.id)
      const body = await request.json() as ItemUpdate
      record.updates.push({ id, body })
      const error = take('update')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      if (CLOSED.includes(item.status)) return errorResponse({ status: 409, code: 'item_closed', message: '已解除或已作废的条目不能再修改' })
      const next = replace({ ...item, ...body } as MedicalItemOut)
      addEvent(next, 'edited', next.status, 'user', { fields: Object.keys(body).sort() })
      return HttpResponse.json(next)
    }),
    http.post('/api/medical/items/:id/confirm', async ({ params, request }) => {
      const id = String(params.id)
      record.confirms.push({ id, body: await request.text() })
      const error = take('confirm')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      if (item.status !== 'pending_confirmation') {
        return errorResponse({ status: 409, code: 'invalid_transition', message: '只有待确认的条目可以确认' })
      }
      const next = replace({ ...item, status: 'active', missing_fields: [], confirmed_at: now() })
      addEvent(next, 'confirmed', 'pending_confirmation', 'user')
      return HttpResponse.json(next)
    }),
    http.post('/api/medical/items/:id/void', async ({ params, request }) => {
      const id = String(params.id)
      const body = await readJson(request)
      record.voids.push({ id, body })
      const error = take('void')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      const reason = (body as { reason?: string } | undefined)?.reason
      const next = replace({ ...item, status: 'voided', closed_at: now(), resolution_proposed_at: null, resolution_reason: null })
      addEvent(next, 'voided', item.status, 'user', reason ? { reason } : null)
      return HttpResponse.json(next)
    }),
    http.post('/api/medical/items/:id/resolve', async ({ params, request }) => {
      const id = String(params.id)
      record.resolves.push({ id, body: await request.text() })
      const error = take('resolve')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      if (!HARD.includes(item.status)) {
        return errorResponse({ status: 409, code: 'invalid_transition', message: '只有生效中或待复核的条目可以解除' })
      }
      const next = replace({ ...item, status: 'resolved', closed_at: now(), resolution_proposed_at: null })
      addEvent(next, 'resolved', item.status, 'user', { reason: item.resolution_reason })
      return HttpResponse.json(next)
    }),
    http.post('/api/medical/items/:id/continue', async ({ params, request }) => {
      const id = String(params.id)
      const body = await request.json() as { review_date: string | null; end_date: string | null }
      record.continues.push({ id, body })
      const error = take('continue')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      const next = replace({
        ...item, status: 'active', review_date: body.review_date, end_date: body.end_date,
        resolution_proposed_at: null, resolution_reason: null,
      })
      addEvent(next, 'continued', item.status, 'user', body)
      return HttpResponse.json(next)
    }),
    http.post('/api/medical/items/:id/cancel-proposal', ({ params }) => {
      const id = String(params.id)
      record.cancels.push(id)
      const error = take('cancel')
      if (error) return errorResponse(error)
      const item = find(id)
      if (!item) return notFound()
      const next = replace({ ...item, resolution_proposed_at: null, resolution_reason: null })
      addEvent(next, 'resolution_proposal_cancelled', next.status, 'user')
      return HttpResponse.json(next)
    }),
  ]
  return { handlers, ...record, items: () => items }
}
