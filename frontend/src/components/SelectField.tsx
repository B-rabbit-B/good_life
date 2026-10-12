import { useId } from 'react'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

/** 下拉（餐次、活动水平、类型）：原生 select，调起系统选择器，样式是 .sel 圆角框。 */
export function SelectField({ label, value, options, onChange }: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className="fld">
      <label className="fld-l" htmlFor={id}>{label}</label>
      <span className="sel">
        <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <Icon name="down" size={18} />
      </span>
    </div>
  )
}
