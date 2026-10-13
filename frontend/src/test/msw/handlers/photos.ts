// 拍照识别的接口：一个内存里的识别记录仓库，按后端的规则模拟识别、修正、确认、放弃与取图；
// 记下修正与确认的请求体、取图的请求，供测试核对。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { PhotoItemIn, PhotoItemOut, RecognitionOut } from '../../../api/types'
import { nutrients } from '../../fixtures/photos'

export interface PhotosOptions {
  /** 仓库里已有的识别记录 */
  records?: RecognitionOut[]
  /** POST 识别的结果：一条记录（加入仓库），或后端的错误 */
  create?: RecognitionOut | { status: number; code: string; message: string }
  /** 有值时 POST 识别要等它兑现才回应（测试“识别中”的样子） */
  hold?: Promise<void>
  /** confirm 的错误；只对第一次请求生效 */
  confirmError?: { status: number; code: string; message: string }
  /** 删除的错误；每次请求都返回 */
  deleteError?: { status: number; code: string; message: string }
  /** 取图的错误（只对保留了图片的记录）；每次请求都返回 */
  imageError?: { status: number; code: string; message: string }
}

const error = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status })
const notEditable = () => error(409, 'photo_not_editable',
  '这条识别记录已经确认入库或已放弃，不能再修改或确认；需要调整时请到饮食记录里修改，或重新拍照识别')

/** 简化的 app/photos/service.py::_revise：带 food_id 的项改为已匹配，改了克数的项不再是估算 */
function revise(change: PhotoItemIn, previous: PhotoItemOut): PhotoItemOut {
  const next: PhotoItemOut = {
    ...previous,
    name: change.name,
    portion_text: change.portion_text ?? previous.portion_text,
    grams: change.grams ?? previous.grams,
  }
  if (change.grams != null) {
    next.grams_source = 'user'
    next.review_reasons = next.review_reasons.filter((reason) => reason !== 'estimated_grams')
  }
  if (change.food_id && change.food_id !== previous.food_id) {
    const picked = previous.candidates.find((candidate) => candidate.food_id === change.food_id)
    Object.assign(next, {
      status: 'matched', food_id: change.food_id, food_name: picked?.name ?? change.food_id, match_type: 'user_selected',
      candidates: [], nutrients: nutrients({ energy_kcal: 180 }), confidence: 1,
    })
    next.review_reasons = next.review_reasons.filter((reason) => reason !== 'needs_confirmation')
  }
  return next
}

export function photosHandlers(opts: PhotosOptions = {}) {
  const records = new Map<string, RecognitionOut>((opts.records ?? []).map((record) => [record.id, record]))
  const updates: { id: string; body: { items: PhotoItemIn[] } }[] = []
  const confirms: { id: string; body: unknown }[] = []
  const discards: string[] = []
  const imageRequests: string[] = []
  const creates: number[] = []
  const deletes: string[] = []
  let listRequests = 0
  let confirmError = opts.confirmError

  const handlers: HttpHandler[] = [
    http.post('/api/photos/recognitions', async () => {
      creates.push(Date.now())
      if (opts.hold) await opts.hold
      const result = opts.create
      if (!result) return error(409, 'llm_not_configured', '还没有设置看图识别用的模型，请先到设置页添加模型服务并选择看图模型')
      if ('code' in result) return error(result.status, result.code, result.message)
      records.set(result.id, result)
      return HttpResponse.json(result, { status: 201 })
    }),
    http.get('/api/photos/recognitions', () => {
      listRequests += 1
      return HttpResponse.json([...records.values()].map((record) => {
        const summary: Partial<RecognitionOut> = { ...record }
        delete summary.evaluation // 列表不带评价
        return summary
      }))
    }),
    http.delete('/api/photos/recognitions/:id', ({ params }) => {
      const id = String(params.id)
      deletes.push(id)
      if (opts.deleteError) return error(opts.deleteError.status, opts.deleteError.code, opts.deleteError.message)
      if (!records.delete(id)) return error(404, 'not_found', '记录不存在')
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/photos/recognitions/:id', ({ params }) => {
      const record = records.get(String(params.id))
      return record ? HttpResponse.json(record) : error(404, 'not_found', '记录不存在')
    }),
    http.put('/api/photos/recognitions/:id/items', async ({ params, request }) => {
      const id = String(params.id)
      const body = (await request.json()) as { items: PhotoItemIn[] }
      updates.push({ id, body })
      const record = records.get(id)
      if (!record) return error(404, 'not_found', '记录不存在')
      if (record.status !== 'draft') return notEditable()
      const previous = new Map(record.items.map((item) => [item.id, item]))
      const items = body.items.map((change) => {
        const before = change.id ? previous.get(change.id) : undefined
        if (!before) throw new Error(`测试的处理器不支持新增识别项：${change.name}`)
        return revise(change, before)
      })
      const next = { ...record, items, needs_review: items.some((item) => item.review_reasons.length > 0) }
      records.set(id, next)
      return HttpResponse.json(next)
    }),
    http.post('/api/photos/recognitions/:id/confirm', async ({ params, request }) => {
      const id = String(params.id)
      const body = (await request.json()) as { eaten_on: string; meal_type: RecognitionOut['meal_type'] }
      confirms.push({ id, body })
      const record = records.get(id)
      if (!record) return error(404, 'not_found', '记录不存在')
      if (record.status !== 'draft') return notEditable()
      if (confirmError) {
        const { status, code, message } = confirmError
        confirmError = undefined
        return error(status, code, message)
      }
      if (record.items.some((item) => item.status !== 'matched')) {
        return error(422, 'photo_items_need_confirmation',
          '还有待确认的菜品：请先从候选里选择对应的食物、改成营养库里有的名称，或删除这一项，再确认入库')
      }
      const next: RecognitionOut = {
        ...record, status: 'confirmed', eaten_on: body.eaten_on, meal_type: body.meal_type, evaluation: null,
        meal_entry_ids: record.items.map((_, i) => `00000000-0000-4000-8000-3000000000${String(i).padStart(2, '0')}`),
      }
      records.set(id, next)
      return HttpResponse.json(next)
    }),
    http.post('/api/photos/recognitions/:id/discard', ({ params }) => {
      const id = String(params.id)
      discards.push(id)
      const record = records.get(id)
      if (!record) return error(404, 'not_found', '记录不存在')
      if (record.status !== 'draft') return notEditable()
      const next: RecognitionOut = { ...record, status: 'discarded', evaluation: null }
      records.set(id, next)
      return HttpResponse.json(next)
    }),
    http.get('/api/photos/recognitions/:id/image', ({ params }) => {
      const id = String(params.id)
      imageRequests.push(id)
      const record = records.get(id)
      if (record?.image_kept && opts.imageError) {
        return error(opts.imageError.status, opts.imageError.code, opts.imageError.message)
      }
      if (!record?.image_kept) {
        return error(404, 'photo_image_not_kept', '这次识别没有保留图片（默认不保留）；需要保留时请在上传时选择“保留图片”')
      }
      return new HttpResponse(new Uint8Array([0xff, 0xd8, 0xff, 0xd9]), { headers: { 'Content-Type': 'image/jpeg' } })
    }),
  ]
  return {
    handlers, records, updates, confirms, discards, imageRequests, creates, deletes,
    /** GET 列表的次数 */
    listRequests: () => listRequests,
  }
}
