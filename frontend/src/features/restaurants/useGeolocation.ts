import { useCallback } from 'react'

const TIMEOUT_MS = 10_000

/**
 * 取一次浏览器定位（高精度、10 秒超时、不用缓存的旧位置）。拒绝、超时、不支持都 reject，调用方改用地点输入。
 * 坐标只交给调用方这一次，不在任何地方保存。
 */
export function useGeolocation(): { request: () => Promise<{ lng: number; lat: number }> } {
  const request = useCallback(() => new Promise<{ lng: number; lat: number }>((resolve, reject) => {
    const geo = typeof navigator === 'undefined' ? undefined : navigator.geolocation
    if (!geo) {
      reject(new Error('geolocation_unavailable'))
      return
    }
    geo.getCurrentPosition(
      (position) => resolve({ lng: position.coords.longitude, lat: position.coords.latitude }),
      (error) => reject(new Error(`geolocation_${error.code}`)),
      { enableHighAccuracy: true, timeout: TIMEOUT_MS, maximumAge: 0 },
    )
  }), [])
  return { request }
}
