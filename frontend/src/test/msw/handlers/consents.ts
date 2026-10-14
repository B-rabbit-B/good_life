// 单独同意的接口：状态在内存里（默认两项都已同意）；同意时核对版本（不是当前版本回 409 consent_outdated），
// 撤回没有有效同意的一项回 404；记下每次同意与撤回。withdrawErrors 依次用于前几次撤回，hold 兑现前撤回不返回，
// grantHold 兑现前同意不返回。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { ConsentKind, ConsentOut } from '../../../api/types'
import { consent, CONSENT_VERSION } from '../../fixtures/consents'

export interface ConsentError {
  status: number
  code: string
  message: string
}

export interface ConsentOptions {
  granted?: Partial<Record<ConsentKind, boolean>>
  withdrawErrors?: ConsentError[]
  hold?: Promise<void>
  grantHold?: Promise<void>
}

const KINDS: readonly ConsentKind[] = ['cycle', 'medical']
const isKind = (value: unknown): value is ConsentKind => KINDS.includes(value as ConsentKind)

export function consentHandlers(opts: ConsentOptions = {}) {
  let consents: ConsentOut[] = KINDS.map((kind) => consent(kind, opts.granted?.[kind] ?? true))
  const withdrawErrors = [...(opts.withdrawErrors ?? [])]
  const record = { grants: [] as { kind: string; version: string }[], withdrawn: [] as string[] }
  const replace = (next: ConsentOut) => {
    consents = consents.map((c) => (c.kind === next.kind ? next : c))
  }

  const handlers: HttpHandler[] = [
    http.get('/api/consents', () => HttpResponse.json(consents)),
    http.post('/api/consents/:kind', async ({ params, request }) => {
      const kind = params.kind
      const { version } = (await request.json()) as { version: string }
      record.grants.push({ kind: String(kind), version })
      await opts.grantHold
      if (!isKind(kind)) return HttpResponse.json({ error: { code: 'validation_error', message: '请求参数不合法' } }, { status: 422 })
      if (version !== CONSENT_VERSION) {
        return HttpResponse.json(
          { error: { code: 'consent_outdated', message: '单独同意的说明已更新，请重新阅读最新版本后同意' } }, { status: 409 },
        )
      }
      const next = consent(kind, true, { granted_at: '2026-10-14T08:00:00Z' })
      replace(next)
      return HttpResponse.json(next)
    }),
    http.post('/api/account/consents/:kind/withdraw', async ({ params }) => {
      const kind = params.kind
      record.withdrawn.push(String(kind))
      await opts.hold
      const error = withdrawErrors.shift()
      if (error) return HttpResponse.json({ error: { code: error.code, message: error.message } }, { status: error.status })
      const current = consents.find((c) => c.kind === kind)
      if (!current?.granted) return HttpResponse.json({ error: { code: 'not_found', message: '记录不存在' } }, { status: 404 })
      replace({ ...current, granted: false, withdrawn_at: '2026-10-14T09:00:00Z' })
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers, record, consents: () => consents }
}
