import type { ReactNode } from 'react'
import { Checkbox as AriaCheckbox } from 'react-aria-components'
import '../styles/components/toggle.css'
import { Icon } from './Icon'

/** 勾选确认：22 方框、圆角 6，选中为钴蓝；整行是标签（React Aria Checkbox）。 */
export function Checkbox({ children, isSelected, onChange, isDisabled }: {
  children: ReactNode
  isSelected: boolean
  onChange: (selected: boolean) => void
  isDisabled?: boolean
}) {
  return (
    <AriaCheckbox className="chk" isSelected={isSelected} onChange={onChange} isDisabled={isDisabled}>
      <span className={isSelected ? 'box on' : 'box'} aria-hidden="true">{isSelected && <Icon name="check" size={18} />}</span>
      <span>{children}</span>
    </AriaCheckbox>
  )
}
