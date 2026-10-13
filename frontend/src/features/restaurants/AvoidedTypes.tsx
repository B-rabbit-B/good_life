import { useId } from 'react'
import type { RestaurantSearchOut } from '../../api/types'
import { RefTag } from '../../components/RefTag'
import { Title } from '../../components/Title'
import { SOURCE_NAMES } from '../../lib/contract'

type Avoided = RestaurantSearchOut['avoided_types'][number]

/**
 * 已避开的类型（与店铺列表分开）：类型名（朱色删除线）、被避开的店名，
 * 每条原因写“{来源} 代表菜“{菜名}”：{说明原文}”。
 */
export function AvoidedTypes({ types }: { types: Avoided[] }) {
  const id = useId()
  return (
    <section aria-labelledby={id}>
      <div className="sec-h">
        <Title k="avoided" level="h" id={id} />
        <RefTag />
      </div>
      <div className="plate">
        {types.map((type) => (
          <div key={type.type_key} className="avd">
            <div className="avd-h">
              <b>{type.type_name}</b>
              <span className="t-cap">{type.restaurants.join('、')}</span>
            </div>
            {type.reasons.map((reason) => (
              <p key={`${reason.code}-${reason.ref}-${reason.food_name}`}>
                <span className="src">{SOURCE_NAMES[reason.source] ?? reason.source}</span>
                代表菜“{reason.food_name}”：{reason.message}
              </p>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}
