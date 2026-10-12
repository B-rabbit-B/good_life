import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { AgentSettingsOut, AgentSettingsUpdate } from '../types'

/** “打开应用时主动提问”的设置 */
export function useAgentSettings() {
  return useQuery({
    queryKey: qk.agentSettings,
    queryFn: ({ signal }) => api<AgentSettingsOut>('/api/agent/settings', { signal }),
  })
}

/** 改设置；成功后直接写入后端返回的设置 */
export function useUpdateAgentSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AgentSettingsUpdate) =>
      api<AgentSettingsOut>('/api/agent/settings', { method: 'PUT', json: body }),
    onSuccess: (settings) => {
      queryClient.setQueryData(qk.agentSettings, settings)
    },
  })
}
