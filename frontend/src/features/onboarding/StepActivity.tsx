// 建档第 2 步：活动水平五档单选（每档一行：名称加一句说明）与目标四选一（DESIGN.md 第十三节的线框）。“下一步”只提交这两项。
import { useState } from 'react'
import { Label, Radio, RadioGroup } from 'react-aria-components'
import { useUpdateProfile } from '../../api/hooks/profile'
import type { ProfileOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Dock } from '../../components/Dock'
import { RadioSegment } from '../../components/RadioSegment'
import { Title } from '../../components/Title'
import { ACTIVITY_HINTS, ACTIVITY_LABELS, GOAL_LABELS, type ActivityLevel, type Goal } from '../../lib/labels'
import { errorsOf, otherErrors, PROFILE_FIELD_LABELS } from '../../lib/formErrors'
import { FormError } from '../../components/FormError'
import { STEP_TITLE_ID } from './stepTitle'

const LEVELS: ActivityLevel[] = ['sedentary', 'light', 'moderate', 'active', 'very_active']
const GOALS = (Object.keys(GOAL_LABELS) as Goal[]).map((value) => ({ value, label: GOAL_LABELS[value] }))

export function StepActivity({ profile, onSaved }: { profile: ProfileOut; onSaved: () => void }) {
  const update = useUpdateProfile()
  const [activity, setActivity] = useState<string>(profile.activity_level ?? '')
  const [goal, setGoal] = useState<string>(profile.goal ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const next = () => {
    setErrors({})
    update.mutate(
      { activity_level: activity as ActivityLevel, goal: goal as Goal },
      { onSuccess: onSaved, onError: (error) => setErrors(errorsOf(error)) },
    )
  }

  return (
    <>
      <div className="pad">
        <div className="onb-h"><Title k="onbActivity" level="display" as="h1" id={STEP_TITLE_ID} tabIndex={-1} /></div>
      </div>
      <div className="plate">
        <RadioGroup className="acts" value={activity} onChange={setActivity}>
          <Label className="fld-l">活动水平</Label>
          {LEVELS.map((level) => (
            <Radio key={level} value={level} className="act">
              <span className="act-dot" aria-hidden="true" />
              <span className="act-t">
                <span>{ACTIVITY_LABELS[level]}</span>{' '}<small>{ACTIVITY_HINTS[level]}</small>
              </span>
            </Radio>
          ))}
        </RadioGroup>
      </div>
      <div className="plate onb-basics">
        <RadioSegment label="目标" options={GOALS} value={goal} onChange={setGoal} />
        <FormError messages={otherErrors(errors, [], PROFILE_FIELD_LABELS)} />
      </div>
      <Dock>
        <Button variant="primary" block isDisabled={activity === '' || goal === ''} isPending={update.isPending} onPress={next}>
          下一步
        </Button>
      </Dock>
    </>
  )
}
