import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { Capabilities, ProfileOut, ProfileUpdate } from '../types'

export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: ({ signal }) => api<ProfileOut>('/api/profile', { signal }) })
}

/**
 * 修改档案的请求体。身高与体重可以直接是输入框里的原文（空或不是数）：界面不替后端判断，
 * 交上去由后端在对应字段下说明哪里不对。
 */
export type ProfilePatch = Omit<ProfileUpdate, 'height_cm' | 'weight_kg'> & {
  height_cm?: number | string | null
  weight_kg?: number | string | null
}

/** 修改档案这个变更的键：/health 的跳转在它进行中时等它（它可能改变开放的模块） */
export const PROFILE_UPDATE_KEY = ['profile', 'update'] as const

/** 修改档案；成功后写入新档案，并等能力清单重新取回（性别等字段决定开放哪些模块）后才算完成。 */
export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: PROFILE_UPDATE_KEY,
    mutationFn: (body: ProfilePatch) => api<ProfileOut>('/api/profile', { method: 'PATCH', json: body }),
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
