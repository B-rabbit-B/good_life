import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { CATEGORY_LABELS, CONFIDENCE_LABELS } from '../../lib/labels'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { itemActionsFor, type ItemActionKind } from './itemActions'

// 值为空时写清确认后的后果（这是对“值为空”的说明，不是规则判断）
const NO_END = '没有写明。确认后视为长期有效，可先补上'
const NO_REVIEW = '没有写明。确认后不设复查日期，可先补上'
const NO_SUBJECTS = '原文没有写明涉及的食物或行为，确认前需要补上'

/**
 * 一条待核对的条目（07b）：类别与“待核对”；有预计结束日期时赭色写明过了那天仍未确认会自动作废；原文（浅灰圆角框）；
 * 字段表（提取内容、涉及、生效日期、预计结束、复查日期、提取把握）；提取时的说明原文；动作“作废”“修改”“确认生效”。
 */
export function PendingItem({ item, onAction }: { item: MedicalItemOut; onAction: (kind: ItemActionKind) => void }) {
  const subjectsMissing = item.missing_fields.includes('subjects')
  return (
    <div className="mo">
      <div className="mo-h">
        <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
        <span className="mo-st pend">待核对</span>
      </div>
      {item.end_date && <p className="t-small mo-expire">{item.end_date} 之后仍未确认，会自动作废</p>}
      {item.source_excerpt && (
        <>
          <p className="t-cap mo-orig-l">原文</p>
          <div className="orig">{item.source_excerpt}</div>
        </>
      )}
      <dl className="fields">
        <dt>{item.origin === 'extracted' ? '提取内容' : '内容'}</dt>
        <dd className="mo-v">{item.content}</dd>
        <dt>涉及</dt>
        {item.subjects.length > 0
          ? <dd>{item.subjects.join('、')}</dd>
          : <dd className={subjectsMissing ? 'miss' : 'mute'}>{subjectsMissing ? NO_SUBJECTS : '未填写'}</dd>}
        <dt>生效日期</dt>
        <dd className="n">{item.start_date}</dd>
        <dt>预计结束</dt>
        {item.end_date ? <dd className="n">{item.end_date}</dd> : <dd className="miss">{NO_END}</dd>}
        <dt>复查日期</dt>
        {item.review_date ? <dd className="n">{item.review_date}</dd> : <dd className="miss">{NO_REVIEW}</dd>}
        {item.confidence && (
          <>
            <dt>提取把握</dt>
            <dd>{CONFIDENCE_LABELS[item.confidence]}</dd>
          </>
        )}
      </dl>
      {item.notes.length > 0 && <ul className="mo-notes">{item.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
      <div className="acts-r">
        {itemActionsFor(item).map(({ kind, label }) => {
          if (kind === 'void') return <Button key={kind} variant="text" ink onPress={() => onAction(kind)}>{label}</Button>
          if (kind === 'edit') {
            return <Button key={kind} variant="quiet" size="sm" icon="edit" onPress={() => onAction(kind)}>{label}</Button>
          }
          return <Button key={kind} variant="primary" size="sm" onPress={() => onAction(kind)}>{label}</Button>
        })}
      </div>
    </div>
  )
}
