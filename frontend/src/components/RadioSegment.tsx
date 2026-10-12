import { Label, Radio, RadioGroup } from 'react-aria-components'
import '../styles/components/field-input.css'
import '../styles/components/tabs.css'

/** 分段单选（性别、目标、减少透明）：轨道加瓷白滑块，每段 44 高（React Aria RadioGroup）。 */
export function RadioSegment({ label, options, value, onChange }: {
  label: string
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <RadioGroup className="fld" value={value} onChange={onChange} orientation="horizontal">
      <Label className="fld-l">{label}</Label>
      <div className="opts">
        {options.map((option) => <Radio key={option.value} value={option.value} className="opt">{option.label}</Radio>)}
      </div>
    </RadioGroup>
  )
}
