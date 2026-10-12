// 应用外壳：背景场、唯一的滚动容器 <main data-scroller>、页面（Outlet），以及按路由的 handle 决定的底部导航。
// 浮起的导航、对话底座与操作坞不占文档流，滚动容器的底部留白由这里直接给（导航 104、对话底座 196、
// 操作坞 112 或 172、都没有 28），保证最后一行能滚出来。
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Outlet, useMatches, useNavigate } from 'react-router'
import { onUnauthorized } from '../api/client'
import { useCapabilities } from '../api/hooks/profile'
import { BottomNav } from '../components/BottomNav'
import { Field } from '../components/Field'
import { ShellPortal } from '../components/ShellPortal'
import '../styles/components/app-shell.css'
import { useRemoveBootShell } from './BootSplash'
import type { LoginState } from './guards'
import { navItems } from './nav'
import { PATHS } from './paths'
import type { RouteHandle } from './routes'
import type { SensitivePage } from './sensitiveAreas'
import { ShellContext, type DockSize, type ShellContextValue } from './shellContext'

export { useDockPadding, useHeaderCover, useScroller, useSensitivePage } from './shellContext'

const PADDING = { tabs: 104, chat: 196, none: 28 } as const
const DOCK_PADDING: Record<DockSize, number> = { short: 112, tall: 172 }
const NO_HANDLE: RouteHandle = { nav: 'none', sensitive: false }

/** 最深一层带 handle 的路由的 handle */
function useRouteHandle(): RouteHandle {
  const matches = useMatches()
  for (let i = matches.length - 1; i >= 0; i -= 1) {
    const handle = matches[i]?.handle as RouteHandle | undefined
    if (handle) return handle
  }
  return NO_HANDLE
}

/** 底部导航：入口按能力清单（守卫已经取好）；渲染进 #shell-root，不在任何 overflow:hidden 的容器里 */
function ShellNav() {
  const caps = useCapabilities()
  if (!caps.data) return null
  return (
    <ShellPortal>
      <BottomNav items={navItems(caps.data)} />
    </ShellPortal>
  )
}

export function AppShell() {
  const handle = useRouteHandle()
  const scroller = useRef<HTMLElement>(null)
  const [dock, setDockState] = useState<DockSize | null>(null)
  const [sensitivePage, setSensitivePageState] = useState<SensitivePage | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  useRemoveBootShell()

  // 登录失效：取消进行中的查询，回登录页并显示“登录已过期”，页面卸载之后再清缓存
  // （先清缓存的话，还挂着的查询会不带令牌重新请求，又触发一次 401）
  useEffect(() => onUnauthorized(() => {
    void (async () => {
      await queryClient.cancelQueries()
      await navigate(PATHS.login, { replace: true, state: { expired: true } satisfies LoginState })
      queryClient.clear()
    })()
  }), [queryClient, navigate])

  const setDock = useCallback((size: DockSize | null) => setDockState(size), [])
  const setSensitivePage = useCallback((page: SensitivePage | null) => setSensitivePageState(page), [])
  const headerCover = handle.sensitive && handle.nav === 'none'
  const context = useMemo<ShellContextValue>(
    () => ({ scroller, setDock, setSensitivePage, headerCover }),
    [setDock, setSensitivePage, headerCover],
  )

  const paddingBottom = dock ? DOCK_PADDING[dock] : PADDING[handle.nav]
  return (
    <ShellContext.Provider value={context}>
      <Field />
      <main
        ref={scroller}
        className="scroller"
        data-scroller=""
        data-sensitive-page={sensitivePage ?? undefined}
        style={{ paddingBottom }}
      >
        <Outlet />
      </main>
      {handle.nav === 'tabs' && <ShellNav />}
    </ShellContext.Provider>
  )
}
