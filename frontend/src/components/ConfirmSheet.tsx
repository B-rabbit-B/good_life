import { useState, type ReactNode } from 'react'
import type { ApiError } from '../api/errors'
import { useSingleFlight } from '../lib/singleFlight'
import '../styles/components/field-input.css'
import { Button } from './Button'
import { Checkbox } from './Checkbox'
import { Icon } from './Icon'
import { Sheet, type SheetTitle } from './Sheet'
import { WillList, type WillItem } from './WillList'

export type ConfirmSheetProps = SheetTitle & {
  isOpen: boolean
  onClose: () => void
  /** 引文框里的原文（医嘱内容、来源） */
  quote?: ReactNode
  /** “确认后会发生”清单 */
  will?: WillItem[]
  confirmLabel: string
  confirmVariant?: 'primary' | 'danger'
  /** 必须勾选的一句话（不可撤销的动作），勾选后确认按钮才可用 */
  ack?: string
  secondary?: { label: string; onPress: () => void }
  note?: string
  onConfirm: () => Promise<void>
  error?: ApiError | null
  /** 结果写进 aria-live="assertive" 区域 */
  resultText?: string
}

function ConfirmBody({ quote, will, confirmLabel, confirmVariant, ack, secondary, note, onConfirm, onClose, error, resultText }:
  Omit<ConfirmSheetProps, 'isOpen' | 'titleKey' | 'title'>) {
  const [acked, setAcked] = useState(false)
  const [pending, setPending] = useState(false)
  // 双击时 pending 还没来得及渲染，第二次按下照样会进来：用 ref 守住，同一时间只确认一次
  const flight = useSingleFlight()
  const confirm = () => {
    const run = flight(() => {
      setPending(true)
      return onConfirm()
    })
    // 失败由调用方通过 error 显示；这里吞掉拒绝，免得成为未处理的 Promise 拒绝（例如传入 mutation.mutateAsync）
    void run?.catch(() => {}).finally(() => setPending(false))
  }
  return (
    <>
      {quote && <div className="quote">{quote}</div>}
      {will && will.length > 0 && (
        <>
          <p className="sheet-lead">确认后会发生：</p>
          <WillList items={will} />
        </>
      )}
      {ack && <Checkbox isSelected={acked} onChange={setAcked}>{ack}</Checkbox>}
      {error && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>{error.message}<small>错误码 {error.code}</small></span>
        </div>
      )}
      <div className="sheet-foot">
        <Button
          variant={confirmVariant === 'danger' ? 'danger' : 'primary'} block
          isDisabled={Boolean(ack) && !acked} isPending={pending} onPress={confirm}
        >
          {confirmLabel}
        </Button>
        {secondary
          ? <Button variant="quiet" block onPress={secondary.onPress}>{secondary.label}</Button>
          : <Button variant="quiet" block onPress={onClose}>取消</Button>}
      </div>
      <p className="note" aria-live="assertive">{resultText ?? note}</p>
    </>
  )
}

/**
 * 关键动作的二次确认面板：引文框、“确认后会发生”清单、（不可撤销时）必勾的一句话、确认按钮与次按钮。
 * 确认中按钮不可重复点；失败时在按钮上方原样显示后端说明与错误码；结果用 aria-live="assertive" 播报。
 */
export function ConfirmSheet({ isOpen, onClose, titleKey, title, ...body }: ConfirmSheetProps) {
  const heading: SheetTitle = titleKey ? { titleKey } : { title: title ?? '' }
  return (
    <Sheet isOpen={isOpen} onClose={onClose} {...heading}>
      <ConfirmBody onClose={onClose} {...body} />
    </Sheet>
  )
}
