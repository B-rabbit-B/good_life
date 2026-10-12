import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { PATHS } from '../../app/paths'
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

/**
 * 退出：先取消进行中的查询，再请求后端作废令牌（令牌早已失效、断网也照样往下走，且不触发“登录已过期”），
 * 清掉本地令牌，回到登录页；调用它的页面卸载时才清缓存——还挂着的页面先卸载，不会拿着空缓存、没有令牌去重新请求。
 * （navigate 返回时 React 可能还没提交新页面：登录页是按需加载的，状态更新又在过渡里；这时清缓存，
 * 仍挂着的页面因变更结束而重绘，会不带令牌重新请求，401 又触发“登录已过期”。）
 * 只能在登录后才有的页面里使用（回到登录页时它一定卸载）。
 */
export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const loggedOut = useRef(false)
  useEffect(() => () => {
    if (loggedOut.current) queryClient.clear()
  }, [queryClient])
  return useMutation({
    mutationFn: async () => {
      await queryClient.cancelQueries()
      await api<undefined>('/api/auth/logout', { method: 'POST', notifyUnauthorized: false }).catch(() => undefined)
      clearToken()
      loggedOut.current = true
      await navigate(PATHS.login, { replace: true })
    },
  })
}
