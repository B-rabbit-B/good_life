import { useState } from 'react'
import { ApiError } from '../../api/errors'
import { useCancelProposal, useMedicalItems } from '../../api/hooks/medical'
import type { MedicalItemOut } from '../../api/types'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { useToast } from '../../components/Toast'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/medical.css'
import { ActiveItem } from './ActiveItem'
import { ContinueSheet } from './ContinueSheet'
import { ItemEditSheet } from './ItemEditSheet'
import { ResolveSheet } from './ResolveSheet'
import { useSheetHost } from './useSheetHost'

type ActiveSheet = { kind: 'resolve' | 'continue' | 'edit'; item: MedicalItemOut; dueReason: string | null }

// 待复核的排在最前，其次是带解除建议的，其余按后端的顺序
const rank = (item: MedicalItemOut) => (item.status === 'pending_review' ? 0 : item.resolution_proposed_at !== null ? 1 : 2)

/**
 * 生效中（07a）：生效中与待复核的条目写在一块瓷胎面板里。继续遵守、确认解除与修改都在底部面板里完成；
 * “不解除”直接撤销建议（不改变约束）。
 */
export function ActiveTab() {
  const items = useMedicalItems()
  const host = useSheetHost<ActiveSheet>()
  const cancel = useCancelProposal()
  const toast = useToast()
  const flight = useSingleFlight()
  const [keeping, setKeeping] = useState<string | null>(null)

  if (items.data === undefined) {
    if (items.isError) {
      const error = items.error instanceof ApiError ? items.error : new ApiError(0, 'unknown_error', String(items.error))
      return <div className="plate"><ErrorState error={error} onRetry={() => void items.refetch()} /></div>
    }
    return <LoadingState variant="list" text="正在读取生效中的医嘱" />
  }

  const list = items.data
    .filter((item) => item.status === 'active' || item.status === 'pending_review')
    .map((item, index) => ({ item, index }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.index - b.index)
    .map(({ item }) => item)

  const keep = (item: MedicalItemOut) => {
    const run = flight(() => {
      setKeeping(item.id)
      return cancel.mutateAsync(item.id)
    })
    run?.then(() => toast.show('已撤销解除建议'))
      .catch((caught: unknown) => toast.show(caught instanceof ApiError ? caught.message : '没能撤销，请稍后再试'))
      .finally(() => setKeeping(null))
  }

  const { sheet } = host
  return (
    <>
      <Sensitive area="content" className="plate">
        {list.length === 0 && <p className="mo-empty">没有生效中的医嘱。</p>}
        {list.map((item) => (
          <ActiveItem
            key={item.id} item={item} keepPending={keeping === item.id}
            onAction={(kind, dueReason) => {
              if (kind === 'cancel-proposal') keep(item)
              else if (kind === 'resolve' || kind === 'continue' || kind === 'edit') host.show({ kind, item, dueReason })
            }}
          />
        ))}
      </Sensitive>
      {sheet?.kind === 'resolve' && (
        <ResolveSheet
          key={host.nonce} item={sheet.item} isOpen={host.open} onClose={host.close}
          onContinue={() => host.show({ kind: 'continue', item: sheet.item, dueReason: sheet.dueReason })}
        />
      )}
      {sheet?.kind === 'continue' && (
        <ContinueSheet key={host.nonce} item={sheet.item} dueReason={sheet.dueReason} isOpen={host.open} onClose={host.close} />
      )}
      {sheet?.kind === 'edit' && <ItemEditSheet key={host.nonce} item={sheet.item} isOpen={host.open} onClose={host.close} />}
    </>
  )
}
