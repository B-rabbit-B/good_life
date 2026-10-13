// 附近餐厅的接口：设置（定位授权、已保存的大致区域）、需求选项与检索。
// 检索的请求体里有坐标或地名：只用于这一次请求，变更结束后不在缓存里多留（gcTime 0；页面在每次检索后 reset，变更随即被回收）。
// 是否询问定位只看后端的 should_ask_location，前端不另存同意状态。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { NeedOut, RestaurantSearchIn, RestaurantSearchOut, RestaurantSettingsOut } from '../types'

const base = '/api/restaurants'

/** 定位授权与已保存的大致区域；enabled 为假时不请求（饮食模块不开放时后端是 403） */
export function useRestaurantSettings(enabled = true) {
  return useQuery({
    queryKey: qk.restaurantSettings,
    queryFn: ({ signal }) => api<RestaurantSettingsOut>(`${base}/settings`, { signal }),
    enabled,
  })
}

/** 记下用户的选择（允许或不允许定位）；返回的新设置直接写入缓存 */
export function useSetConsent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (consent: 'granted' | 'denied') =>
      api<RestaurantSettingsOut>(`${base}/settings/consent`, { method: 'PUT', json: { consent } }),
    onSuccess: (settings) => {
      queryClient.setQueryData(qk.restaurantSettings, settings)
    },
  })
}

/** 清除已保存的大致区域；完成后重新读取设置 */
export function useClearArea() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>(`${base}/settings/area`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.restaurantSettings }),
  })
}

/** 需求选项（按后端的词表顺序） */
export function useNeeds() {
  return useQuery({ queryKey: qk.needs, queryFn: ({ signal }) => api<NeedOut[]>(`${base}/needs`, { signal }) })
}

/** 地点三选一：浏览器定位的坐标、地名（可加城市）、已保存的大致区域 */
export type SearchWhere =
  | { location: { lng: number; lat: number; coord_type: 'gps' } }
  | { place: string; city?: string }
  | { use_saved_area: true }

export type SearchBody = Pick<RestaurantSearchIn, 'needs' | 'radius' | 'remember_area'> & SearchWhere

/**
 * 检索附近的店（地点三选一：坐标、地名加可选城市、已保存的大致区域）。
 * 请求体不留在变更缓存里（gcTime 0，调用方用完 reset）；记住了大致区域时重新读取设置。
 */
export function useRestaurantSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: 0,
    mutationFn: (body: SearchBody) => api<RestaurantSearchOut>(`${base}/search`, { method: 'POST', json: body }),
    onSuccess: (_result, body) => {
      if (body.remember_area) void queryClient.invalidateQueries({ queryKey: qk.restaurantSettings })
    },
  })
}
