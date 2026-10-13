import { useId } from 'react'
import { ApiError } from '../../api/errors'
import { useOrders } from '../../api/hooks/medicalPage'
import type { MedicalItemOut, OrderOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Sensitive } from '../../components/Sensitive'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import '../../styles/components/medical.css'
import { ConfirmEffectSheet } from './ConfirmEffectSheet'
import { EvidenceViewer } from './EvidenceViewer'
import { ItemEditSheet } from './ItemEditSheet'
import { ManualItemSheet } from './ManualItemSheet'
import { OrderSource } from './OrderSource'
import { PendingItem } from './PendingItem'
import { useSheetHost } from './useSheetHost'
import { VoidSheet } from './VoidSheet'

type PendingSheet =
  | { kind: 'void' | 'edit' | 'confirm'; item: MedicalItemOut; order: OrderOut }
  | { kind: 'manual' | 'evidence'; order: OrderOut }

const isPending = (item: MedicalItemOut) => item.status === 'pending_confirmation'

function OrderGroup({ order, onSheet }: { order: OrderOut; onSheet: (sheet: PendingSheet) => void }) {
  const titleId = useId()
  return (
    <Sensitive as="section" area="content" className="plate" aria-labelledby={titleId}>
      <OrderSource order={order} titleId={titleId} onView={() => onSheet({ kind: 'evidence', order })} />
      {order.items.filter(isPending).map((item) => (
        <PendingItem
          key={item.id} item={item}
          onAction={(kind) => {
            if (kind === 'void' || kind === 'edit' || kind === 'confirm') onSheet({ kind, item, order })
          }}
        />
      ))}
      <div className="mo-add">
        <Button variant="text" icon="plus" onPress={() => onSheet({ kind: 'manual', order })}>手动补充一条</Button>
      </div>
    </Sensitive>
  )
}

/**
 * 待核对（07b）：按医嘱分组，每组是来源、逐条待核对的条目与“手动补充一条”。只列还有待核对条目的医嘱，
 * 以及一条也没提取出来的医嘱（好在它下面手动补充）。作废、修改、确认生效与手动补充都在底部面板里完成。
 */
export function PendingTab() {
  const orders = useOrders()
  const host = useSheetHost<PendingSheet>()
  if (orders.data === undefined) {
    if (orders.isError) {
      const error = orders.error instanceof ApiError ? orders.error : new ApiError(0, 'unknown_error', String(orders.error))
      return <div className="plate"><ErrorState error={error} onRetry={() => void orders.refetch()} /></div>
    }
    return <LoadingState variant="list" text="正在读取待核对的条目" />
  }
  const groups = orders.data.filter((order) => order.items.some(isPending) || order.items.length === 0)
  const { sheet } = host
  return (
    <>
      <p className="t-cap sec-cap">提取出来的条目要逐条核对，确认前不参与任何建议。</p>
      {groups.length === 0
        ? <div className="plate"><p className="mo-empty">没有待核对的条目。录入医嘱后，提取出的条目会出现在这里。</p></div>
        : groups.map((order) => <OrderGroup key={order.id} order={order} onSheet={host.show} />)}
      {sheet?.kind === 'void' && <VoidSheet key={host.nonce} item={sheet.item} isOpen={host.open} onClose={host.close} />}
      {sheet?.kind === 'edit' && <ItemEditSheet key={host.nonce} item={sheet.item} isOpen={host.open} onClose={host.close} />}
      {sheet?.kind === 'confirm' && (
        <ConfirmEffectSheet
          key={host.nonce} item={sheet.item} order={sheet.order} isOpen={host.open} onClose={host.close}
          onEdit={() => host.show({ kind: 'edit', item: sheet.item, order: sheet.order })}
        />
      )}
      {sheet?.kind === 'manual' && <ManualItemSheet key={host.nonce} order={sheet.order} isOpen={host.open} onClose={host.close} />}
      {sheet?.kind === 'evidence' && <EvidenceViewer key={host.nonce} order={sheet.order} isOpen={host.open} onClose={host.close} />}
    </>
  )
}
