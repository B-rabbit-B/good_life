import type { ReactNode } from 'react'
import { useDockPadding } from '../app/shellContext'
import '../styles/components/dock.css'
import { ShellPortal } from './ShellPortal'
import { Surface } from './Surface'

/**
 * 底部操作坞：浮起的活玻璃，渲染进 #shell-root；长页面的主按钮放在这里，内容从下面滚过。tall 是带勾选或说明的高坞。
 * 挂载期间外壳的滚动容器底部留白改为 112（tall 时 172），卸载时恢复。
 */
export function Dock({ tall = false, children }: { tall?: boolean; children: ReactNode }) {
  useDockPadding(tall ? 'tall' : 'short')
  return (
    <ShellPortal>
      <Surface tier="chrome" className={tall ? 'stick tall' : 'stick'}>{children}</Surface>
    </ShellPortal>
  )
}
