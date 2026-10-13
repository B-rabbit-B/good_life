import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { invalidateDomain } from '../invalidation'
import { qk } from '../keys'
import type { EventOut, MedicalItemOut } from '../types'
import { useCapabilities } from './profile'

// 对话页也用的部分（待处理列表、条目与事件、继续遵守、不解除）放在这里；只有医嘱页用的（医嘱单、证据、修改、确认、
// 作废、解除、审计）在 medicalPage.ts，免得进对话页的首屏。
export const base = '/api/medical'

/** 需要本人处理的条目：待复核的，以及仍在生效但带着解除建议的（只在医嘱模块开放时请求） */
export function useMedicalReviews() {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.reviews,
    queryFn: ({ signal }) => api<MedicalItemOut[]>(`${base}/reviews`, { signal }),
    enabled: caps.data?.medical === true,
  })
}

/** 全部医嘱条目 */
export function useMedicalItems() {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.medicalItems,
    queryFn: ({ signal }) => api<MedicalItemOut[]>(`${base}/items`, { signal }),
    enabled: caps.data?.medical === true,
  })
}

/** 一个条目的事件（到期原因、谁提出的解除建议都在这里） */
export function useItemEvents(id: string, enabled: boolean) {
  return useQuery({
    queryKey: qk.itemEvents(id),
    queryFn: ({ signal }) => api<EventOut[]>(`${base}/items/${id}/events`, { signal }),
    enabled,
  })
}

/**
 * 条目或医嘱变了：按医嘱域的失效表（invalidation.ts）重新取全部医嘱查询，以及跟着变的饮食、训练记录与识别记录。
 * 在变更的 onSuccess 里等它完成，mutateAsync 返回时列表已是新的。
 */
export function useRefreshMedical() {
  const queryClient = useQueryClient()
  return () => invalidateDomain(queryClient, 'medical')
}

export interface ContinueInput {
  id: string
  review_date: string | null
  end_date: string | null
}

/** 继续遵守：两个日期永远一起提交（后端会同时覆盖两项，没提交的那项会被清空） */
export function useContinueItem() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: ({ id, review_date, end_date }: ContinueInput) =>
      api<MedicalItemOut>(`${base}/items/${id}/continue`, { method: 'POST', json: { review_date, end_date } }),
    onSuccess: refresh,
  })
}

/** 不解除：撤销解除建议，条目照常生效 */
export function useCancelProposal() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: (id: string) => api<MedicalItemOut>(`${base}/items/${id}/cancel-proposal`, { method: 'POST' }),
    onSuccess: refresh,
  })
}
