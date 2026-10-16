import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useDeleteAccountRequest } from '../api/hooks/account'
import { clearToken } from '../api/token'
import { clearPendingPhoto } from '../lib/photoHandoff'
import type { LoginState } from './guards'
import { PATHS } from './paths'

/**
 * 删除账号：请求成功（后端已删光全部数据，令牌随之失效）后按 useLogout 的顺序收尾：取消进行中的查询、清令牌、
 * 清交给拍照页的照片、回到登录页并带上“已删除”，调用它的页面卸载后才清全部查询缓存（理由见 useLogout）。
 * 先取消查询：还没回来的查询会因令牌失效回 401，触发“登录已过期”盖掉“已删除”。请求之前不取消：密码错了还要留在本页，
 * 取消会让还没取到数据的查询停在加载中。
 * 密码错了（403 password_incorrect）或请求失败时什么都不清，错误原样抛给面板显示。只能在登录后才有的页面里使用。
 */
export function useDeleteAccount() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const request = useDeleteAccountRequest()
  const deleted = useRef(false)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      if (deleted.current) queryClient.clear()
    }
  }, [queryClient])
  return useMutation({
    gcTime: 0,
    mutationFn: async (password: string) => {
      try {
        await request.mutateAsync(password)
      } finally {
        // 请求体里有密码：不论成败都让它离开变更缓存
        request.reset()
      }
      await queryClient.cancelQueries()
      clearToken()
      clearPendingPhoto()
      deleted.current = true
      await navigate(PATHS.login, { replace: true, state: { deleted: true } satisfies LoginState })
      if (!mounted.current) queryClient.clear()
    },
  })
}
