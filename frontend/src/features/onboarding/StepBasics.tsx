// 建档第 1 步：出生年份、性别、身高、体重（设计稿 02）。“下一步”只提交这四项。
import { useState } from 'react'
import { useUpdateProfile } from '../../api/hooks/profile'
import type { ProfileOut } from '../../api/types'
import { Button } from '../../components/Button'
import { Dock } from '../../components/Dock'
import { RadioSegment } from '../../components/RadioSegment'
import { Ruler } from '../../components/Ruler'
import { SelectField } from '../../components/SelectField'
import { Title } from '../../components/Title'
import { GENDER_LABELS, type Gender } from '../../lib/labels'
import { errorsOf, otherErrors, PROFILE_FIELD_LABELS } from '../../lib/formErrors'
import { FormError } from '../../components/FormError'
import { STEP_TITLE_ID } from './stepTitle'

const YEARS = 100
const DEFAULT_HEIGHT = 165
const DEFAULT_WEIGHT = 60
const GENDERS = (Object.keys(GENDER_LABELS) as Gender[]).map((value) => ({ value, label: GENDER_LABELS[value] }))

/** 近 100 年（今年在前）；档案里已有更早的年份时也列上 */
function yearOptions(current: number | null): { value: string; label: string }[] {
  const thisYear = new Date().getFullYear()
  const years = Array.from({ length: YEARS }, (_, i) => thisYear - i)
  if (current !== null && !years.includes(current)) years.push(current)
  return years.map((year) => ({ value: String(year), label: String(year) }))
}

export function StepBasics({ profile, onSaved }: { profile: ProfileOut; onSaved: () => void }) {
  const update = useUpdateProfile()
  const [birthYear, setBirthYear] = useState(profile.birth_year === null ? '' : String(profile.birth_year))
  const [gender, setGender] = useState<string>(profile.gender ?? '')
  const [height, setHeight] = useState(profile.height_cm ?? DEFAULT_HEIGHT)
  const [weight, setWeight] = useState(profile.weight_kg ?? DEFAULT_WEIGHT)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const years = yearOptions(profile.birth_year)
  const options = birthYear === '' ? [{ value: '', label: '请选择' }, ...years] : years

  const next = () => {
    setErrors({})
    update.mutate(
      { birth_year: Number(birthYear), gender: gender as Gender, height_cm: height, weight_kg: weight },
      { onSuccess: onSaved, onError: (error) => setErrors(errorsOf(error)) },
    )
  }

  return (
    <>
      <div className="pad">
        <div className="onb-h"><Title k="onbBasics" level="display" as="h1" id={STEP_TITLE_ID} tabIndex={-1} /></div>
        <p className="t-small ink2 onb-intro">用来估算每天需要多少能量与营养。之后可以在“我的”里修改。</p>
      </div>
      <div className="plate onb-basics">
        <div className="onb-year">
          <SelectField label="出生年份" value={birthYear} options={options} onChange={setBirthYear} />
        </div>
        <RadioSegment
          label="性别" options={GENDERS} value={gender} onChange={setGender}
          hint="用于估算能量需要，也决定是否显示经期记录。"
        />
      </div>
      <div className="plate onb-rulers">
        <Ruler label="身高" unit="厘米" value={height} onChange={setHeight} min={50} max={250} step={1} major={10} ppu={8} />
        <Ruler
          label="体重" unit="千克" value={weight} onChange={setWeight} min={20} max={300} step={0.5} major={5} ppu={16}
          hint="左右拖动刻度，或点数字直接输入。"
        />
        <FormError messages={otherErrors(errors, [], PROFILE_FIELD_LABELS)} />
      </div>
      <Dock>
        <Button variant="primary" block isDisabled={birthYear === '' || gender === ''} isPending={update.isPending} onPress={next}>
          下一步
        </Button>
      </Dock>
    </>
  )
}
