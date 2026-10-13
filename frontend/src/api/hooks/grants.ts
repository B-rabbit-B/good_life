// 外部授权与调用审计（隐私与数据页）：授权列表、吊销、审计记录（可按客户端名筛选）。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { AuditOut, GrantOut } from '../types'

const base = '/api/agent-grants'
/** 不筛选时取最近 200 条（筛选胶囊的客户端名从这里来），筛选时取 50 条 */
export const AUDIT_ALL_LIMIT = 200
export const AUDIT_FILTERED_LIMIT = 50

export function useGrants() {
  return useQuery({ queryKey: qk.grants, queryFn: ({ signal }) => api<GrantOut[]>(base, { signal }) })
}

/** 吊销一个授权；完成后重新读取授权列表 */
export function useRevokeGrant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`${base}/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.grants }),
  })
}

/** 调用审计：clientName 为空时取最近 200 条，否则只取这个客户端的最近 50 条 */
export function useAudits(clientName?: string) {
  return useQuery({
    queryKey: qk.audits(clientName),
    queryFn: ({ signal }) => api<AuditOut[]>(`${base}/audit`, {
      query: clientName ? { limit: AUDIT_FILTERED_LIMIT, client_name: clientName } : { limit: AUDIT_ALL_LIMIT },
      signal,
    }),
  })
}
