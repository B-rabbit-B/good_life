import { useLayoutEffect, useRef, type ElementType, type HTMLAttributes, type ReactNode } from 'react'
import '../styles/components/sens.css'
import { useCover } from './cover'

const FOCUSABLE = 'a, button, input, textarea, select, [tabindex]'

export type SensitiveProps = {
  as?: ElementType
  /** 直接包住整段消息流时用直角（就医提示是出血到屏幕边的直角块） */
  square?: boolean
  className?: string
  children?: ReactNode
} & Omit<HTMLAttributes<HTMLElement>, 'className' | 'children'>

/**
 * 敏感区：遮盖时盖上不透明斜纹（圆角跟随所在面板），同时设 aria-hidden 与 inert；
 * 浏览器不支持 inert 时，把子树里可聚焦元素的 tabindex 存进 data-ti 后设为 -1，取消遮盖时恢复原值。
 */
export function Sensitive({ as, square = false, className, children, ...rest }: SensitiveProps) {
  const { covered } = useCover()
  const ref = useRef<HTMLElement>(null)
  const Element: ElementType = as ?? 'div'

  useLayoutEffect(() => {
    const el = ref.current
    if (!covered || !el || 'inert' in HTMLElement.prototype) return undefined
    const nodes = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE))
    for (const node of nodes) {
      node.dataset.ti = node.getAttribute('tabindex') ?? ''
      node.setAttribute('tabindex', '-1')
    }
    return () => {
      for (const node of nodes) {
        const original = node.dataset.ti
        if (original) node.setAttribute('tabindex', original)
        else node.removeAttribute('tabindex')
        delete node.dataset.ti
      }
    }
  }, [covered])

  const classes = ['sens', square ? 'sens-sq' : '', className ?? ''].filter(Boolean).join(' ')
  return (
    <Element
      {...rest}
      ref={ref}
      className={classes}
      data-sensitive=""
      data-covered={covered ? '' : undefined}
      aria-hidden={covered ? true : undefined}
      inert={covered}
    >
      {children}
    </Element>
  )
}
