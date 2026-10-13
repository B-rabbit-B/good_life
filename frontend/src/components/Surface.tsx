import type { ElementType, HTMLAttributes, ReactNode } from 'react'

export type SurfaceTier = 'plate' | 'still' | 'chrome' | 'sheet'

export type SurfaceProps = {
  tier: SurfaceTier
  as?: ElementType
  className?: string
  children?: ReactNode
} & Omit<HTMLAttributes<HTMLElement>, 'className' | 'children'>

/**
 * 材质原语：只输出 plate、still、chrome、sheet 之一的类名与 data-tier，不做运行时计算。
 * 四种材质的样式与降级规则在 styles/materials.css。
 */
export function Surface({ tier, as, className, children, ...rest }: SurfaceProps) {
  const Element: ElementType = as ?? 'div'
  return (
    <Element {...rest} className={className ? `${tier} ${className}` : tier} data-tier={tier}>
      {children}
    </Element>
  )
}
