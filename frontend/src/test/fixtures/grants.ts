// 外部授权与调用审计的测试数据：两个授权（一个有效、一个已吊销），审计里有应用内助手（agent）与一个外部客户端的调用。
import type { AuditOut, GrantOut } from '../../api/types'

export function grant(over: Partial<GrantOut> = {}): GrantOut {
  return {
    id: '74000000-0000-4000-8000-000000000001',
    name: '我的笔记应用',
    access: 'read',
    status: 'active',
    expires_at: '2026-12-31T08:00:00Z',
    created_at: '2026-10-01T08:00:00Z',
    revoked_at: null,
    last_used_at: '2026-10-11T12:30:00Z',
    ...over,
  }
}

export const GRANTS: GrantOut[] = [
  grant(),
  grant({
    id: '74000000-0000-4000-8000-000000000002', name: '旧的同步脚本', access: 'read_write', status: 'revoked',
    revoked_at: '2026-10-05T08:00:00Z', last_used_at: null,
  }),
]

export function audit(over: Partial<AuditOut> = {}): AuditOut {
  return {
    id: '75000000-0000-4000-8000-000000000001',
    grant_id: null,
    credential_kind: 'user',
    client_name: 'agent',
    capability: 'nutrition.log_meal',
    outcome: 'ok',
    error_code: null,
    duration_ms: 42,
    created_at: '2026-10-12T09:15:00Z',
    ...over,
  }
}

export const AUDITS: AuditOut[] = [
  audit(),
  audit({
    id: '75000000-0000-4000-8000-000000000002', grant_id: GRANTS[0]?.id ?? null, credential_kind: 'grant',
    client_name: 'notes-app', capability: 'nutrition.daily_summary', outcome: 'error', error_code: 'forbidden',
    duration_ms: 7, created_at: '2026-10-12T08:00:00Z',
  }),
  audit({ id: '75000000-0000-4000-8000-000000000003', capability: 'medical.list_constraints', duration_ms: 118, created_at: '2026-10-11T20:00:00Z' }),
]
