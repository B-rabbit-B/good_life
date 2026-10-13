import { describe, expect, it } from 'vitest'
import { ApiError, asApiError, networkError } from './errors'

describe('as api error', () => {
  it('returns an api error unchanged', () => {
    const error = new ApiError(409, 'username_taken', '该用户名已被注册，请换一个')
    expect(asApiError(error)).toBe(error)
  })

  it('turns a rejected fetch into the network error', () => {
    expect(asApiError(new TypeError('Failed to fetch'))).toMatchObject(networkError())
    expect(asApiError(new TypeError('Failed to fetch')).code).toBe('network_error')
  })

  it('turns anything else into unknown_error with a chinese message', () => {
    for (const caught of [new Error('boom'), 'boom', undefined, null, { code: 'x' }]) {
      const error = asApiError(caught)
      expect(error).toBeInstanceOf(ApiError)
      expect(error).toMatchObject({ status: 0, code: 'unknown_error', message: '出了点问题，请稍后再试' })
    }
  })
})
