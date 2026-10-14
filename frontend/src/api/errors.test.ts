import { describe, expect, it } from 'vitest'
import { ApiError, asApiError, networkError } from './errors'

describe('as api error', () => {
  it('returns an api error unchanged', () => {
    const error = new ApiError(409, 'username_taken', '该用户名已被注册，请换一个')
    expect(asApiError(error)).toBe(error)
  })

  it('keeps a programming type error out of the network error', () => {
    for (const caught of [new TypeError('Failed to fetch'), new TypeError("Cannot read properties of undefined (reading 'x')")]) {
      expect(asApiError(caught)).toMatchObject({ status: 0, code: 'unknown_error', message: '出了点问题，请稍后再试' })
    }
  })

  it('leaves the network error to the callers that see the rejected fetch', () => {
    expect(networkError()).toMatchObject({ status: 0, code: 'network_error' })
    expect(asApiError(networkError()).code).toBe('network_error')
  })

  it('turns anything else into unknown_error with a chinese message', () => {
    for (const caught of [new Error('boom'), 'boom', undefined, null, { code: 'x' }]) {
      const error = asApiError(caught)
      expect(error).toBeInstanceOf(ApiError)
      expect(error).toMatchObject({ status: 0, code: 'unknown_error', message: '出了点问题，请稍后再试' })
    }
  })
})
