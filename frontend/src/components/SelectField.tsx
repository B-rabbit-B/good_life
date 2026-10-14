import { useId, type ReactNode } from 'react'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

/**
 * 下拉（餐次、活动水平、类型）：原生 select，调起系统选择器，样式是 .sel 圆角框。
 * error 是后端的说明原文：与 TextField 一样朱色写在框下、框描朱色，并用 aria-invalid 与 aria-describedby 关联到下拉框。
 */
export function SelectField({ label, value, options, onChange, isDisabled, error }: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
  isDisabled?: boolean
  error?: ReactNode
}) {
  const id = useId()
  const errorId = useId()
  return (
    <div className="fld">
      <label className="fld-l" htmlFor={id}>{label}</label>
      <span className={error ? 'sel bad' : 'sel'}>
        <select
          id={id} value={value} disabled={isDisabled} onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined} aria-describedby={error ? errorId : undefined}
        >
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <Icon name="down" size={18} />
      </span>
      {error && (
        <div className="err" id={errorId}>
          <Icon name="alert" size={18} />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
