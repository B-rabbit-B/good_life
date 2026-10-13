// 修改档案（设计稿 13b）：身高、体重、活动水平、目标、饮食偏好与忌口、健康状况；只提交改过的字段。
// 数字照原样交给后端判断（填的不是数时把原文交上去，后端的说明写在字段下面）；保存成功回到“我的”并轻提示“已保存”。
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useProfile, useUpdateProfile, type ProfilePatch } from '../../api/hooks/profile'
import type { ProfileOut } from '../../api/types'
import { useSensitivePage } from '../../app/AppShell'
import { PATHS } from '../../app/paths'
import { Button } from '../../components/Button'
import { Dock } from '../../components/Dock'
import { PageHeader } from '../../components/PageHeader'
import { RadioSegment } from '../../components/RadioSegment'
import { SelectField } from '../../components/SelectField'
import { Sensitive } from '../../components/Sensitive'
import { LoadingState } from '../../components/states/LoadingState'
import { TagField } from '../../components/TagField'
import { TextField } from '../../components/TextField'
import { useToast } from '../../components/Toast'
import { todayISO } from '../../lib/dates'
import {
  ACTIVITY_HINTS, ACTIVITY_LABELS, GENDER_LABELS, GOAL_LABELS, HEALTH_HINT, type ActivityLevel, type Goal,
} from '../../lib/labels'
import '../../styles/components/me.css'
import { errorsOf, otherErrors, PROFILE_FIELD_LABELS, useFocusFirstInvalid } from '../../lib/formErrors'
import { FormError } from '../../components/FormError'

const LEVELS: ActivityLevel[] = ['sedentary', 'light', 'moderate', 'active', 'very_active']
const ACTIVITY_OPTIONS = LEVELS.map((value) => ({ value, label: `${ACTIVITY_LABELS[value]}：${ACTIVITY_HINTS[value]}` }))
const GOALS = (Object.keys(GOAL_LABELS) as Goal[]).map((value) => ({ value, label: GOAL_LABELS[value] }))
const SHOWN = ['height_cm', 'weight_kg', 'diet_preferences', 'food_avoidances', 'health_conditions']

const numberText = (n: number | null) => (n === null ? '' : String(n))
/**
 * 输入框的文字：能读成数就交数，否则（包括清空）把原文交上去，由后端在字段下说明哪里不对。
 * 不交 null：后端接受 null，档案就缺了这一项，守卫会把人送回建档第 1 步。
 */
const numberValue = (text: string): number | string => {
  const trimmed = text.trim()
  const n = Number(trimmed)
  return trimmed !== '' && Number.isFinite(n) ? n : trimmed
}
const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((item, i) => item === b[i])

function EditForm({ profile }: { profile: ProfileOut }) {
  const update = useUpdateProfile()
  const navigate = useNavigate()
  const toast = useToast()
  const [height, setHeight] = useState(numberText(profile.height_cm))
  const [weight, setWeight] = useState(numberText(profile.weight_kg))
  const [activity, setActivity] = useState<string>(profile.activity_level ?? '')
  const [goal, setGoal] = useState<string>(profile.goal ?? '')
  const [prefs, setPrefs] = useState(profile.diet_preferences)
  const [avoid, setAvoid] = useState(profile.food_avoidances)
  const [health, setHealth] = useState(profile.health_conditions ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const formRef = useRef<HTMLDivElement>(null)
  useFocusFirstInvalid(errors, formRef)

  const changes = (): ProfilePatch => {
    const body: ProfilePatch = {}
    if (height !== numberText(profile.height_cm)) body.height_cm = numberValue(height)
    if (weight !== numberText(profile.weight_kg)) body.weight_kg = numberValue(weight)
    if (activity !== (profile.activity_level ?? '')) body.activity_level = activity as ActivityLevel
    if (goal !== (profile.goal ?? '')) body.goal = goal as Goal
    if (!sameList(prefs, profile.diet_preferences)) body.diet_preferences = prefs
    if (!sameList(avoid, profile.food_avoidances)) body.food_avoidances = avoid
    if (health !== (profile.health_conditions ?? '')) body.health_conditions = health.trim() === '' ? null : health
    return body
  }

  const save = () => {
    setErrors({})
    const body = changes()
    if (Object.keys(body).length === 0) {
      void navigate(PATHS.me)
      return
    }
    update.mutate(body, {
      onSuccess: () => {
        toast.show('已保存')
        void navigate(PATHS.me)
      },
      onError: (error) => setErrors(errorsOf(error)),
    })
  }

  const activityOptions = activity === '' ? [{ value: '', label: '请选择' }, ...ACTIVITY_OPTIONS] : ACTIVITY_OPTIONS
  const gender = profile.gender ? GENDER_LABELS[profile.gender] : '未填'
  return (
    <>
      <div ref={formRef}>
        <Sensitive area="profile" className="plate pe">
          <div className="pe-pair">
            <TextField label="身高" value={height} onChange={setHeight} inputMode="decimal" suffix="厘米" error={errors.height_cm} />
            <TextField label="体重" value={weight} onChange={setWeight} inputMode="decimal" suffix="千克" error={errors.weight_kg} />
          </div>
          <SelectField label="活动水平" value={activity} options={activityOptions} onChange={setActivity} />
          <RadioSegment label="目标" options={GOALS} value={goal} onChange={setGoal} />
          <TagField label="饮食偏好" tags={prefs} onChange={setPrefs} error={errors.diet_preferences} />
          <TagField label="忌口" tags={avoid} onChange={setAvoid} error={errors.food_avoidances} />
          <TextField
            label="健康状况" value={health} onChange={setHealth} multiline rows={2}
            hint={HEALTH_HINT} error={errors.health_conditions}
          />
          <FormError messages={otherErrors(errors, SHOWN, PROFILE_FIELD_LABELS)} />
        </Sensitive>
      </div>
      <p className="t-cap pad pe-foot">
        出生年份 {profile.birth_year ?? '未填'}，性别 {gender}；上次更新 {todayISO(new Date(profile.updated_at))}
      </p>
      <Dock>
        <Button variant="primary" block isPending={update.isPending} onPress={save}>保存</Button>
      </Dock>
    </>
  )
}

export default function ProfileEditPage() {
  useSensitivePage('profileEdit')
  const profile = useProfile()
  return (
    <>
      <PageHeader titleKey="profile" variant="sub" back={PATHS.me} />
      {profile.data ? <EditForm profile={profile.data} /> : <LoadingState variant="list" text="正在读取档案" />}
    </>
  )
}
