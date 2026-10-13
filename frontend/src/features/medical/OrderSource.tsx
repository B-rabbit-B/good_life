import { useId, useState } from 'react'
import type { OrderOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { formatMonthDay, todayISO } from '../../lib/dates'
import '../../styles/components/fold.css'
import '../../styles/components/medical.css'

/** 医嘱的来源名：证据文件名（多个用顿号连起来），没有证据时是“原文” */
export function sourceName(order: OrderOut | undefined): string {
  if (!order || order.evidence.length === 0) return '原文'
  return order.evidence.map((file) => file.filename).join('、')
}

function thumbText(order: OrderOut): string {
  const first = order.evidence[0]
  if (!first) return '原文'
  return first.content_type === 'application/pdf' ? 'PDF' : '原图'
}

/**
 * 待核对里一组条目的来源（07b）：证据缩略或“原文”、录入日期与提取出几条、“查看”打开原文与证据；
 * 后端提取时没有用上的句子（ignored，带原因）与整份医嘱的说明（notes）原文折叠在“未提取的句子”里。
 * 折叠是一个带 aria-expanded 的按钮（不用 React Aria 的 Disclosure：对话页的依据折叠在首屏用它，
 * 这里再用会让它从对话页的块里拆出来）。
 */
export function OrderSource({ order, titleId, onView }: { order: OrderOut; titleId: string; onView: () => void }) {
  const [open, setOpen] = useState(false)
  const listId = useId()
  const extracted = order.items.filter((item) => item.origin === 'extracted').length
  const skipped = order.ignored.length + order.notes.length
  return (
    <>
      <div className="srcbox">
        <div className="src-img" aria-hidden="true">{thumbText(order)}</div>
        <div>
          <div className="src-t" id={titleId}>{sourceName(order)}</div>
          <div className="t-cap">{formatMonthDay(todayISO(new Date(order.created_at)))} 录入，提取出 {extracted} 条</div>
        </div>
        <Button variant="text" onPress={onView}>查看</Button>
      </div>
      {skipped > 0 && (
        <div className="src-fold">
          <button
            type="button" className="fold" aria-expanded={open} aria-controls={open ? listId : undefined}
            onClick={() => setOpen((value) => !value)}
          >
            <span>未提取的句子</span>
            <em>{skipped}</em>
            <span className="sp" />
            <Icon name="down" size={18} />
          </button>
          {open && (
            <ul className="ev" id={listId}>
              {order.notes.map((note) => <li key={`n-${note}`}>{note}</li>)}
              {order.ignored.map((sentence) => (
                <li key={`i-${sentence.text}`}>{sentence.text}<small>{sentence.reason}</small></li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  )
}
