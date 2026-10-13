import { Switch as AriaSwitch } from 'react-aria-components'
import '../styles/components/toggle.css'

/** 圆角胶囊开关（50 × 30）：关时 1.5 像素描边，开时钴蓝釉；整行是标签、行高 56（React Aria Switch）。 */
export function Switch({ label, description, isSelected, onChange }: {
  label: string
  description?: string
  isSelected: boolean
  onChange: (selected: boolean) => void
}) {
  return (
    <AriaSwitch className="tg-row" isSelected={isSelected} onChange={onChange}>
      <span>
        {label}
        {description && <small>{description}</small>}
      </span>
      <span className="tg" aria-hidden="true" />
    </AriaSwitch>
  )
}
