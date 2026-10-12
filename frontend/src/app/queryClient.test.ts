import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { createQueryClient, shouldRetry } from './queryClient'

describe('query client', () => {
  it('retries server and network errors once and nothing else', () => {
    expect(shouldRetry(0, new ApiError(502, 'http_error', 'x'))).toBe(true)
    expect(shouldRetry(0, new ApiError(0, 'network_error', 'x'))).toBe(true)
    expect(shouldRetry(1, new ApiError(500, 'internal_error', 'x'))).toBe(false)
    expect(shouldRetry(0, new ApiError(404, 'not_found', 'x'))).toBe(false)
    expect(shouldRetry(0, new ApiError(401, 'invalid_token', 'x'))).toBe(false)
    expect(shouldRetry(0, new Error('x'))).toBe(false)
  })

  it('keeps data fresh for 30 seconds and ignores window focus', () => {
    const queries = createQueryClient().getDefaultOptions().queries
    expect(queries?.staleTime).toBe(30_000)
    expect(queries?.refetchOnWindowFocus).toBe(false)
    expect(queries?.retry).toBe(shouldRetry)
  })
})
