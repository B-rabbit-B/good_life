// 建档第 3 步（可跳过）：饮食偏好与忌口两组标签、健康状况（DESIGN.md 第十三节的线框）。“完成”提交这三项后进入对话；
// “跳过这一步”不提交任何东西。
import { useRef, useState } from 'react'
import { useUpdateProfile } from '../../api/hooks/profile'
import type { ProfileOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Dock } from '../../components/Dock'
import { TagField } from '../../components/TagField'
import { TextField } from '../../components/TextField'
import { Title } from '../../components/Title'
import { errorsOf, otherErrors, PROFILE_FIELD_LABELS, useFocusFirstInvalid } from '../../lib/formErrors'
import { HEALTH_HINT } from '../../lib/labels'
import { FormError } from '../../components/FormError'
import { STEP_TITLE_ID } from './stepTitle'

const SHOWN = ['diet_preferences', 'food_avoidances', 'health_conditions']

export function StepDiet({ profile, onDone }: { profile: ProfileOut; onDone: () => void }) {
  const update = useUpdateProfile()
  const [prefs, setPrefs] = useState(profile.diet_preferences)
  const [avoid, setAvoid] = useState(profile.food_avoidances)
  const [health, setHealth] = useState(profile.health_conditions ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const formRef = useRef<HTMLDivElement>(null)
  useFocusFirstInvalid(errors, formRef)

  const finish = () => {
    setErrors({})
    update.mutate(
      { diet_preferences: prefs, food_avoidances: avoid, health_conditions: health.trim() === '' ? null : health },
      { onSuccess: onDone, onError: (error) => setErrors(errorsOf(error)) },
    )
  }

  return (
    <>
      <div className="pad">
        <div className="onb-h"><Title k="onbDiet" level="display" as="h1" id={STEP_TITLE_ID} tabIndex={-1} /></div>
      </div>
      <div ref={formRef} className="plate onb-basics">
        <TagField label="饮食偏好" tags={prefs} onChange={setPrefs} error={errors.diet_preferences} />
        <TagField label="忌口" tags={avoid} onChange={setAvoid} error={errors.food_avoidances} />
        <TextField
          label="健康状况" value={health} onChange={setHealth} multiline rows={3}
          hint={HEALTH_HINT} error={errors.health_conditions}
        />
        <FormError messages={otherErrors(errors, SHOWN, PROFILE_FIELD_LABELS)} />
      </div>
      <Dock tall>
        <Button variant="primary" block isPending={update.isPending} onPress={finish}>完成</Button>
        <div className="onb-skip">
          <Button variant="text" ink onPress={onDone}>跳过这一步</Button>
        </div>
      </Dock>
    </>
  )
}
