import type { ReactNode } from 'react'
import { Link } from 'react-router'
import '../styles/components/button.css'
import { buttonClassName, type ButtonVariant } from './Button'

/** 与 Button 同样式的路由链接：只导航，不做别的。 */
export function ButtonLink({ to, variant, size, block, children }: {
  to: string
  variant: ButtonVariant
  size?: 'md' | 'sm'
  block?: boolean
  children: ReactNode
}) {
  const small = size === 'sm' && variant !== 'text'
  return (
    <Link to={to} className={buttonClassName({ variant, size, block })} data-hit44={small ? '' : undefined}>
      {children}
    </Link>
  )
}
