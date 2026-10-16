// 经期与医嘱两类敏感信息的单独同意：状态、同意、撤回，以及“模块可用”（能力清单开放且已同意）。
// 后端的能力清单不反映同意；未同意时这两个模块的接口回 403 consent_required，所以入口与查询都看 useModuleReady。
// 对话页的待处理条经 medical.ts 用到这里：只放钩子，保持很小。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { discardDomain, invalidateDomain } from '../invalidation'
import { qk } from '../keys'
import type { ConsentKind, ConsentOut } from '../types'
import { useCapabilities } from './profile'

/** 两项同意的状态（顺序同后端：经期、医嘱），每项带标题、正文与当前版本 */
export function useConsents(enabled = true) {
  return useQuery({
    queryKey: qk.consents,
    queryFn: ({ signal }) => api<ConsentOut[]>('/api/consents', { signal }),
    enabled,
  })
}

/**
 * 模块的状态：ready 是能力清单开放且已单独同意；closed 是没开放、没同意或读不到同意状态；pending 是同意状态还在读。
 * 能力清单没开放时不请求同意状态。需要“等结论再画”的页面（对话页等待处理列表）用它区分“还在读”与“不可用”。
 */
export function useModuleConsent(kind: ConsentKind): 'ready' | 'closed' | 'pending' {
  const caps = useCapabilities()
  const open = caps.data?.[kind] === true
  const consents = useConsents(open)
  if (!open) return 'closed'
  // 已有结论时后台重取失败不改结论；从来没读到才算不可用
  if (consents.data === undefined) return consents.isError ? 'closed' : 'pending'
  return consents.data.some((consent) => consent.kind === kind && consent.granted) ? 'ready' : 'closed'
}

/** 模块能不能用：能力清单开放了这个模块，并且已经单独同意 */
export function useModuleReady(kind: ConsentKind): boolean {
  return useModuleConsent(kind) === 'ready'
}

/** 同意页面上显示的那个版本；成功后重新取同意状态与该模块的数据域 */
export function useGrantConsent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, version }: { kind: ConsentKind; version: string }) =>
      api<ConsentOut>(`/api/consents/${kind}`, { method: 'POST', json: { version } }),
    onSuccess: async (_consent, { kind }) => {
      await queryClient.invalidateQueries({ queryKey: qk.consents })
      await invalidateDomain(queryClient, kind)
    },
  })
}

/**
 * 撤回：后端在同一个事务里清除该模块的全部数据并关闭模块。成功后先重新取同意状态（模块的查询随之停用），
 * 再按失效表把该域与跟着变的缓存丢掉、已取过的开场问候改成“没有开场”（见 invalidation.ts 的 discardDomain）。
 */
export function useWithdrawConsent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (kind: ConsentKind) => api<void>(`/api/account/consents/${kind}/withdraw`, { method: 'POST' }),
    onSuccess: async (_result, kind) => {
      await queryClient.invalidateQueries({ queryKey: qk.consents })
      await discardDomain(queryClient, kind)
    },
  })
}
