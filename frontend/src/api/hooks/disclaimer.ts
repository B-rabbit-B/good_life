import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { DisclaimerOut, DisclaimerStatus } from '../types'

export function useDisclaimer() {
  return useQuery({ queryKey: qk.disclaimer, queryFn: ({ signal }) => api<DisclaimerOut>('/api/disclaimer', { signal }) })
}

export function useDisclaimerStatus() {
  return useQuery({
    queryKey: qk.disclaimerStatus,
    queryFn: ({ signal }) => api<DisclaimerStatus>('/api/disclaimer/status', { signal }),
  })
}

/** 确认当前版本；成功后直接写入新的状态，守卫随即放行。 */
export function useAcceptDisclaimer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (version: string) =>
      api<DisclaimerStatus>('/api/disclaimer/accept', { method: 'POST', json: { version } }),
    onSuccess: (status) => {
      queryClient.setQueryData(qk.disclaimerStatus, status)
    },
  })
}
