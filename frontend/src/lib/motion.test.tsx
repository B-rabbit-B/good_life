import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { setMediaMatches } from '../test/setup'
import { usePrefersReducedMotion } from './motion'

describe('motion preference', () => {
  it('reads and follows the reduced motion setting', () => {
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(false)
    act(() => setMediaMatches((query) => query === '(prefers-reduced-motion: reduce)'))
    expect(result.current).toBe(true)
  })
})

describe('api error', () => {
  it('keeps the backend status, code, message and field details', () => {
    const error = new ApiError(422, 'validation_error', '参数不合法', [{ field: 'height_cm', message: '超出范围' }])
    expect(error).toBeInstanceOf(Error)
    expect(error.name).toBe('ApiError')
    expect(error.status).toBe(422)
    expect(error.code).toBe('validation_error')
    expect(error.message).toBe('参数不合法')
    expect(error.details).toEqual([{ field: 'height_cm', message: '超出范围' }])
    expect(new ApiError(500, 'internal_error', '出错了').details).toBeUndefined()
  })
})
