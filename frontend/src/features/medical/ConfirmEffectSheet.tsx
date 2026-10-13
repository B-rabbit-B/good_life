import { useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useConfirmItem } from '../../api/hooks/medicalPage'
import type { MedicalItemOut, OrderOut } from '../../api/types'
import { ConfirmSheet } from '../../components/ConfirmSheet'
import { Sensitive } from '../../components/Sensitive'
import { useToast } from '../../components/Toast'
import type { WillItem } from '../../components/WillList'
import { CATEGORY_LABELS, CONFIDENCE_LABELS } from '../../lib/labels'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { sourceName } from './OrderSource'

export const ONLY_HERE_NOTE = '医嘱只能在这里确认或解除，对话里无法完成。'


/**
 * 确认生效（07c）：引文框写类别、内容与来源（证据文件名或“原文”，提取把握），列出确认后会发生的四件事；
 * 只有按下面板里的“确认生效”才发 POST /confirm（不带请求体），打开面板不发任何请求。
 * 生效之后仍可修改或解除，所以不加勾选。“返回修改”换成修改面板。后端的错误（如 subjects_required）原样显示。
 */
export function ConfirmEffectSheet({ item, order, isOpen, onClose, onEdit }: {
  item: MedicalItemOut
  order: OrderOut | undefined
  isOpen: boolean
  onClose: () => void
  onEdit: () => void
}) {
  const confirm = useConfirmItem()
  const toast = useToast()
  const [error, setError] = useState<ApiError | null>(null)

  const will: WillItem[] = [
    { text: '状态从“待核对”变为“生效中”。' },
    { text: '之后的对话、拍照评价和附近餐厅推荐都按它约束。' },
    {
      text: item.end_date
        ? `预计结束 ${item.end_date}。结束前一天起进入待复核，那天打开应用时会提醒你。`
        : '没有预计结束日期，视为长期有效。',
    },
    { text: '记一条审计：时间、由你本人确认、来源与修改过的字段。' },
  ]

  const onConfirm = async () => {
    setError(null)
    try {
      await confirm.mutateAsync(item.id)
    } catch (caught) {
      setError(asApiError(caught))
      throw caught
    }
    onClose()
    toast.show('已确认生效，可在“生效中”查看')
  }

  return (
    <ConfirmSheet
      isOpen={isOpen} onClose={onClose} titleKey="confirmSheet"
      quote={(
        <Sensitive area="content">
          <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
          <div className="mo-c">{item.content}</div>
          <span className="t-cap">
            来源：{sourceName(order)}{item.confidence ? `，提取把握 ${CONFIDENCE_LABELS[item.confidence]}` : ''}
          </span>
        </Sensitive>
      )}
      will={will}
      confirmLabel="确认生效"
      secondary={{ label: '返回修改', onPress: onEdit }}
      note={ONLY_HERE_NOTE}
      onConfirm={onConfirm}
      error={error}
    />
  )
}
