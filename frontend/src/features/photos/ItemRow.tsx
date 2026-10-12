import { useState } from 'react'
import { Radio, RadioGroup } from 'react-aria-components'
import type { PhotoItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { ConfidenceCells } from '../../components/ConfidenceCells'
import { VerdictMark } from '../../components/VerdictMark'
import { fmtNum } from '../../lib/format'
import { REVIEW_REASON_LABELS, type Conclusion } from '../../lib/labels'

const reasonLabel = (code: string) => (REVIEW_REASON_LABELS as Record<string, string>)[code] ?? code

/**
 * 一个识别项（设计稿 04b 的账目行）：菜名与评价里这一项的结论、热量（待确认的写“待确认”）、
 * 份量说法与克数（克数是估算的写“（估算）”）、把握程度、营养库里对应的食物。
 * 后端给了 review_reasons 的项左侧一道赭色竖线，原因逐条写出，可以修改或删除；
 * 待确认的项内嵌候选单选（选中即提交 food_id），也可以改名或删除。只读时没有动作。
 */
export function ItemRow({ item, conclusion, editable, busy, onEdit, onDelete, onPick }: {
  item: PhotoItemOut
  /** 整餐评价里这一项的结论（只有已匹配的项有） */
  conclusion?: Conclusion
  editable: boolean
  busy: boolean
  onEdit: (item: PhotoItemOut) => void
  onDelete: (item: PhotoItemOut) => void
  /** 选中候选；失败时拒绝（单选恢复为未选） */
  onPick: (item: PhotoItemOut, foodId: string) => Promise<unknown>
}) {
  const [picked, setPicked] = useState<string | null>(null)
  const flagged = item.review_reasons.length > 0
  const waiting = item.status === 'needs_confirmation'
  const kcal = item.nutrients?.energy_kcal ?? null
  const pick = (foodId: string) => {
    setPicked(foodId)
    onPick(item, foodId).catch(() => setPicked(null))
  }
  return (
    <div className={flagged ? 'item flag' : 'item'} data-item-id={item.id} tabIndex={-1}>
      <span className="item-n">
        <span>{item.name}</span>
        {conclusion && <VerdictMark conclusion={conclusion} />}
      </span>
      {waiting
        ? <span className="item-k wait">待确认</span>
        : <span className="item-k ns">{kcal === null ? '—' : fmtNum(kcal, 1)}<small>千卡</small></span>}
      <span className="item-m">
        <span>
          {item.portion_text ? `${item.portion_text}，` : ''}
          <span className="n">{fmtNum(item.grams, 1)}</span> 克{item.review_reasons.includes('estimated_grams') ? '（估算）' : ''}
        </span>
        <ConfidenceCells value={item.confidence} />
        {item.food_name && <span>营养库：{item.food_name}</span>}
      </span>
      {flagged && (
        <ul className="why">
          {item.review_reasons.map((code) => <li key={code}>{reasonLabel(code)}</li>)}
        </ul>
      )}
      {editable && waiting && (
        <div className="cands">
          {item.candidates.length > 0 && (
            <RadioGroup aria-label="选择对应的食物" value={picked} onChange={pick} isDisabled={busy}>
              {item.candidates.map((candidate) => (
                <Radio key={candidate.food_id} value={candidate.food_id} className="cand">
                  {({ isSelected }) => (
                    <>
                      <span className={isSelected ? 'radio on' : 'radio'} aria-hidden="true" />
                      {candidate.name}
                    </>
                  )}
                </Radio>
              ))}
            </RadioGroup>
          )}
          <div className="cand-acts">
            <Button variant="text" isDisabled={busy} onPress={() => onEdit(item)}>改个名字</Button>
            <Button variant="text" ink isDisabled={busy} onPress={() => onDelete(item)}>删除这一项</Button>
          </div>
        </div>
      )}
      {editable && flagged && !waiting && (
        <span className="acts">
          <Button variant="text" isDisabled={busy} onPress={() => onEdit(item)}>修改</Button>
          <Button variant="text" ink isDisabled={busy} onPress={() => onDelete(item)}>删除这一项</Button>
        </span>
      )}
    </div>
  )
}
