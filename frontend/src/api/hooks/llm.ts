import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { AssignmentOut, ProviderOut } from '../types'

/** 本人添加的模型服务（只含后端给的密钥掩码） */
export function useProviders() {
  return useQuery({ queryKey: qk.providers, queryFn: ({ signal }) => api<ProviderOut[]>('/api/llm/providers', { signal }) })
}

/** 日常对话与看图识别各用哪个模型 */
export function useAssignments() {
  return useQuery({
    queryKey: qk.assignments,
    queryFn: ({ signal }) => api<AssignmentOut[]>('/api/llm/assignments', { signal }),
  })
}
