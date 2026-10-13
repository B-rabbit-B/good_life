import type { ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import '../styles/components/button.css'
import { Icon, type IconName } from './Icon'

export type ButtonVariant = 'primary' | 'quiet' | 'text' | 'danger' | 'danger-outline'

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'btn btn-pri',
  quiet: 'btn btn-qt',
  text: 'btn-txt',
  danger: 'btn btn-dng',
  'danger-outline': 'btn btn-dng-qt',
}

export interface ButtonStyleOptions {
  variant: ButtonVariant
  size?: 'md' | 'sm'
  block?: boolean
  ink?: boolean
  onField?: boolean
}

/** 按钮与按钮式链接共用的类名：变体、小号（btn-sm）、通栏、海军蓝文字、背景场上的白底。 */
export function buttonClassName({ variant, size = 'md', block = false, ink = false, onField = false }: ButtonStyleOptions): string {
  const classes = [VARIANT_CLASS[variant]]
  if (size === 'sm' && variant !== 'text') classes.push('btn-sm')
  if (block) classes.push('btn-blk')
  if (ink) classes.push('ink')
  if (onField) classes.push('on-field')
  return classes.join(' ')
}

export interface ButtonProps extends ButtonStyleOptions {
  icon?: IconName
  isDisabled?: boolean
  /** 动作进行中：不可重复点，焦点留在按钮上 */
  isPending?: boolean
  onPress: () => void
  type?: 'button' | 'submit'
  children: ReactNode
}

/** 瓷釉按钮：高 48、圆角 16；小号 36、圆角 10，点按区补到 44（data-hit44）。行为来自 React Aria Button。 */
export function Button({ variant, size, block, ink, onField, icon, isDisabled, isPending, onPress, type = 'button', children }: ButtonProps) {
  const small = size === 'sm' && variant !== 'text'
  return (
    <AriaButton
      type={type}
      className={buttonClassName({ variant, size, block, ink, onField })}
      isDisabled={isDisabled}
      isPending={isPending}
      onPress={onPress}
      data-hit44={small ? '' : undefined}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </AriaButton>
  )
}
