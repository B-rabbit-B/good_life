import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { EventOut, MedicalItemOut } from '../types'
import { useCapabilities } from './profile'

/** 需要本人处理的条目：待复核的，以及仍在生效但带着解除建议的（只在医嘱模块开放时请求） */
export function useMedicalReviews() {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.reviews,
    queryFn: ({ signal }) => api<MedicalItemOut[]>('/api/medical/reviews', { signal }),
    enabled: caps.data?.medical === true,
  })
}

/** 全部医嘱条目 */
export function useMedicalItems() {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.medicalItems,
    queryFn: ({ signal }) => api<MedicalItemOut[]>('/api/medical/items', { signal }),
    enabled: caps.data?.medical === true,
  })
}

/** 一个条目的事件（到期原因、谁提出的解除建议都在这里） */
export function useItemEvents(id: string, enabled: boolean) {
  return useQuery({
    queryKey: qk.itemEvents(id),
    queryFn: ({ signal }) => api<EventOut[]>(`/api/medical/items/${id}/events`, { signal }),
    enabled,
  })
}

/** 条目变了：待处理列表、条目列表、当前约束与这一条的事件都要重新取 */
function useRefreshItem() {
  const queryClient = useQueryClient()
  return async (id: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: qk.reviews }),
      queryClient.invalidateQueries({ queryKey: qk.medicalItems }),
      queryClient.invalidateQueries({ queryKey: ['medical', 'constraints'] }),
      queryClient.invalidateQueries({ queryKey: qk.itemEvents(id) }),
    ])
  }
}

export interface ContinueInput {
  id: string
  review_date: string | null
  end_date: string | null
}

/** 继续遵守：两个日期永远一起提交（后端会同时覆盖两项，没提交的那项会被清空） */
export function useContinueItem() {
  const refresh = useRefreshItem()
  return useMutation({
    mutationFn: ({ id, review_date, end_date }: ContinueInput) =>
      api<MedicalItemOut>(`/api/medical/items/${id}/continue`, { method: 'POST', json: { review_date, end_date } }),
    onSuccess: (_item, { id }) => refresh(id),
  })
}

/** 不解除：撤销解除建议，条目照常生效 */
export function useCancelProposal() {
  const refresh = useRefreshItem()
  return useMutation({
    mutationFn: (id: string) => api<MedicalItemOut>(`/api/medical/items/${id}/cancel-proposal`, { method: 'POST' }),
    onSuccess: (_item, id) => refresh(id),
  })
}
