import { useRef, useState } from 'react'
import type { ApiError } from '../../api/errors'
import { useCancelProposal } from '../../api/hooks/medical'
import { useOrders, useResolveItem } from '../../api/hooks/medicalPage'
import type { MedicalItemOut } from '../../api/types'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import type { WillItem } from '../../components/WillList'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { CATEGORY_LABELS } from '../../lib/labels'
import { ITEM_STATUS_LABELS } from '../../lib/medicalLabels'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { ONLY_HERE_NOTE, toApiError } from './ConfirmEffectSheet'
import { resolveSecondaryFor } from './itemActions'
import { sourceName } from './OrderSource'

// 结果播报之后多久关上面板（读屏读完“已解除：……”）
const RESULT_MS = 1200
export const RESOLVE_ACK = '我知道解除后不能撤销，需要重新录入才能恢复这条约束'

const wait = (ms: number) => new Promise<void>((resolve) => {
  setTimeout(resolve, ms)
})

/**
 * 确认解除（07d）：引文框写类别、内容与来源（开具日期与证据文件名或“原文”）；四条后果，最后一条“不能撤销”朱色；
 * 必须勾选“我知道解除后不能撤销……”，朱色的“确认解除”才可用，按下才发 POST /resolve（不带请求体）。
 * 次按钮按条目状态切换（resolveSecondaryFor）：待复核是“继续遵守”（换成继续遵守面板），带建议的是撤销这条建议，
 * 其余是“取消”。结果用 aria-live="assertive" 播报“已解除：内容。审计已记录。”，随后关上面板，条目移到“历史与审计”。
 */
export function ResolveSheet({ item, isOpen, onClose, onContinue }: {
  item: MedicalItemOut
  isOpen: boolean
  onClose: () => void
  /** 待复核的条目点“继续遵守”：换成继续遵守面板 */
  onContinue: () => void
}) {
  const orders = useOrders()
  const resolve = useResolveItem()
  const cancel = useCancelProposal()
  const toast = useToast()
  const flight = useSingleFlight()
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<string | undefined>(undefined)
  const resolved = useRef(false) // 已解除、正在播报结果：次按钮只关闭
  const order = orders.data?.find((o) => o.id === item.order_id)
  const secondary = resolveSecondaryFor(item)
  const proposedOn = item.resolution_proposed_at ? formatMonthDay(todayISO(new Date(item.resolution_proposed_at))) : null

  const will: WillItem[] = [
    { text: `这条医嘱从“${ITEM_STATUS_LABELS[item.status]}”变为“已解除”。` },
    { text: '之后的训练与饮食建议不再按它约束。' },
    { text: `记一条审计：时间、由你本人确认${proposedOn ? `，依据是 ${proposedOn} 的解除建议` : ''}。` },
    { text: '解除不能撤销。以后需要时，请重新录入。', irreversible: true },
  ]

  const onConfirm = async () => {
    setError(null)
    try {
      await resolve.mutateAsync(item.id)
    } catch (caught) {
      setError(toApiError(caught))
      throw caught
    }
    resolved.current = true
    setResult(`已解除：${item.content}。审计已记录。`)
    await wait(RESULT_MS)
    onClose()
  }

  const onSecondary = () => {
    if (resolved.current || secondary.action === 'close') {
      onClose()
      return
    }
    if (secondary.action === 'open-continue') {
      onContinue()
      return
    }
    const run = flight(() => cancel.mutateAsync(item.id))
    run?.then(() => {
      onClose()
      toast.show('已撤销解除建议')
    }).catch((caught: unknown) => setError(toApiError(caught)))
  }

  return (
    <ConfirmSheet
      isOpen={isOpen} onClose={onClose} titleKey="resolveSheet"
      quote={(
        <Sensitive area="content">
          <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
          <div className="mo-c">{item.content}</div>
          <span className="t-cap">来源：{order ? `${order.order_date} ` : ''}{sourceName(order)}</span>
        </Sensitive>
      )}
      will={will}
      ack={RESOLVE_ACK}
      confirmLabel="确认解除"
      confirmVariant="danger"
      secondary={{ label: secondary.label, onPress: onSecondary }}
      note={ONLY_HERE_NOTE}
      onConfirm={onConfirm}
      error={error}
      resultText={result}
    />
  )
}
