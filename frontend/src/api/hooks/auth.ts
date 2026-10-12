import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import { clearToken, setToken } from '../token'
import type { LoginRequest, RegisterRequest, TokenResponse, UserOut } from '../types'

export function useMe() {
  return useQuery({ queryKey: qk.me, queryFn: ({ signal }) => api<UserOut>('/api/auth/me', { signal }) })
}

/** 登录成功后换掉缓存（上一个账号的数据不能留下）并保存令牌。401 invalid_credentials 只交给表单显示。 */
export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LoginRequest) => api<TokenResponse>('/api/auth/login', { method: 'POST', json: body }),
    onSuccess: (data) => {
      queryClient.clear()
      setToken(data.access_token)
    },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: RegisterRequest) => api<UserOut>('/api/auth/register', { method: 'POST', json: body }),
  })
}

/** 退出：先请求后端作废令牌；接口失败（例如令牌已失效、断网）也照样清掉本地令牌与缓存。 */
export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api<undefined>('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
      clearToken()
      queryClient.clear()
    },
  })
}
