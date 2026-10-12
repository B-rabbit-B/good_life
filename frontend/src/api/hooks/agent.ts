import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type {
  AgentSettingsOut, AgentSettingsUpdate, ConversationDetailOut, ConversationOut, OpeningResponse,
} from '../types'

/** 本人的会话，最近更新的在前 */
export function useConversations() {
  return useQuery({
    queryKey: qk.conversations,
    queryFn: ({ signal }) => api<ConversationOut[]>('/api/agent/conversations', { signal }),
  })
}

/** 一个会话与它的可见消息（用户与助手） */
export function useConversation(id: string | null) {
  return useQuery({
    queryKey: qk.conversation(id ?? ''),
    queryFn: ({ signal }) => api<ConversationDetailOut>(`/api/agent/conversations/${id ?? ''}`, { signal }),
    enabled: id !== null,
  })
}

/** 新建会话（第一次发消息前）；成功后放进会话列表的最前面 */
export function useCreateConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<ConversationOut>('/api/agent/conversations', { method: 'POST', json: {} }),
    onSuccess: (conversation) => {
      queryClient.setQueryData<ConversationOut[]>(qk.conversations, (list) => [conversation, ...(list ?? [])])
      queryClient.setQueryData<ConversationDetailOut>(qk.conversation(conversation.id), { ...conversation, messages: [] })
    },
  })
}

/** 今天的开场问题：一次打开应用只取一次（不过期、不回收）；回答或拒绝后在缓存里清掉 */
export function useOpening() {
  return useQuery({
    queryKey: qk.opening,
    queryFn: ({ signal }) => api<OpeningResponse>('/api/agent/opening', { signal }),
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

function useOpeningAction(action: 'decline' | 'answer') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<undefined>(`/api/agent/opening/${id}/${action}`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.setQueryData<OpeningResponse>(qk.opening, { opening: null })
    },
  })
}

/** “稍后”“不用了”：开场标为已拒绝 */
export function useDeclineOpening() {
  return useOpeningAction('decline')
}

/** 按开场卡片去处理了（跳转或继续遵守成功）：开场标为已回答 */
export function useAnswerOpening() {
  return useOpeningAction('answer')
}

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
