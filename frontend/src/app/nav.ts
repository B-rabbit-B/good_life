// 底部导航与分段只看后端的能力清单：经期入口只对开放经期模块的用户显示；经期与医嘱都不开放时“健康”隐藏，导航变三项。
import type { Capabilities } from '../api/types'
import type { NavItem } from '../components/BottomNav'
import { PATHS } from './paths'

export type { NavItem }

export function navItems(caps: Capabilities): NavItem[] {
  const items: NavItem[] = [{ key: 'chat', label: '对话', to: PATHS.chat }]
  if (caps.nutrition || caps.fitness) items.push({ key: 'records', label: '记录', to: PATHS.records })
  if (caps.cycle || caps.medical) items.push({ key: 'health', label: '健康', to: PATHS.health })
  items.push({ key: 'me', label: '我的', to: PATHS.me })
  return items
}

/** 健康页的分段：经期在前、医嘱在后；只有一段时页面不显示分段控件。 */
export function healthSegments(caps: Capabilities): ('cycle' | 'medical')[] {
  return [...(caps.cycle ? ['cycle' as const] : []), ...(caps.medical ? ['medical' as const] : [])]
}

/** 记录页的分段：饮食在前、训练在后。 */
export function recordSegments(caps: Capabilities): ('diet' | 'training')[] {
  return [...(caps.nutrition ? ['diet' as const] : []), ...(caps.fitness ? ['training' as const] : [])]
}
