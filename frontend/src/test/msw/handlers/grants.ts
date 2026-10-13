// 外部授权与调用审计的接口：授权在内存里，吊销后状态变为 revoked（再吊销是 404）；审计按 limit 与 client_name 筛选。
// 记下每次吊销与审计请求的参数；revokeErrors 依次用于前几次吊销，hold 兑现前吊销不返回。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { AuditOut, GrantOut } from '../../../api/types'
import { AUDITS, GRANTS } from '../../fixtures/grants'

export interface GrantError {
  status: number
  code: string
  message: string
}

export function grantHandlers(opts: { grants?: GrantOut[]; audits?: AuditOut[]; revokeErrors?: GrantError[]; hold?: Promise<void> } = {}) {
  let grants = [...(opts.grants ?? GRANTS)]
  const audits = opts.audits ?? AUDITS
  const revokeErrors = [...(opts.revokeErrors ?? [])]
  const record = { revoked: [] as string[], auditQueries: [] as { limit: string | null; client_name: string | null }[] }

  const handlers: HttpHandler[] = [
    http.get('/api/agent-grants', () => HttpResponse.json(grants)),
    http.delete('/api/agent-grants/:id', async ({ params }) => {
      const id = String(params.id)
      record.revoked.push(id)
      await opts.hold
      const error = revokeErrors.shift()
      if (error) return HttpResponse.json({ error: { code: error.code, message: error.message } }, { status: error.status })
      grants = grants.map((g) => (g.id === id ? { ...g, status: 'revoked', revoked_at: '2026-10-12T10:00:00Z' } : g))
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/agent-grants/audit', ({ request }) => {
      const params = new URL(request.url).searchParams
      const limit = params.get('limit')
      const client = params.get('client_name')
      record.auditQueries.push({ limit, client_name: client })
      const rows = audits.filter((a) => client === null || a.client_name === client)
      return HttpResponse.json(rows.slice(0, Number(limit ?? 50)))
    }),
  ]
  return { handlers, record }
}
