import { useRef, useState } from 'react'
import { ApiError } from '../../api/errors'
import type { PhotoItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Sheet } from '../../components/Sheet'
import { TextField } from '../../components/TextField'
import { MAX_NAME_LENGTH } from '../../lib/contract'
import { fmtNum } from '../../lib/format'
import { useSingleFlight } from '../../lib/singleFlight'
import { errorsOf, FORM_ERROR, otherErrors } from '../onboarding/fieldErrors'
import { FormError } from '../onboarding/FormError'
import type { ItemChange } from './itemsUpdate'

type EditChange = Extract<ItemChange, { kind: 'edit' }>


const FIELD_LABELS: Record<string, string> = { name: '菜名', portion_text: '份量说法', grams: '克数' }

function EditForm({ item, onClose, onSave }: {
  item: PhotoItemOut
  onClose: () => void
  onSave: (change: EditChange) => Promise<unknown>
}) {
  const [name, setName] = useState(item.name)
  const [portion, setPortion] = useState(item.portion_text)
  const original = fmtNum(item.grams, 1).replace(/,/g, '')
  const [grams, setGrams] = useState(original)
  const [error, setError] = useState<unknown>(null)
  const [pending, setPending] = useState(false)
  const flight = useSingleFlight()
  const saved = useRef(false) // 保存成功、面板正在关上时不再保存
  const errors = errorsOf(error)

  const save = () => {
    const change: EditChange = { kind: 'edit', id: item.id }
    if (name.trim() !== item.name) change.name = name.trim()
    if (portion.trim() !== item.portion_text) change.portion_text = portion.trim()
    const text = grams.trim()
    if (text !== original) {
      const value = Number(text)
      change.grams = text !== '' && Number.isFinite(value) ? value : text
    }
    if (Object.keys(change).length === 2) {
      onClose()
      return
    }
    if (saved.current) return
    const run = flight(() => {
      setPending(true)
      setError(null)
      return onSave(change)
    })
    run?.then(() => {
      saved.current = true
      onClose()
    })
      .catch((caught: unknown) => setError(caught))
      .finally(() => setPending(false))
  }

  return (
    <>
      <TextField label="菜名" value={name} onChange={setName} error={errors.name} maxLength={MAX_NAME_LENGTH} />
      <TextField
        label="份量说法" value={portion} onChange={setPortion} error={errors.portion_text} maxLength={MAX_NAME_LENGTH}
        hint="例如 一碗、半条、一小碟"
      />
      <TextField label="克数" value={grams} onChange={setGrams} error={errors.grams} inputMode="decimal" suffix="克" />
      <FormError messages={otherErrors(errors, ['name', 'portion_text', 'grams'], FIELD_LABELS)} />
      {error instanceof ApiError && errors[FORM_ERROR] && <p className="t-cap">错误码 {error.code}</p>}
      <div className="sheet-foot">
        <Button variant="primary" block isPending={pending} onPress={save}>保存</Button>
        <Button variant="quiet" block onPress={onClose}>取消</Button>
      </div>
    </>
  )
}

/**
 * 修改一个识别项（底部面板）：菜名、份量说法、克数。只发改动的字段；改了菜名后端按新名字重新匹配营养库，
 * 只改克数时沿用原来的食物。后端的字段说明原样写在对应字段下面。
 */
export function ItemEditSheet({ item, isOpen, onClose, onSave }: {
  item: PhotoItemOut | null
  isOpen: boolean
  onClose: () => void
  onSave: (change: EditChange) => Promise<unknown>
}) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} titleKey="editRecognitionItem">
      {item && <EditForm key={item.id} item={item} onClose={onClose} onSave={onSave} />}
    </Sheet>
  )
}
