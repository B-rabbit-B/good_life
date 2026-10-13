import type { RestaurantSearchOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { VerdictMark } from '../../components/VerdictMark'
import { fmtDistance } from '../../lib/format'

type Shop = RestaurantSearchOut['restaurants'][number]
type Advice = RestaurantSearchOut['type_advice'][number]

const ADVICE_LINES = [['order', '可点'], ['moderate', '适量'], ['avoid', '应避开']] as const

/** 一家店的建议：按同类型的 type_advice 写“可点 / 适量 / 应避开”（顿号连接，空的不写）；判断不出类型时只写 tip 原文。 */
function ShopAdvice({ shop, advice }: { shop: Shop; advice: Advice | undefined }) {
  if (shop.type_key === null || !advice) return shop.tip ? <p className="shop-o">{shop.tip}</p> : null
  const lines = ADVICE_LINES.filter(([key]) => advice[key].length > 0)
  if (lines.length === 0) return null
  return (
    <p className="shop-o">
      {lines.map(([key, label], i) => (
        <span key={key}>
          {i > 0 && <br />}
          <b>{label}</b>
          {advice[key].join('、')}
        </span>
      ))}
    </p>
  )
}

/** 店铺写在一块面板里：店名、结论、类型、距离、建议，右侧 56 的导航瓷扣（在新窗口打开后端给的导航链接）。 */
export function ShopList({ result }: { result: RestaurantSearchOut }) {
  const advice = new Map(result.type_advice.map((item) => [item.type_key, item]))
  return (
    <ul className="plate shops" aria-label="附近的店">
      {result.restaurants.map((shop) => (
        <li key={shop.id} className="shop">
          <span className="shop-n">{shop.name}</span>
          <span className="shop-m">
            <VerdictMark conclusion={shop.conclusion} />
            {shop.type_name && <span>{shop.type_name}</span>}
            {shop.distance_m !== null && <span className="n">{fmtDistance(shop.distance_m)}</span>}
          </span>
          <ShopAdvice shop={shop} advice={shop.type_key === null ? undefined : advice.get(shop.type_key)} />
          <a className="navb" href={shop.nav_url} target="_blank" rel="noopener noreferrer" aria-label={`导航到${shop.name}`}>
            <Icon name="nav" size={20} />
            导航
          </a>
        </li>
      ))}
    </ul>
  )
}
