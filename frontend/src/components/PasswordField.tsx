import { useState } from 'react'
import { Input, Label, Text, TextField as AriaTextField } from 'react-aria-components'
import '../styles/components/field-input.css'
import { Icon } from './Icon'
import { IconButton } from './IconButton'

/** 密码与密钥输入：与 TextField 同样式，框内右侧一个“显示密码”切换键（按下时显示明文）。 */
export function PasswordField({ label, value, onChange, hint, error, autoComplete, showLabel = '显示密码' }: {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  error?: string
  autoComplete?: string
  /** 切换键的读屏名称，例如“显示密钥” */
  showLabel?: string
}) {
  const [shown, setShown] = useState(false)
  const invalid = Boolean(error)
  return (
    <AriaTextField
      className="fld" value={value} onChange={onChange} isInvalid={invalid}
      type={shown ? 'text' : 'password'} autoComplete={autoComplete}
    >
      <Label className="fld-l">{label}</Label>
      <span className={invalid ? 'fld-i bad' : 'fld-i'}>
        <Input autoCapitalize="off" autoCorrect="off" spellCheck={false} />
        <IconButton icon="eye" label={showLabel} pressed={shown} onPress={() => setShown((s) => !s)} />
      </span>
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
