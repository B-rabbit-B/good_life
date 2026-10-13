// 医嘱条目按状态能做的动作（DESIGN.md 第四节的动作表）。这里只决定“哪个状态给哪些按钮”，
// 能不能做由后端判断；确认生效与确认解除只在医嘱页的确认面板里完成。界面上“删除”一律写作“作废”。
import type { MedicalItemOut } from '../../api/types'

export type ItemActionKind = 'void' | 'edit' | 'confirm' | 'continue' | 'cancel-proposal' | 'resolve'

export interface ItemAction {
  kind: ItemActionKind
  label: string
}

const LABELS: Record<ItemActionKind, string> = {
  void: '作废',
  edit: '修改',
  confirm: '确认生效',
  continue: '继续遵守',
  'cancel-proposal': '不解除',
  resolve: '确认解除',
}

const actions = (...kinds: ItemActionKind[]): ItemAction[] => kinds.map((kind) => ({ kind, label: LABELS[kind] }))

/**
 * 待核对：作废、修改、确认生效；待复核：继续遵守、确认解除（即使也带着解除建议）；
 * 生效中且有解除建议：不解除、确认解除（放在解除建议区里）；生效中没有建议：修改、确认解除；已解除与已作废：无。
 */
export function itemActionsFor(item: MedicalItemOut): ItemAction[] {
  switch (item.status) {
    case 'pending_confirmation':
      return actions('void', 'edit', 'confirm')
    case 'pending_review':
      return actions('continue', 'resolve')
    case 'active':
      return item.resolution_proposed_at !== null ? actions('cancel-proposal', 'resolve') : actions('edit', 'resolve')
    default:
      return []
  }
}

export interface ResolveSecondary {
  label: '继续遵守' | '不解除，撤销这条建议' | '取消'
  action: 'open-continue' | 'cancel-proposal' | 'close'
}

/** 解除面板的次按钮：待复核是“继续遵守”（打开继续遵守面板），带建议的生效条目撤销建议，其余只关闭 */
export function resolveSecondaryFor(item: MedicalItemOut): ResolveSecondary {
  if (item.status === 'pending_review') return { label: '继续遵守', action: 'open-continue' }
  if (item.resolution_proposed_at !== null) return { label: '不解除，撤销这条建议', action: 'cancel-proposal' }
  return { label: '取消', action: 'close' }
}
