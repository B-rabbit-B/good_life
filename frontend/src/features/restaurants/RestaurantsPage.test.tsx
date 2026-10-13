import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import {
  NOT_GRANTED_MESSAGE, NOTICE, PLACE_NOT_FOUND_MESSAGE, SAVED_AREA, searchResult, UNCHECKED_TIP,
} from '../../test/fixtures/restaurants'
import { restaurantHandlers, type RestaurantOptions } from '../../test/msw/handlers/restaurants'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const LNG = 116.4627
const LAT = 39.9087

function stubGeolocation(ok: boolean) {
  const getCurrentPosition = vi.fn((success: PositionCallback, failure?: PositionErrorCallback | null) => {
    if (ok) success({ coords: { longitude: LNG, latitude: LAT } } as GeolocationPosition)
    else failure?.({ code: 1, message: 'denied' } as GeolocationPositionError)
  })
  Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
  return getCurrentPosition
}

function renderRestaurants(opts: RestaurantOptions = {}) {
  const restaurants = restaurantHandlers(opts)
  server.use(...restaurants.handlers)
  return { ...renderRoute('/restaurants'), restaurants }
}

async function searchByPlace(user: ReturnType<typeof userEvent.setup>, place = '国贸', city = '') {
  await user.type(await screen.findByLabelText('地名或地标'), place)
  if (city) await user.type(screen.getByLabelText('城市（可不填）'), city)
  await user.click(screen.getByRole('button', { name: '查找附近的店' }))
}

const shopRow = (name: string) => {
  const list = screen.getByRole('list', { name: '附近的店' })
  const row = within(list).getAllByRole('listitem').find((item) => item.querySelector('.shop-n')?.textContent === name)
  if (!row) throw new Error(`没有 ${name}`)
  return row
}

beforeAll(async () => {
  await import('./RestaurantsPage')
}, 60_000)

afterEach(() => {
  Reflect.deleteProperty(navigator, 'geolocation')
})

describe('restaurants page', { timeout: 15_000 }, () => {
  it('asks for location only when the backend says so', async () => {
    const asked = renderRestaurants()
    expect(await screen.findByRole('heading', { name: '用一次你的位置？' })).toBeInTheDocument()
    expect(screen.getByText('只用来查找附近的餐厅，精确位置不会保存。不允许也没关系，可以输入地名或地标，以后不再询问。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '允许定位' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '输入地点' })).toBeInTheDocument()
    expect(screen.queryByLabelText('地名或地标')).not.toBeInTheDocument()
    asked.unmount()

    renderRestaurants({ settings: { location_consent: 'denied' } })
    expect(await screen.findByLabelText('地名或地标')).toBeInTheDocument()
    expect(screen.getByText('没有开启定位，输入地名或地标即可，不会再请求定位。')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '用一次你的位置？' })).not.toBeInTheDocument()
  })

  it('records denial and never asks again', async () => {
    const user = userEvent.setup()
    const get = stubGeolocation(true)
    const restaurants = restaurantHandlers()
    server.use(...restaurants.handlers)
    const first = renderRoute('/restaurants')
    await user.click(await screen.findByRole('button', { name: '输入地点' }))
    expect(await screen.findByLabelText('地名或地标')).toBeInTheDocument()
    expect(restaurants.record.consents).toEqual(['denied'])
    first.unmount()

    renderRoute('/restaurants')
    expect(await screen.findByText('没有开启定位，输入地名或地标即可，不会再请求定位。')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '用一次你的位置？' })).not.toBeInTheDocument()
    expect(get).not.toHaveBeenCalled()
    expect(restaurants.record.searches).toEqual([])
  })

  it('records the choice once on a double press', async () => {
    const user = userEvent.setup({ delay: null })
    const { restaurants } = renderRestaurants()
    await user.dblClick(await screen.findByRole('button', { name: '输入地点' }))
    expect(await screen.findByLabelText('地名或地标')).toBeInTheDocument()
    expect(restaurants.record.consents).toEqual(['denied'])
  })

  it('searches with gps coordinates after consent', async () => {
    const user = userEvent.setup()
    stubGeolocation(true)
    const { restaurants } = renderRestaurants()
    await user.click(await screen.findByRole('button', { name: '允许定位' }))
    expect(await screen.findByRole('list', { name: '附近的店' })).toBeInTheDocument()
    expect(restaurants.record.consents).toEqual(['granted'])
    expect(restaurants.record.searches).toEqual([
      { location: { lng: LNG, lat: LAT, coord_type: 'gps' }, needs: [], radius: 2000, remember_area: false },
    ])
  })

  it('searches once on entry when location is already granted', async () => {
    stubGeolocation(true)
    const { restaurants } = renderRestaurants({ settings: { location_consent: 'granted' } })
    expect(await screen.findByRole('list', { name: '附近的店' })).toBeInTheDocument()
    expect(restaurants.record.searches).toHaveLength(1)
    expect(restaurants.record.searches[0]?.location).toEqual({ lng: LNG, lat: LAT, coord_type: 'gps' })
  })

  it('falls back to the place form when the browser refuses', async () => {
    stubGeolocation(false)
    const { restaurants } = renderRestaurants({ settings: { location_consent: 'granted' } })
    expect(await screen.findByText('没能取得定位，输入地名或地标即可。')).toBeInTheDocument()
    expect(screen.getByLabelText('地名或地标')).toBeInTheDocument()
    expect(restaurants.record.searches).toEqual([])
  })

  it('searches by place and city', async () => {
    const user = userEvent.setup()
    const { restaurants } = renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user, '国贸', '北京')
    expect(await screen.findByRole('list', { name: '附近的店' })).toBeInTheDocument()
    expect(restaurants.record.searches).toEqual([{ place: '国贸', city: '北京', needs: [], radius: 2000, remember_area: false }])
  })

  it('limits needs to three', async () => {
    const user = userEvent.setup()
    const { restaurants } = renderRestaurants({ settings: { location_consent: 'denied' } })
    const group = await screen.findByRole('group', { name: '需求' })
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['清淡', '粥', '汤', '轻食', '全部 12 项'])
    await user.click(within(group).getByRole('button', { name: '全部 12 项' }))
    for (const name of ['清淡', '不辣', '少油']) await user.click(within(group).getByRole('button', { name }))
    expect(within(group).getByRole('button', { name: '少油' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: '甜品' })).toBeDisabled()
    expect(screen.getByText('最多选 3 项')).toBeInTheDocument()
    await user.click(within(group).getByRole('button', { name: '甜品' }))
    expect(within(group).getByRole('button', { name: '甜品' })).toHaveAttribute('aria-pressed', 'false')
    await searchByPlace(user)
    await waitFor(() => expect(restaurants.record.searches[0]?.needs).toEqual(['light', 'not_spicy', 'less_oil']))
    await user.click(within(group).getByRole('button', { name: '不辣' }))
    expect(within(group).getByRole('button', { name: '甜品' })).toBeEnabled()
    expect(screen.queryByText('最多选 3 项')).not.toBeInTheDocument()
  })

  it('shows the notice with a reference tag on every result', async () => {
    const user = userEvent.setup()
    renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user)
    const notice = await screen.findByText(NOTICE)
    expect(within(notice.parentElement as HTMLElement).getByText('仅供参考')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '附近的店' })).toBeInTheDocument()
    expect(screen.getByText('2 公里内 4 家，按适合程度与距离')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '查找附近的店' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '查找附近的店' })).toBeEnabled())
    expect(screen.getByText(NOTICE)).toBeInTheDocument()
    expect(screen.getByText('以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。')).toBeInTheDocument()
  })

  it('shows dish advice from the type advice', async () => {
    const user = userEvent.setup()
    renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user)
    await screen.findByRole('list', { name: '附近的店' })
    const canton = shopRow('岭南小馆')
    expect(within(canton).getByText('注意')).toBeInTheDocument()
    expect(within(canton).getByText('粤菜')).toBeInTheDocument()
    expect(within(canton).getByText('650 米')).toBeInTheDocument()
    expect(canton).toHaveTextContent('可点清蒸鱼、白灼时蔬')
    expect(canton).toHaveTextContent('适量烧味、煲仔饭')
    const noodles = shopRow('张姐面馆')
    expect(noodles).toHaveTextContent('应避开浓汤底拉面')
    expect(within(noodles).getByText('1.5 公里')).toBeInTheDocument()
    expect(within(shopRow('张记粥铺')).getByText('适合')).toBeInTheDocument()
  })

  it('shows only the tip for unknown types', async () => {
    const user = userEvent.setup()
    renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user)
    await screen.findByRole('list', { name: '附近的店' })
    const unknown = shopRow('某某餐厅')
    expect(within(unknown).getByText('未核对')).toBeInTheDocument()
    expect(within(unknown).getByText(UNCHECKED_TIP)).toBeInTheDocument()
    expect(unknown).not.toHaveTextContent('可点')
  })

  it('lists avoided types with dish attributed reasons apart from the list', async () => {
    const user = userEvent.setup()
    renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user)
    const heading = await screen.findByRole('heading', { name: '已避开的类型' })
    const section = heading.closest('section') as HTMLElement
    expect(within(section).getByText('仅供参考')).toBeInTheDocument()
    const hotpot = within(section).getByText('火锅')
    expect(hotpot.tagName).toBe('B')
    expect(within(section).getByText('老码头火锅')).toBeInTheDocument()
    expect(within(section).getByText('杨记麻辣烫、串串香')).toBeInTheDocument()
    expect(section).toHaveTextContent('医嘱代表菜“火锅（浓汤底）”：避免动物内脏与浓肉汤（高嘌呤）')
    expect(section).toHaveTextContent('当日摄入代表菜“麻辣烫”：今天的钠已到 1,640 毫克，再吃一份预计超过上限')
    const list = screen.getByRole('list', { name: '附近的店' })
    expect(within(list).queryByText('老码头火锅')).not.toBeInTheDocument()
  })

  it('links navigation to nav_url', async () => {
    const user = userEvent.setup()
    renderRestaurants({ settings: { location_consent: 'denied' } })
    await searchByPlace(user)
    const link = await screen.findByRole('link', { name: '导航到张记粥铺' })
    expect(link).toHaveAttribute('href', searchResult().restaurants[0]?.nav_url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('remembers the rough area when asked', async () => {
    const user = userEvent.setup()
    const { restaurants } = renderRestaurants({ settings: { location_consent: 'denied' } })
    await user.click(await screen.findByRole('checkbox', { name: '记住大致区域，下次不用再输入。可在设置里清除。' }))
    await searchByPlace(user)
    await screen.findByRole('list', { name: '附近的店' })
    expect(restaurants.record.searches[0]?.remember_area).toBe(true)
    await user.click(await screen.findByRole('button', { name: `用已保存的区域：${SAVED_AREA.name}` }))
    await waitFor(() => expect(restaurants.record.searches[1]).toEqual({ use_saved_area: true, needs: [], radius: 2000, remember_area: false }))
  })

  it('switches to the place form on restaurant_location_not_granted', async () => {
    stubGeolocation(true)
    const { restaurants } = renderRestaurants({
      settings: { location_consent: 'granted' },
      searchErrors: [{ status: 409, code: 'restaurant_location_not_granted', message: NOT_GRANTED_MESSAGE }],
    })
    expect(await screen.findByText(NOT_GRANTED_MESSAGE)).toBeInTheDocument()
    expect(screen.getByLabelText('地名或地标')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(restaurants.record.searches).toHaveLength(1)
  })

  it('shows other restaurant errors verbatim and retries', async () => {
    const user = userEvent.setup()
    const { restaurants } = renderRestaurants({
      settings: { location_consent: 'denied' },
      searchErrors: [{ status: 422, code: 'restaurant_place_not_found', message: PLACE_NOT_FOUND_MESSAGE }],
    })
    await searchByPlace(user, '不存在的地方')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(PLACE_NOT_FOUND_MESSAGE)
    expect(alert).toHaveTextContent('错误码 restaurant_place_not_found')
    await user.click(within(alert).getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('list', { name: '附近的店' })).toBeInTheDocument()
    expect(restaurants.record.searches).toHaveLength(2)
    expect(restaurants.record.searches[1]?.place).toBe('不存在的地方')
  })

  it('keeps the coordinates out of storage and caches', async () => {
    stubGeolocation(true)
    const { queryClient } = renderRestaurants({ settings: { location_consent: 'granted' } })
    await screen.findByRole('list', { name: '附近的店' })
    await waitFor(() => expect(queryClient.getMutationCache().getAll()).toEqual([]))
    const dump = JSON.stringify([
      queryClient.getQueryCache().getAll().map((query) => [query.queryKey, query.state.data]),
      { ...window.localStorage }, { ...window.sessionStorage },
    ])
    expect(dump).not.toContain(String(LNG))
    expect(dump).not.toContain(String(LAT))
  })

  it('marks the place and the remember row as sensitive', async () => {
    const { container } = renderRestaurants({ settings: { location_consent: 'denied', area: SAVED_AREA } })
    await screen.findByLabelText('地名或地标')
    expect(within(screen.getByLabelText('地名或地标').closest('[data-sensitive]') as HTMLElement)
      .getByRole('button', { name: `用已保存的区域：${SAVED_AREA.name}` })).toBeInTheDocument()
    expect(sensitiveAreaMismatch(container)).toEqual({ page: 'restaurants', missing: [], unexpected: [] })
  })
})
