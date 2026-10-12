// 外壳给页面的三个钩子（由 AppShell 提供；不在外壳里时——例如组件样张页与单元测试——都不做任何事）。
import { createContext, useContext, useLayoutEffect, useRef, type RefObject } from 'react'
import type { SensitivePage } from './sensitiveAreas'

export type DockSize = 'short' | 'tall'

export interface ShellContextValue {
  scroller: RefObject<HTMLElement | null>
  setDock: (size: DockSize | null) => void
  setSensitivePage: (page: SensitivePage | null) => void
}

export const ShellContext = createContext<ShellContextValue | null>(null)

/** 唯一的滚动容器 <main data-scroller>；页面用它滚到某处或观察滚动。 */
export function useScroller(): RefObject<HTMLElement | null> {
  const context = useContext(ShellContext)
  const fallback = useRef<HTMLElement | null>(null)
  return context?.scroller ?? fallback
}

/** 页面有底部操作坞期间，滚动容器的底部留白改为 112（short）或 172（tall）；卸载时恢复路由给的值。Dock 组件会自动调用。 */
export function useDockPadding(size: DockSize): void {
  const setDock = useContext(ShellContext)?.setDock
  useLayoutEffect(() => {
    if (!setDock) return undefined
    setDock(size)
    return () => setDock(null)
  }, [setDock, size])
}

/** 页面登记“本页有敏感区”（登记表见 sensitiveAreas.ts）；卸载时撤销。 */
export function useSensitivePage(page: SensitivePage): void {
  const setSensitivePage = useContext(ShellContext)?.setSensitivePage
  useLayoutEffect(() => {
    if (!setSensitivePage) return undefined
    setSensitivePage(page)
    return () => setSensitivePage(null)
  }, [setSensitivePage, page])
}
