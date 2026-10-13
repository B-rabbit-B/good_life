// 附近吃什么（设计稿 09）：后端说要询问时先问一次定位（允许 → 记下授权、取定位、按坐标检索；输入地点 → 记下拒绝，以后不再询问）；
// 已授权时进页面自动取一次定位检索，取不到就改为输入地点；已拒绝时只用地点输入（有已保存的大致区域时可直接用它）。
// 需求胶囊最多选 3 个；“记住大致区域”随这次检索一起交给后端。结果：提示原文加“仅供参考”、店铺面板、已避开的类型、免责原文。
// 坐标只用于这一次请求：不放进状态、存储或查询键，检索变更用完就 reset。地点输入与“记住区域”一行在敏感区里。
import { useEffect, useRef, useState } from 'react'
import { type ApiError, asApiError } from '../../api/errors'
import { useNeeds, useRestaurantSearch, useRestaurantSettings, useSetConsent, type SearchWhere } from '../../api/hooks/restaurants'
import type { RestaurantSearchOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { Title } from '../../components/Title'
import { RESTAURANT_LOCATION_NOT_GRANTED } from '../../lib/contract'
import { fmtDistance } from '../../lib/format'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/field-input.css'
import '../../styles/components/restaurants.css'
import '../../styles/components/sec-head.css'
import { AvoidedTypes } from './AvoidedTypes'
import { LocationAsk } from './LocationAsk'
import { NeedChips } from './NeedChips'
import { PlaceForm } from './PlaceForm'
import { ShopList } from './ShopList'
import { useGeolocation } from './useGeolocation'

const RADIUS = 2000
const DENIED_NOTE = '没有开启定位，输入地名或地标即可，不会再请求定位。'
const FAILED_NOTE = '没能取得定位，输入地名或地标即可。'
const REMEMBER = '记住大致区域，下次不用再输入。可在设置里清除。'

type Mode = 'auto' | 'gps' | 'place'
type Kind = 'gps' | 'place' | 'saved'

function Results({ result }: { result: RestaurantSearchOut }) {
  const count = result.restaurants.length
  return (
    <div className="rs-res">
      <p className="notice"><span>{result.notice}</span><RefTag /></p>
      <div className="sec-h">
        <Title k="nearbyList" level="h" />
        <span className="t-cap">{fmtDistance(RADIUS)}内 {count} 家，按适合程度与距离</span>
      </div>
      {count > 0 && <ShopList result={result} />}
      {result.avoided_types.length > 0 && <AvoidedTypes types={result.avoided_types} />}
      <p className="rs-disc">{result.disclaimer}</p>
    </div>
  )
}

export default function RestaurantsPage() {
  useSensitivePage('restaurants')
  const settings = useRestaurantSettings()
  const needs = useNeeds()
  const consent = useSetConsent()
  const search = useRestaurantSearch()
  const geo = useGeolocation()
  const flight = useSingleFlight()

  const [mode, setMode] = useState<Mode>('auto')
  const [note, setNote] = useState<string | null>(null)
  const [place, setPlace] = useState('')
  const [city, setCity] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [remember, setRemember] = useState(false)
  const [busy, setBusy] = useState<'locating' | 'searching' | null>(null)
  const [result, setResult] = useState<RestaurantSearchOut | null>(null)
  const [error, setError] = useState<{ error: ApiError; kind: Kind } | null>(null)
  const autoTried = useRef(false)

  const toPlace = (text: string | null) => {
    setMode('place')
    setNote(text)
  }

  /** 发出一次检索；结束后立即 reset，请求体（坐标、地名）不留在变更缓存里 */
  const run = async (where: SearchWhere, kind: Kind) => {
    setBusy('searching')
    setError(null)
    try {
      const out = await search.mutateAsync({
        ...where, needs: selected, radius: RADIUS, remember_area: kind === 'saved' ? false : remember,
      })
      setResult(out)
      if (kind !== 'saved') setRemember(false)
    } catch (caught) {
      const failure = asApiError(caught)
      setResult(null)
      if (failure.code === RESTAURANT_LOCATION_NOT_GRANTED) {
        toPlace(failure.message)
        void settings.refetch()
      } else {
        setError({ error: failure, kind })
      }
    } finally {
      search.reset()
      setBusy(null)
    }
  }

  /** 取一次定位并按坐标检索；坐标只在这个函数里，用完即弃 */
  const locateAndSearch = async () => {
    setMode('gps')
    setBusy('locating')
    let coords: { lng: number; lat: number }
    try {
      coords = await geo.request()
    } catch {
      setBusy(null)
      toPlace(FAILED_NOTE)
      return
    }
    await run({ location: { lng: coords.lng, lat: coords.lat, coord_type: 'gps' } }, 'gps')
  }

  const searchGps = () => flight(locateAndSearch)

  const searchPlace = () => flight(() => {
    const trimmed = city.trim()
    return run(trimmed ? { place: place.trim(), city: trimmed } : { place: place.trim() }, 'place')
  })

  const searchSaved = () => flight(() => run({ use_saved_area: true }, 'saved'))

  // 已授权（而且不必再问）时，进页面自动取一次定位检索
  const data = settings.data
  useEffect(() => {
    if (autoTried.current || !data || data.should_ask_location || data.location_consent !== 'granted') return
    autoTried.current = true
    void searchGps()
  })

  /** 记下选择（同一时间只记一次）；允许时接着取定位检索。失败时 consent.error 原样显示在按钮下面 */
  const choose = (choice: 'granted' | 'denied') => {
    autoTried.current = true
    void flight(async () => {
      try {
        await consent.mutateAsync(choice)
      } catch {
        return
      }
      if (choice === 'granted') await locateAndSearch()
      else toPlace(null)
    })
  }

  const retry = () => {
    if (!error) return
    if (error.kind === 'gps') void searchGps()
    else if (error.kind === 'saved') void searchSaved()
    else void searchPlace()
  }

  const header = <PageHeader titleKey="restaurants" variant="sub" back />
  if (!data) {
    return (
      <>
        {header}
        {settings.isError
          ? <ErrorState error={asApiError(settings.error)} onRetry={() => void settings.refetch()} />
          : <LoadingState variant="list" text="正在读取" />}
      </>
    )
  }

  if (mode === 'auto' && data.should_ask_location) {
    const consentError = consent.error ? asApiError(consent.error) : null
    return (
      <>
        {header}
        <LocationAsk
          pending={consent.isPending ? consent.variables : null}
          onAllow={() => choose('granted')} onPlace={() => choose('denied')}
        />
        {consentError && (
          <div className="err pad" role="alert">
            <Icon name="alert" size={18} />
            <span>{consentError.message}<small>错误码 {consentError.code}</small></span>
          </div>
        )}
      </>
    )
  }

  const effective: Mode = mode === 'auto' ? (data.location_consent === 'granted' ? 'gps' : 'place') : mode
  const placeNote = note ?? (data.location_consent === 'denied' ? DENIED_NOTE : null)
  const working = busy !== null
  return (
    <>
      {header}
      {effective === 'gps'
        ? (
          <div className="rs-gps">
            <span>按你现在的位置查找附近的店。</span>
            <Button variant="text" isDisabled={working} onPress={() => toPlace(null)}>改为输入地点</Button>
          </div>
        )
        : (
          <>
            <PlaceForm
              place={place} city={city} onPlace={setPlace} onCity={setCity}
              savedArea={data.area?.name ?? null} onUseSaved={() => void searchSaved()} busy={working}
            />
            {placeNote && <p className="loc-off">{placeNote}</p>}
          </>
        )}
      {needs.data && <NeedChips needs={needs.data} selected={selected} onChange={setSelected} />}
      <Sensitive area="rememberArea" className="plate rs-remember">
        <Checkbox isSelected={remember} onChange={setRemember}>{REMEMBER}</Checkbox>
      </Sensitive>
      <div className="pad rs-go">
        <Button
          variant="primary" block isPending={working}
          isDisabled={effective === 'place' && place.trim() === ''}
          onPress={() => void (effective === 'gps' ? searchGps() : searchPlace())}
        >
          查找附近的店
        </Button>
      </div>
      {busy === 'locating' && <LoadingState variant="list" text="正在取得定位" />}
      {busy === 'searching' && <LoadingState variant="list" text="正在查找附近的店" />}
      {!working && error && <ErrorState error={error.error} onRetry={retry} />}
      {!working && result && <Results result={result} />}
    </>
  )
}
