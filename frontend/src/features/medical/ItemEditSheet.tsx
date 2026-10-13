import { useRef, useState } from 'react'
import { ApiError } from '../../api/errors'
import { useUpdateItem } from '../../api/hooks/medicalPage'
import type { ItemUpdate, MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { DateField } from '../../components/DateField'
import { Icon } from '../../components/Icon'
import { SelectField } from '../../components/SelectField'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { TagField } from '../../components/TagField'
import { TextField } from '../../components/TextField'
import { useToast } from '../../components/Toast'
import { INVALID_DATE_REASONS, MAX_CONTENT, SUBJECTS_REQUIRED } from '../../lib/contract'
import { CATEGORY_LABELS, type ItemCategory } from '../../lib/labels'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/medical.css'
import { errorsOf, FORM_ERROR, otherErrors } from '../onboarding/fieldErrors'

// app/medical/schemas.py：内容最多 500 个字

export interface ItemFormValues {
  category: ItemCategory
  content: string
  subjects: string[]
  start_date: string | null
  end_date: string | null
  review_date: string | null
}

const FIELD_LABELS: Record<string, string> = {
  category: '类别', content: '内容', subjects: '涉及', start_date: '生效日期', end_date: '预计结束', review_date: '复查日期',
}
const CATEGORY_OPTIONS = (Object.keys(CATEGORY_LABELS) as ItemCategory[]).map((value) => ({ value, label: CATEGORY_LABELS[value] }))

/** 后端的错误写在哪个字段下：字段校验按字段名；日期前后不对按说明原文（contract.ts）；缺涉及对象写在“涉及”下 */
function itemErrors(error: unknown): Record<string, string> {
  if (error instanceof ApiError && error.code === 'invalid_item_dates') {
    const field = INVALID_DATE_REASONS[error.message]
    return { [field === 'end' ? 'end_date' : field === 'review' ? 'review_date' : FORM_ERROR]: error.message }
  }
  if (error instanceof ApiError && error.code === SUBJECTS_REQUIRED) return { subjects: error.message }
  return errorsOf(error)
}

function ClearableDate({ label, value, onChange, error, placeholder }: {
  label: string
  value: string | null
  onChange: (value: string | null) => void
  error?: string
  placeholder: string
}) {
  return (
    <div className="mo-date">
      <DateField label={label} value={value} onChange={onChange} placeholder={placeholder} error={error} />
      {value !== null && (
        <button type="button" className="btn-txt mo-date-x" aria-label={`清除${label}`} onClick={() => onChange(null)}>清除</button>
      )}
    </div>
  )
}

/**
 * 条目表单（修改与手动补充共用）：类别、内容、涉及、生效日期、预计结束、复查日期。提交交给 onSubmit；
 * 失败时后端的说明原文写在对应字段下，其余写在按钮上方（带错误码）。
 */
export function ItemForm({ initial, onSubmit, onClose }: {
  initial: ItemFormValues
  onSubmit: (values: ItemFormValues) => Promise<unknown>
  onClose: () => void
}) {
  const [values, setValues] = useState(initial)
  const [error, setError] = useState<unknown>(null)
  const [pending, setPending] = useState(false)
  const flight = useSingleFlight()
  const saved = useRef(false) // 保存成功、面板正在关上时不再保存
  const errors = itemErrors(error)
  const set = <K extends keyof ItemFormValues>(key: K) => (value: ItemFormValues[K]) => setValues((v) => ({ ...v, [key]: value }))
  const others = otherErrors(errors, ['category', 'content', 'subjects', 'start_date', 'end_date', 'review_date'], FIELD_LABELS)

  const save = () => {
    if (saved.current) return
    const run = flight(() => {
      setPending(true)
      setError(null)
      return onSubmit({ ...values, content: values.content.trim() })
    })
    run?.then(() => {
      saved.current = true
      onClose()
    })
      .catch((caught: unknown) => setError(caught))
      .finally(() => setPending(false))
  }

  return (
    <div className="mo-form">
      {/* 医嘱内容：遮盖时一起盖住（按钮在外面，盖住时仍能关上面板） */}
      <Sensitive area="content">
        <SelectField
          label="类别" value={values.category} options={CATEGORY_OPTIONS} onChange={(v) => set('category')(v as ItemCategory)}
        />
        <TextField
          label="内容" value={values.content} onChange={set('content')} multiline rows={3} maxLength={MAX_CONTENT}
          error={errors.content}
        />
        <TagField label="涉及的食物或行为" tags={values.subjects} onChange={set('subjects')} error={errors.subjects} />
        <DateField label="生效日期" value={values.start_date} onChange={set('start_date')} error={errors.start_date} />
        <ClearableDate
          label="预计结束" value={values.end_date} onChange={set('end_date')} error={errors.end_date} placeholder="不设（长期有效）"
        />
        <ClearableDate
          label="复查日期" value={values.review_date} onChange={set('review_date')} error={errors.review_date} placeholder="不设"
        />
      </Sensitive>
      {others.length > 0 && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>
            {others.map((message) => <span key={message} className="form-err-line">{message}</span>)}
            {error instanceof ApiError && <small>错误码 {error.code}</small>}
          </span>
        </div>
      )}
      <div className="sheet-foot">
        <Button variant="primary" block isPending={pending} onPress={save}>保存</Button>
        <Button variant="quiet" block onPress={onClose}>取消</Button>
      </div>
    </div>
  )
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((value, i) => value === b[i])

/** 只取改动了的字段（结束日期与复查日期清空时发 null） */
export function changedFields(item: MedicalItemOut, values: ItemFormValues): ItemUpdate {
  const changes: ItemUpdate = {}
  if (values.category !== item.category) changes.category = values.category
  if (values.content !== item.content) changes.content = values.content
  if (!sameList(values.subjects, item.subjects)) changes.subjects = values.subjects
  if (values.start_date !== item.start_date) changes.start_date = values.start_date
  if (values.end_date !== item.end_date) changes.end_date = values.end_date
  if (values.review_date !== item.review_date) changes.review_date = values.review_date
  return changes
}

function EditBody({ item, onClose }: { item: MedicalItemOut; onClose: () => void }) {
  const update = useUpdateItem()
  const toast = useToast()
  const submit = async (values: ItemFormValues) => {
    const changes = changedFields(item, values)
    if (Object.keys(changes).length === 0) return
    await update.mutateAsync({ id: item.id, changes })
    toast.show('已保存修改')
  }
  return (
    <ItemForm
      initial={{
        category: item.category, content: item.content, subjects: item.subjects,
        start_date: item.start_date, end_date: item.end_date, review_date: item.review_date,
      }}
      onSubmit={submit}
      onClose={onClose}
    />
  )
}

/** 修改一条医嘱（底部面板）：只发改动了的字段（PATCH），每次修改都记审计。 */
export function ItemEditSheet({ item, isOpen, onClose }: { item: MedicalItemOut; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} titleKey="editItem">
      <EditBody item={item} onClose={onClose} />
    </Sheet>
  )
}
