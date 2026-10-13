import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import { setToken } from '../token'
import type { LoginRequest, RegisterRequest, TokenResponse, UserOut } from '../types'

export function useMe() {
  return useQuery({ queryKey: qk.me, queryFn: ({ signal }) => api<UserOut>('/api/auth/me', { signal }) })
}

/**
 * 登录与注册的请求体里有密码：变更结束后不在缓存里多留（gcTime 0；页面在每次提交后 reset，变更随即被回收）。
 */
const CREDENTIALS_GC_TIME = 0

/** 登录成功后换掉缓存（上一个账号的数据不能留下）并保存令牌。401 invalid_credentials 只交给表单显示。 */
export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: CREDENTIALS_GC_TIME,
    mutationFn: (body: LoginRequest) => api<TokenResponse>('/api/auth/login', { method: 'POST', json: body }),
    onSuccess: (data) => {
      queryClient.clear()
      setToken(data.access_token)
    },
  })
}

export function useRegister() {
  return useMutation({
    gcTime: CREDENTIALS_GC_TIME,
    mutationFn: (body: RegisterRequest) => api<UserOut>('/api/auth/register', { method: 'POST', json: body }),
  })
}
