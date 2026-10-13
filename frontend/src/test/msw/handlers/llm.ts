// 模型服务的接口，按后端的规则模拟：服务与模型在内存里；同名 409 llm_provider_exists，地址不是 http(s) 时 422 llm_invalid_url，
// 改了地址的主机却没重填密钥时 422 llm_key_required_for_new_url；获取模型时密钥是 BAD_KEY 就 400 llm_invalid_key；
// 返回的服务只带密钥掩码 key_hint。fetchErrors 与 testReports 依次用于前几次获取与测试；记下每次请求。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { AssignmentOut, ConnectionReportOut, ModelOut, ProviderOut } from '../../../api/types'
import { BAD_KEY, fetchedModels, INVALID_KEY_MESSAGE, keyHint, model, okReport, PRESETS } from '../../fixtures/llm'

export interface LlmError {
  status: number
  code: string
  message: string
}

export interface LlmOptions {
  providers?: ProviderOut[]
  assignments?: AssignmentOut[]
  /** 已有服务的模型（按服务编号） */
  models?: Record<string, ModelOut[]>
  /** 新服务获取到的模型；默认 fetchedModels */
  fetched?: (providerId: string) => ModelOut[]
  fetchErrors?: LlmError[]
  testReports?: ConnectionReportOut[]
  testErrors?: LlmError[]
  /** 按用途的分配错误（每次都返回） */
  assignErrors?: Partial<Record<'chat' | 'vision', LlmError>>
  /** 改能力标注时附带的提醒 */
  warnings?: string[]
  hold?: { create?: Promise<void>; test?: Promise<void> }
}

const errorResponse = ({ status, code, message }: LlmError) => HttpResponse.json({ error: { code, message } }, { status })
const host = (url: string) => {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

export function llmHandlers(opts: LlmOptions = {}) {
  let providers = [...(opts.providers ?? [])]
  let assignments = [...(opts.assignments ?? [])]
  const models: Record<string, ModelOut[]> = { ...(opts.models ?? {}) }
  const keys: Record<string, string> = {}
  const fetchErrors = [...(opts.fetchErrors ?? [])]
  const testReports = [...(opts.testReports ?? [])]
  const testErrors = [...(opts.testErrors ?? [])]
  let counter = 0
  const record = {
    creates: [] as unknown[],
    updates: [] as { id: string; body: Record<string, unknown> }[],
    fetches: [] as string[],
    tests: [] as { id: string; body: unknown }[],
    overrides: [] as { pk: string; body: unknown }[],
    assigns: [] as { purpose: string; body: unknown }[],
    manual: [] as unknown[],
  }
  const allModels = () => Object.values(models).flat()

  const handlers: HttpHandler[] = [
    http.get('/api/llm/presets', () => HttpResponse.json(PRESETS)),
    http.get('/api/llm/providers', () => HttpResponse.json(providers)),
    http.post('/api/llm/providers', async ({ request }) => {
      const body = await request.json() as { name: string; kind: ProviderOut['kind']; base_url: string; api_key: string }
      record.creates.push(body)
      await opts.hold?.create
      if (!/^https?:\/\//.test(body.base_url)) {
        return errorResponse({ status: 422, code: 'llm_invalid_url', message: '服务地址要以 http:// 或 https:// 开头' })
      }
      if (providers.some((p) => p.name === body.name)) {
        return errorResponse({ status: 409, code: 'llm_provider_exists', message: '已有同名的模型服务，请换一个名称或直接修改原来的服务' })
      }
      counter += 1
      const created: ProviderOut = {
        id: `73000000-0000-4000-8000-${String(counter).padStart(12, '0')}`, name: body.name, kind: body.kind,
        base_url: body.base_url, key_hint: keyHint(body.api_key),
        created_at: '2026-10-12T08:00:00Z', updated_at: '2026-10-12T08:00:00Z',
      }
      keys[created.id] = body.api_key
      providers = [...providers, created]
      return HttpResponse.json(created, { status: 201 })
    }),
    http.patch('/api/llm/providers/:id', async ({ request, params }) => {
      const id = String(params.id)
      const body = await request.json() as { name?: string; base_url?: string; api_key?: string }
      record.updates.push({ id, body })
      const current = providers.find((p) => p.id === id)
      if (!current) return errorResponse({ status: 404, code: 'not_found', message: '没有找到' })
      if (body.base_url && !body.api_key && host(body.base_url) !== host(current.base_url)) {
        return errorResponse({ status: 422, code: 'llm_key_required_for_new_url', message: '服务地址的协议、主机或端口变了，请重新填写密钥' })
      }
      const next: ProviderOut = {
        ...current, ...(body.name ? { name: body.name } : {}), ...(body.base_url ? { base_url: body.base_url } : {}),
        ...(body.api_key ? { key_hint: keyHint(body.api_key) } : {}),
      }
      if (body.api_key) keys[id] = body.api_key
      providers = providers.map((p) => (p.id === id ? next : p))
      return HttpResponse.json(next)
    }),
    http.delete('/api/llm/providers/:id', ({ params }) => {
      providers = providers.filter((p) => p.id !== String(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
    http.post('/api/llm/providers/:id/fetch-models', ({ params }) => {
      const id = String(params.id)
      record.fetches.push(id)
      const error = fetchErrors.shift()
      if (error) return errorResponse(error)
      if (keys[id] === BAD_KEY) return errorResponse({ status: 400, code: 'llm_invalid_key', message: INVALID_KEY_MESSAGE })
      const listed = (opts.fetched ?? fetchedModels)(id)
      const known = models[id] ?? []
      models[id] = [...known, ...listed.filter((m) => !known.some((k) => k.model_id === m.model_id))]
      return HttpResponse.json({ added: listed.length, total: listed.length, skipped: 0, models: models[id] })
    }),
    http.get('/api/llm/providers/:id/models', ({ params }) => HttpResponse.json(models[String(params.id)] ?? [])),
    http.post('/api/llm/providers/:id/models', async ({ request, params }) => {
      const id = String(params.id)
      const body = await request.json() as { model_id: string }
      record.manual.push(body)
      const added = model(id, body.model_id, { vision: null, tools: null, chat: null }, { source: 'manual' })
      models[id] = [...(models[id] ?? []), added]
      return HttpResponse.json(added, { status: 201 })
    }),
    http.post('/api/llm/providers/:id/test', async ({ request, params }) => {
      const id = String(params.id)
      const body = await request.json() as { model_id?: string }
      record.tests.push({ id, body })
      await opts.hold?.test
      const error = testErrors.shift()
      if (error) return errorResponse(error)
      return HttpResponse.json(testReports.shift() ?? okReport(body.model_id ?? ''))
    }),
    http.patch('/api/llm/models/:pk', async ({ request, params }) => {
      const pk = String(params.pk)
      const body = await request.json() as Partial<Record<'vision' | 'tools' | 'chat', boolean | null>>
      record.overrides.push({ pk, body })
      const current = allModels().find((m) => m.id === pk)
      if (!current) return errorResponse({ status: 404, code: 'not_found', message: '没有找到' })
      const overrides = { ...current.overrides, ...body }
      const effective = (name: 'vision' | 'tools' | 'chat') => overrides[name] ?? current.table_capabilities[name]
      const next: ModelOut = {
        ...current, overrides, capabilities: { vision: effective('vision'), tools: effective('tools'), chat: effective('chat') },
      }
      models[current.provider_id] = (models[current.provider_id] ?? []).map((m) => (m.id === pk ? next : m))
      return HttpResponse.json({ ...next, assignment_warnings: opts.warnings ?? [] })
    }),
    http.get('/api/llm/assignments', () => HttpResponse.json(assignments)),
    http.put('/api/llm/assignments/:purpose', async ({ request, params }) => {
      const purpose = String(params.purpose) as 'chat' | 'vision'
      const body = await request.json() as { model_id: string }
      record.assigns.push({ purpose, body })
      const error = opts.assignErrors?.[purpose]
      if (error) return errorResponse(error)
      const target = allModels().find((m) => m.id === body.model_id)
      if (!target) return errorResponse({ status: 404, code: 'not_found', message: '没有找到这个模型' })
      const name = providers.find((p) => p.id === target.provider_id)?.name ?? ''
      const next: AssignmentOut = { purpose, model: target, provider_name: name }
      assignments = [...assignments.filter((a) => a.purpose !== purpose), next]
      return HttpResponse.json(next)
    }),
  ]
  return { handlers, record }
}
