// 数据可控（“我的 → 隐私与数据”页）：导出全部数据、删除账号、清空全部对话。只有隐私与数据页用，不放进对话页也用的钩子文件。
// 导出与删除的请求体里有密码：变更结束后不在缓存里多留（gcTime 0；页面在每次提交后 reset，变更随即被回收）；
// 密码只在请求体里，不进地址、日志与浏览器存储。
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, apiDownload } from '../client'
import { discardConversations } from '../invalidation'

/** 重新输入密码后导出：返回压缩包与后端给的文件名（good-life-export-年月日.zip）；密码错了是 403 password_incorrect */
export function useExportData() {
  return useMutation({
    gcTime: 0,
    mutationFn: (password: string) => apiDownload('/api/account/export', { password }),
  })
}

/** 删除账号的请求本身（带上“我知道不能恢复”的勾选）；成功后的清理见 app/useDeleteAccount */
export function useDeleteAccountRequest() {
  return useMutation({
    gcTime: 0,
    mutationFn: (password: string) =>
      api<undefined>('/api/account/delete', { method: 'POST', json: { password, confirm: true } }),
  })
}

/** 清空全部对话（后端同时清掉开场问候）；成功后丢掉对话与开场的缓存（invalidation.ts 的 discardConversations） */
export function useClearConversations() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<undefined>('/api/agent/conversations', { method: 'DELETE' }),
    onSuccess: () => discardConversations(queryClient),
  })
}
