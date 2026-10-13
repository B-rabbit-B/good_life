import { useEffect, useId, useRef, useState } from 'react'
import { ApiError, asApiError } from '../../api/errors'
import { useContinueItem } from '../../api/hooks/medical'
import type { MedicalItemOut } from '../../api/types'
import type { SensitiveArea } from '../../app/sensitiveAreas'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { useToast } from '../../components/Toast'
import { WillList, type WillItem } from '../../components/WillList'
import { INVALID_DATE_REASONS, STILL_DUE } from '../../lib/contract'
import { addMonths, todayISO } from '../../lib/dates'
import { useSingleFlight } from '../../lib/singleFlight'
import { CATEGORY_LABELS } from '../../lib/labels'
import '../../styles/components/continue.css'
import '../../styles/components/field-input.css'
import '../../styles/components/medical-item.css'
import { dueFieldOf } from '../../api/itemContext/dueReason'

type DateKey = 'review' | 'end'

export interface ContinueSheetProps {
  item: MedicalItemOut
  /** 后端写的到期原因原文；用它标出触发复核的那一项 */
  dueReason: string | null
  isOpen: boolean
  onClose: () => void
  onDone?: () => void
  /**
   * 引文框（医嘱原文）所在敏感区的名字，按打开它的页面登记表里的区域：医嘱页是 content（默认），
   * 对话页从开场卡片打开是 opening、从待处理条打开是 reviewBar
   */
  area?: SensitiveArea
}

/** 错误写在哪里：still_due 写在触发项下，invalid_item_dates 与字段校验写在对应字段下，其余写在按钮上方 */
function errorPlace(error: ApiError, trigger: DateKey | null): DateKey | 'form' {
  if (error.code === STILL_DUE) return trigger ?? 'form'
  if (error.code === 'invalid_item_dates') return INVALID_DATE_REASONS[error.message] ?? 'form'
  const field = error.details?.[0]?.field.split('.').pop()
  if (error.code === 'validation_error' && field === 'review_date') return 'review'
  if (error.code === 'validation_error' && field === 'end_date') return 'end'
  return 'form'
}

function ErrorLine({ error, id }: { error: ApiError; id?: string }) {
  return (
    <div className="err" role="alert" id={id}>
      <Icon name="alert" size={18} />
      <span>{error.message}<small>错误码 {error.code}</small></span>
    </div>
  )
}

/** 一个日期框：原生 input type=date 铺满 .sel 圆角框，点哪里都调起系统日期选择器 */
function DateBox({ id, value, empty, invalid, errorId, onChange }: {
  id: string
  value: string | null
  empty: string
  invalid: boolean
  errorId: string
  onChange: (value: string | null) => void
}) {
  return (
    <span className={invalid ? 'sel dt-sel bad' : 'sel dt-sel'}>
      <span className={value ? 'n' : 'mute'} aria-hidden="true">{value ?? empty}</span>
      <Icon name="cal" size={18} />
      <input
        id={id} type="date" value={value ?? ''}
        aria-invalid={invalid || undefined} aria-describedby={invalid ? errorId : undefined}
        onChange={(event) => onChange(event.target.value || null)}
        onClick={(event) => {
          try {
            event.currentTarget.showPicker()
          } catch {
            // 不支持 showPicker 的浏览器点击输入框本身就会打开
          }
        }}
      />
    </span>
  )
}

function endConsequence(original: string | null, next: string | null): string {
  if (next === null) return original === null ? '预计结束保持不设，继续长期有效。' : '预计结束改为不设，长期有效。'
  if (next === original) return `预计结束保持 ${next}，结束前一天起进入待复核。`
  return `预计结束改为 ${next}，结束前一天起进入待复核。`
}

function ContinueBody({ item, dueReason, onClose, onDone, area = 'content' }: Omit<ContinueSheetProps, 'isOpen'>) {
  const trigger = dueFieldOf(dueReason)
  const today = todayISO()
  const oneMonth = addMonths(today, 1)
  const threeMonths = addMonths(today, 3)
  const [review, setReview] = useState<string | null>(trigger === 'review' ? oneMonth : item.review_date)
  const [end, setEnd] = useState<string | null>(item.end_date)
  const [error, setError] = useState<ApiError | null>(null)
  const continueItem = useContinueItem()
  const toast = useToast()
  const reviewId = useId()
  const endId = useId()
  const errorId = useId()

  const will: WillItem[] = [
    { text: '状态从‘待复核’回到‘生效中’，建议继续按它约束。' },
    { text: review === null ? '不再设复查日期。' : `复查日期改为 ${review}，那天打开应用时会再次提醒复核。` },
    { text: endConsequence(item.end_date, end) },
    { text: '记一条审计：时间、由你本人确认、两个新日期。' },
  ]

  // 同一帧连按两次时 isPending 还没渲染出来：用单飞锁守住，只发一次；成功后面板关上的这段时间也不再提交
  const flight = useSingleFlight()
  const done = useRef(false)
  const submit = () => {
    if (done.current) return
    const run = flight(async () => {
      setError(null)
      try {
        // 两个键永远都带上：后端会同时覆盖复查日期与预计结束，没提交的那项会被清空
        await continueItem.mutateAsync({ id: item.id, review_date: review, end_date: end })
      } catch (caught) {
        setError(asApiError(caught))
        return
      }
      done.current = true
      onClose()
      toast.show('已继续遵守')
      onDone?.()
    })
    void run
  }

  const place = error ? errorPlace(error, trigger) : null
  // 出错的日期框：写着说明的那一项标红并把焦点移过去（still_due 时就是触发复核的那一项）
  useEffect(() => {
    if (place === 'review' || place === 'end') document.getElementById(place === 'review' ? reviewId : endId)?.focus()
  }, [error, place, reviewId, endId])
  const why = (key: DateKey, fallback?: string) =>
    trigger === key && dueReason ? <span className="dt-why">{dueReason}</span> : fallback && <span className="dt-why">{fallback}</span>

  return (
    <>
      <Sensitive area={area} className="quote cs-quote">
        <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
        <div className="mo-c">{item.content}</div>
        <span className="t-cap">生效 {item.start_date}</span>
      </Sensitive>
      <p className="t-small cs-note">两个日期一起提交，留空的一项会被清除。</p>

      <div className={trigger === 'review' ? 'dt-row due' : 'dt-row'}>
        <div className="dt-l"><label htmlFor={reviewId}>复查日期</label>{why('review')}</div>
        <div className="dt-v">
          <span className="dt-old">原 {item.review_date ?? '未设'}</span>
          <DateBox
            id={reviewId} value={review} empty="不再设" invalid={place === 'review'} errorId={errorId} onChange={setReview}
          />
        </div>
        <div className="dt-quick" role="group" aria-label="复查日期快捷选择">
          <button type="button" className="btn-txt" aria-pressed={review === oneMonth} onClick={() => setReview(oneMonth)}>1 个月后</button>
          <button type="button" className="btn-txt" aria-pressed={review === threeMonths} onClick={() => setReview(threeMonths)}>3 个月后</button>
          <button type="button" className="btn-txt ink" aria-pressed={review === null} onClick={() => setReview(null)}>不再设</button>
        </div>
        {error && place === 'review' && <ErrorLine error={error} id={errorId} />}
      </div>

      <div className={trigger === 'end' ? 'dt-row due' : 'dt-row'}>
        <div className="dt-l">
          <label htmlFor={endId}>预计结束</label>
          {why('end', item.end_date === null ? '原来没有设，表示长期有效' : undefined)}
        </div>
        <div className="dt-v">
          <span className="dt-old">原 {item.end_date ?? '未设'}</span>
          <DateBox
            id={endId} value={end} empty="不设（长期）" invalid={place === 'end'} errorId={errorId} onChange={setEnd}
          />
        </div>
        {error && place === 'end' && <ErrorLine error={error} id={errorId} />}
      </div>

      <div className="cs-will"><WillList items={will} /></div>
      {error && place === 'form' && <ErrorLine error={error} />}
      <div className="sheet-foot">
        <Button variant="primary" block isPending={continueItem.isPending} onPress={submit}>继续遵守</Button>
        <Button variant="quiet" block onPress={onClose}>取消</Button>
      </div>
    </>
  )
}

/**
 * 继续遵守面板（03d）：引文框写类别、内容与生效日期；复查日期与预计结束两项都显示、预填，并写“原 某日”或“原 未设”；
 * 触发这次复核的一项用赭色圆头竖线标出并写后端的到期原因原文。提交永远同时带 review_date 与 end_date。
 * 成功后关闭面板、轻提示“已继续遵守”，再调用 onDone。
 */
export function ContinueSheet({ isOpen, onClose, ...body }: ContinueSheetProps) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} titleKey="continueSheet">
      <ContinueBody onClose={onClose} {...body} />
    </Sheet>
  )
}

export default ContinueSheet
