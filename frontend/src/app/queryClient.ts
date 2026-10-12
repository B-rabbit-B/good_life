import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/errors'

/** 只对 5xx 与网络错误重试一次；4xx 是后端的明确答复，重试没有意义。 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false
  return error instanceof ApiError && (error.status === 0 || error.status >= 500)
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 30_000, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
}

export const queryClient = createQueryClient()
