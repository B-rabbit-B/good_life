import { useRef, useState } from 'react'
import { useVoidItem } from '../../api/hooks/medicalPage'
import type { MedicalItemOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { Sheet } from '../../components/Sheet'
import { TextField } from '../../components/TextField'
import { useToast } from '../../components/Toast'
import { WillList } from '../../components/WillList'
import { CATEGORY_LABELS } from '../../lib/labels'
import { ITEM_STATUS_LABELS } from '../../lib/medicalLabels'
import { useSingleFlight } from '../../lib/singleFlight'
import '../../styles/components/medical-item.css'
import '../../styles/components/medical.css'
import { errorsOf, FORM_ERROR } from '../onboarding/fieldErrors'

// app/medical/schemas.py 的 Reason：原因最多 500 个字
const MAX_REASON = 500

function VoidBody({ item, onClose }: { item: MedicalItemOut; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [pending, setPending] = useState(false)
  const flight = useSingleFlight()
  const voidItem = useVoidItem()
  const toast = useToast()
  const done = useRef(false) // 作废成功、面板正在关上时不再提交
  const errors = errorsOf(error)
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : null

  const submit = () => {
    if (done.current) return
    const run = flight(() => {
      setPending(true)
      setError(null)
      // 不填原因时不带请求体
      return voidItem.mutateAsync({ id: item.id, reason: reason.trim() || undefined })
    })
    run?.then(() => {
      done.current = true
      onClose()
      toast.show('已作废，可在“历史与审计”查看')
    })
      .catch((caught: unknown) => setError(caught))
      .finally(() => setPending(false))
  }

  return (
    <>
      <div className="quote">
        <Sensitive area="content">
          <span className="mo-cat">{CATEGORY_LABELS[item.category]}</span>
          <div className="mo-c">{item.content}</div>
        </Sensitive>
      </div>
      <p className="sheet-lead">作废后会发生：</p>
      <WillList items={[
        { text: `这条从“${ITEM_STATUS_LABELS[item.status]}”变为“已作废”，移到“历史与审计”。` },
        { text: '记一条审计：时间、由你本人作废，以及你填写的原因。' },
        { text: '作废不能撤销。以后需要时，请重新录入。', irreversible: true },
      ]}
      />
      <Sensitive area="content">
        <TextField
          label="原因（可不填）" value={reason} onChange={setReason} multiline rows={2} maxLength={MAX_REASON}
          error={errors.reason}
        />
      </Sensitive>
      {errors[FORM_ERROR] && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span>{errors[FORM_ERROR]}{code && <small>错误码 {code}</small>}</span>
        </div>
      )}
      <div className="sheet-foot">
        <Button variant="danger" block isPending={pending} onPress={submit}>作废</Button>
        <Button variant="quiet" block onPress={onClose}>取消</Button>
      </div>
    </>
  )
}

/** 作废（“删除”一律写作“作废”）：条目进入历史并留审计，不是物理删除；原因可不填。 */
export function VoidSheet({ item, isOpen, onClose }: { item: MedicalItemOut; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet isOpen={isOpen} onClose={onClose} titleKey="voidSheet">
      <VoidBody item={item} onClose={onClose} />
    </Sheet>
  )
}
