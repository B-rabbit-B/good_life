import { useState } from 'react'
import type { ApiError } from '../../api/errors'
import { useSetAssignment, useUpdateModelOverrides } from '../../api/hooks/llmSettings'
import type { ModelOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Icon } from '../../components/Icon'
import { SelectField } from '../../components/SelectField'
import type { Purpose } from '../../lib/labels'
import { useSingleFlight } from '../../lib/singleFlight'
import { CAPABILITY_LABELS, PURPOSE_LABELS } from '../../lib/settingsLabels'
import { ErrorText } from './StepCredentials'

const SHOWN_CAPS = ['vision', 'tools'] as const
type ShownCap = (typeof SHOWN_CAPS)[number]
const MANUAL: Record<ShownCap, string> = { vision: '能看图（手动标注）', tools: '能调用工具（手动标注）' }
/** 每个用途下面只给它需要的那一项手动标注：对话的助手要调用工具，看图识别要能看图 */
const NEEDS: Record<Purpose, ShownCap> = { chat: 'tools', vision: 'vision' }

/** 能力胶囊：只写支持的能力；手动标注过的写“… 手动”并用虚线框 */
function Caps({ model }: { model: ModelOut }) {
  const shown = SHOWN_CAPS.filter((cap) => model.capabilities[cap] === true)
  if (shown.length === 0) return null
  return (
    <span className="caps">
      {shown.map((cap) => {
        const manual = model.overrides[cap] !== null
        return <span key={cap} className={manual ? 'cap man' : 'cap'}>{CAPABILITY_LABELS[cap]}{manual ? ' 手动' : ''}</span>
      })}
    </span>
  )
}

function PurposeBlock({ purpose, models, value, onChange, error, onOverride, overriding }: {
  purpose: Purpose
  models: ModelOut[]
  value: string
  onChange: (modelId: string) => void
  error: ApiError | undefined
  onOverride: (model: ModelOut, cap: ShownCap, on: boolean) => void
  overriding: boolean
}) {
  const model = models.find((m) => m.model_id === value)
  const label = PURPOSE_LABELS[purpose]
  return (
    <div className="use-g" role="group" aria-label={`${label}用的模型`}>
      <SelectField
        label={label} value={value} onChange={onChange}
        options={[{ value: '', label: '暂不选择' }, ...models.map((m) => ({ value: m.model_id, label: m.model_id }))]}
      />
      {model && <Caps model={model} />}
      {model && (
        <Checkbox
          isSelected={model.overrides[NEEDS[purpose]] === true} isDisabled={overriding}
          onChange={(on) => onOverride(model, NEEDS[purpose], on)}
        >
          {MANUAL[NEEDS[purpose]]}
        </Checkbox>
      )}
      {error && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span><ErrorText message={error.message} code={error.code} /></span>
        </div>
      )}
    </div>
  )
}

/**
 * 第 4 步“选择用途模型”：日常对话与看图识别各选一个本服务的模型（默认对话用测试过的模型、看图用第一个能看图的），
 * 每个下拉下面是能力胶囊与一个手动标注的勾选（对话“能调用工具”、看图“能看图”；取消即回到对照表），后端的提醒原文显示；“保存用途”依次分配对话与看图（未选的不发），
 * 错误原样写在对应的下拉下面；都成功后交给 onDone。
 */
export function StepAssign({ models, tested, onDone }: { models: ModelOut[]; tested: string; onDone: () => void }) {
  const [chat, setChat] = useState(() => (models.some((m) => m.model_id === tested) ? tested : ''))
  const [vision, setVision] = useState(() => models.find((m) => m.capabilities.vision === true)?.model_id ?? '')
  const [errors, setErrors] = useState<Partial<Record<Purpose, ApiError>>>({})
  const [warnings, setWarnings] = useState<string[]>([])
  const [overrideError, setOverrideError] = useState<ApiError | null>(null)
  const [saving, setSaving] = useState(false)
  const overrides = useUpdateModelOverrides()
  const assign = useSetAssignment()
  const saveFlight = useSingleFlight()
  const overrideFlight = useSingleFlight()

  const override = (model: ModelOut, cap: ShownCap, on: boolean) => {
    void overrideFlight(async () => {
      setOverrideError(null)
      try {
        const updated = await overrides.mutateAsync({ pk: model.id, overrides: { [cap]: on ? true : null } })
        setWarnings(updated.assignment_warnings)
      } catch (caught) {
        setOverrideError(caught as ApiError)
      }
    })
  }

  const save = () => saveFlight(async () => {
    setSaving(true)
    const failed: Partial<Record<Purpose, ApiError>> = {}
    for (const [purpose, modelId] of [['chat', chat], ['vision', vision]] as const) {
      const model = models.find((m) => m.model_id === modelId)
      if (!model) continue
      try {
        await assign.mutateAsync({ purpose, modelPk: model.id })
      } catch (caught) {
        failed[purpose] = caught as ApiError
      }
    }
    setErrors(failed)
    setSaving(false)
    if (Object.keys(failed).length === 0) onDone()
  })

  const block = (purpose: Purpose, value: string, onChange: (id: string) => void) => (
    <PurposeBlock
      purpose={purpose} models={models} value={value} onChange={onChange} error={errors[purpose]}
      onOverride={override} overriding={overrides.isPending}
    />
  )
  return (
    <div className="use">
      {block('chat', chat, setChat)}
      {block('vision', vision, setVision)}
      {warnings.map((warning) => <p key={warning} className="use-warn" role="status">{warning}</p>)}
      {overrideError && (
        <div className="err" role="alert">
          <Icon name="alert" size={18} />
          <span><ErrorText message={overrideError.message} code={overrideError.code} /></span>
        </div>
      )}
      <div className="fs-go">
        <Button variant="primary" block isPending={saving} isDisabled={chat === '' && vision === ''} onPress={() => void save()}>
          保存用途
        </Button>
      </div>
    </div>
  )
}
