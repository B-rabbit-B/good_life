// 附近餐厅的接口，按后端的规则模拟：设置在内存里（未询问时 should_ask_location 为真；记下选择后为假），
// 用坐标检索而没有授权时 409 restaurant_location_not_granted；remember_area 时把区域记成“朝阳区”。
// 记下每次授权与检索的请求体；searchErrors 依次用于前几次检索，hold 兑现前检索不返回。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { RestaurantSearchIn, RestaurantSearchOut, RestaurantSettingsOut } from '../../../api/types'
import { NEEDS, NOT_GRANTED_MESSAGE, restaurantSettings, SAVED_AREA, searchResult } from '../../fixtures/restaurants'

export interface RestaurantError {
  status: number
  code: string
  message: string
}

export interface RestaurantOptions {
  settings?: Partial<RestaurantSettingsOut>
  result?: RestaurantSearchOut
  searchErrors?: RestaurantError[]
  hold?: Promise<void>
}

const errorResponse = ({ status, code, message }: RestaurantError) =>
  HttpResponse.json({ error: { code, message } }, { status })

export function restaurantHandlers(opts: RestaurantOptions = {}) {
  let settings = restaurantSettings(opts.settings)
  const searchErrors = [...(opts.searchErrors ?? [])]
  const record = {
    consents: [] as string[],
    searches: [] as RestaurantSearchIn[],
    clears: 0,
  }

  const handlers: HttpHandler[] = [
    http.get('/api/restaurants/settings', () => HttpResponse.json(settings)),
    http.put('/api/restaurants/settings/consent', async ({ request }) => {
      const { consent } = await request.json() as { consent: 'granted' | 'denied' }
      record.consents.push(consent)
      settings = { ...settings, location_consent: consent, should_ask_location: false }
      return HttpResponse.json(settings)
    }),
    http.delete('/api/restaurants/settings/area', () => {
      record.clears += 1
      settings = { ...settings, area: null }
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/restaurants/needs', () => HttpResponse.json(NEEDS)),
    http.post('/api/restaurants/search', async ({ request }) => {
      const body = await request.json() as RestaurantSearchIn
      record.searches.push(body)
      await opts.hold
      const error = searchErrors.shift()
      if (error) return errorResponse(error)
      if (body.location && settings.location_consent !== 'granted') {
        return errorResponse({ status: 409, code: 'restaurant_location_not_granted', message: NOT_GRANTED_MESSAGE })
      }
      if (body.remember_area && !body.use_saved_area) settings = { ...settings, area: SAVED_AREA }
      return HttpResponse.json(opts.result ?? searchResult())
    }),
  ]
  return { handlers, record, current: () => settings }
}
