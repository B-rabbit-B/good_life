import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { Capabilities, ProfileOut, ProfileUpdate } from '../types'

export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: ({ signal }) => api<ProfileOut>('/api/profile', { signal }) })
}

/** 修改档案；成功后写入新档案，并等能力清单重新取回（性别等字段决定开放哪些模块）后才算完成。 */
export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ProfileUpdate) => api<ProfileOut>('/api/profile', { method: 'PATCH', json: body }),
    onSuccess: async (profile) => {
      queryClient.setQueryData(qk.profile, profile)
      await queryClient.invalidateQueries({ queryKey: qk.capabilities })
    },
  })
}

/** 哪些模块向本人开放：入口显隐只看它，前端不自己判断。 */
export function useCapabilities() {
  return useQuery({
    queryKey: qk.capabilities,
    queryFn: ({ signal }) => api<Capabilities>('/api/me/capabilities', { signal }),
  })
}
