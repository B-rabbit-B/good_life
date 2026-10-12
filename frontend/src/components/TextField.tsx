import type { HTMLAttributes } from 'react'
import { Input, Label, Text, TextArea, TextField as AriaTextField } from 'react-aria-components'
import '../styles/components/field-input.css'
import { Icon } from './Icon'

export interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  /** 后端返回的字段说明，原样显示 */
  error?: string
  type?: 'text' | 'email' | 'tel' | 'url' | 'search' | 'password'
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode']
  autoComplete?: string
  maxLength?: number
  multiline?: boolean
  rows?: number
  isInvalid?: boolean
}

/** 填充式圆角输入框（52 高），聚焦 2 像素钴蓝内描边；多行时是 .area。说明在下，错误用朱色写在框下（React Aria TextField）。 */
export function TextField({ label, value, onChange, hint, error, type = 'text', inputMode, autoComplete, maxLength, multiline = false, rows, isInvalid = false }: TextFieldProps) {
  const invalid = isInvalid || Boolean(error)
  return (
    <AriaTextField
      className="fld" value={value} onChange={onChange} isInvalid={invalid}
      type={type} inputMode={inputMode} autoComplete={autoComplete} maxLength={maxLength}
    >
      <Label className="fld-l">{label}</Label>
      {multiline
        ? <TextArea className={invalid ? 'area bad' : 'area'} rows={rows} />
        : <span className={invalid ? 'fld-i bad' : 'fld-i'}><Input /></span>}
      {hint && <Text slot="description" className="fld-h">{hint}</Text>}
      {error && (
        <Text slot="errorMessage" className="err">
          <Icon name="alert" size={18} />
          <span>{error}</span>
        </Text>
      )}
    </AriaTextField>
  )
}
