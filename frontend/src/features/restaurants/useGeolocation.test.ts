import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useGeolocation } from './useGeolocation'

type Success = (position: GeolocationPosition) => void
type Failure = (error: GeolocationPositionError) => void

function stubGeolocation(answer: (success: Success, failure: Failure, options?: PositionOptions) => void) {
  const getCurrentPosition = vi.fn(answer)
  Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
  return getCurrentPosition
}

const failure = (code: number) => ({ code, message: '', PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 }) as GeolocationPositionError

afterEach(() => {
  Reflect.deleteProperty(navigator, 'geolocation')
})

describe('use geolocation', () => {
  it('resolves the coordinates with high accuracy and a ten second timeout', async () => {
    const get = stubGeolocation((success) => success({ coords: { longitude: 116.46, latitude: 39.91 } } as GeolocationPosition))
    const { result } = renderHook(() => useGeolocation())
    await expect(result.current.request()).resolves.toEqual({ lng: 116.46, lat: 39.91 })
    expect(get.mock.calls[0]?.[2]).toEqual({ enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 })
  })

  it('rejects when the user refuses', async () => {
    stubGeolocation((_success, fail) => fail(failure(1)))
    const { result } = renderHook(() => useGeolocation())
    await expect(result.current.request()).rejects.toThrow('geolocation_1')
  })

  it('rejects on a timeout', async () => {
    stubGeolocation((_success, fail) => fail(failure(3)))
    const { result } = renderHook(() => useGeolocation())
    await expect(result.current.request()).rejects.toThrow('geolocation_3')
  })

  it('rejects when the browser has no geolocation', async () => {
    const { result } = renderHook(() => useGeolocation())
    await expect(result.current.request()).rejects.toThrow('geolocation_unavailable')
  })
})
