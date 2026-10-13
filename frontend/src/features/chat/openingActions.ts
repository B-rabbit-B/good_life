// 开场卡片的动作：按开场类别给“去处理”的入口（只是跳转或打开继续遵守面板）和一个拒绝。
// 入口所在的模块没有开放时不给那个入口；不认识的类别只有“不用了”。
import type { Capabilities, MedicalItemOut, OpeningOut } from '../../api/types'
import { addDays, todayISO } from '../../lib/dates'

export interface OpeningAction {
  label: string
  kind: 'continue' | 'navigate' | 'decline'
  to?: string
}

const go = (label: string, to: string): OpeningAction => ({ label, kind: 'navigate', to })
const decline = (label: string): OpeningAction => ({ label, kind: 'decline' })

/**
 * target 是待处理列表的第一条（后端的 review_due 开场就是按它问的）：它真的待复核时才给“继续遵守”；
 * 只带解除建议的条目只给“去医嘱页处理”与“稍后”。
 */
export function openingActionsFor(
  opening: OpeningOut, target: MedicalItemOut | undefined, caps: Capabilities, now: Date = new Date(),
): OpeningAction[] {
  switch (opening.kind) {
    case 'review_due':
      return [
        ...(caps.medical && target?.status === 'pending_review' ? [{ label: '继续遵守', kind: 'continue' } as const] : []),
        ...(caps.medical ? [go('去医嘱页处理', '/health/medical?tab=active')] : []),
        decline('稍后'),
      ]
    case 'period_soon':
      return [...(caps.cycle ? [go('看看安排', '/health/cycle')] : []), decline('不用了')]
    case 'trained_no_meal_yesterday':
      return [
        ...(caps.nutrition ? [go('去补记', `/records/meals/new?date=${addDays(todayISO(now), -1)}`)] : []),
        decline('不用了'),
      ]
    case 'no_meal_today':
      return [
        ...(caps.nutrition ? [go('拍一张', '/photos/new'), go('手动记', '/records/meals/new')] : []),
        decline('不用了'),
      ]
    case 'profile_stale':
      return [go('更新档案', '/me/profile'), decline('不用了')]
    default:
      return [decline('不用了')]
  }
}
