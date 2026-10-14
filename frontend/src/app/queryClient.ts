import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/errors'
import { refreshConsentsOnRequired } from '../api/invalidation'

/** 只对 5xx 与网络错误重试一次；4xx 是后端的明确答复，重试没有意义。 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false
  return error instanceof ApiError && (error.status === 0 || error.status >= 500)
}

/**
 * 请求一律真的发出去（TanStack 默认 'online'：浏览器认为离线时把请求挂起，按钮一直转、什么也不说，恢复网络后才补发）。
 * 离线时 fetch 被拒绝，客户端统一报“网络连接失败，请检查网络后重试”，页面照常显示。测试用的查询客户端也用它。
 */
export const NETWORK_MODE = 'always' as const

/** 查询与写操作的统一出错处理：回 403 consent_required 时重新读取单独同意（测试用的查询客户端也装它） */
export function consentCaches(client: () => QueryClient): { queryCache: QueryCache; mutationCache: MutationCache } {
  const onError = (error: unknown) => refreshConsentsOnRequired(client(), error)
  return { queryCache: new QueryCache({ onError }), mutationCache: new MutationCache({ onError }) }
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    ...consentCaches(() => client),
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 30_000, refetchOnWindowFocus: false, networkMode: NETWORK_MODE },
      mutations: { retry: false, networkMode: NETWORK_MODE },
    },
  })
  return client
}

export const queryClient = createQueryClient()
