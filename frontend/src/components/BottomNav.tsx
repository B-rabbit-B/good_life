import type { CSSProperties } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Link, useLocation } from 'react-router'
import '../styles/components/nav.css'
import { COVER_NAMES, useCover } from './cover'
import { Icon } from './Icon'
import { Surface } from './Surface'

export interface NavItem {
  key: 'chat' | 'records' | 'health' | 'me'
  label: string
  to: string
}

function isCurrent(pathname: string, to: string): boolean {
  if (to === '/') return pathname === '/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

/** 最右 60 宽的遮盖格：在拇指区，是按钮而不是第五个标签 */
function CoverCell() {
  const { covered, toggle } = useCover()
  const names = covered ? COVER_NAMES.on : COVER_NAMES.off
  return (
    <AriaButton className="cov" aria-pressed={covered} aria-label={names.label} onPress={toggle}>
      <Icon name="cover" size={20} />
      <span>{names.text}</span>
    </AriaButton>
  )
}

/**
 * 底部导航：3 或 4 项文字加遮盖格，浮起的活玻璃。当前项 aria-current="page"，画成一汪下陷的“积釉”，
 * 当前项变化时凹槽与短线用 240 毫秒 transform 移过去（减弱动效时直接跳到）。
 * embedded 时放在对话底座里，去掉自身材质。
 */
export function BottomNav({ items, embedded = false }: { items: NavItem[]; embedded?: boolean }) {
  const { pathname } = useLocation()
  const current = items.findIndex((item) => isCurrent(pathname, item.to))
  const style = { '--cols': items.length } as CSSProperties
  const content = (
    <>
      {current >= 0 && <span className="rnav-glaze" aria-hidden="true" style={{ '--at': current } as CSSProperties} />}
      {items.map((item, i) => (
        <Link key={item.key} to={item.to} aria-current={i === current ? 'page' : undefined}>{item.label}</Link>
      ))}
      <CoverCell />
    </>
  )
  if (embedded) {
    return <nav className="rnav embedded" aria-label="主导航" style={style}>{content}</nav>
  }
  return <Surface tier="chrome" as="nav" className="rnav" aria-label="主导航" style={style}>{content}</Surface>
}
