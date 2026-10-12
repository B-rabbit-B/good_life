import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

/** 遮盖按钮（导航里的 CoverCell 与右上角的 CoverButton）共用的读屏名称与文字 */
export const COVER_NAMES = {
  off: { label: '遮盖敏感内容', text: '遮盖' },
  on: { label: '已遮盖，点按恢复显示', text: '已遮盖' },
} as const

const ANNOUNCE = { on: '已遮盖', off: '已恢复显示' } as const

interface CoverContextValue {
  covered: boolean
  toggle: () => void
  setCovered: (covered: boolean) => void
}

const CoverContext = createContext<CoverContextValue | null>(null)

/**
 * 全局遮盖状态：打开时所有 Sensitive 盖上不透明斜纹并对读屏隐藏，切换时向 aria-live 区域播报；
 * 应用切到后台（visibilityState 变为 hidden）时自动遮盖，回来后保持，等用户自己恢复。
 */
export function CoverProvider({ children }: { children: ReactNode }) {
  const [covered, setCoveredState] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const coveredRef = useRef(covered)

  const setCovered = useCallback((next: boolean) => {
    if (coveredRef.current === next) return
    coveredRef.current = next
    setCoveredState(next)
    setAnnouncement(next ? ANNOUNCE.on : ANNOUNCE.off)
  }, [])
  const toggle = useCallback(() => setCovered(!coveredRef.current), [setCovered])

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') setCovered(true)
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [setCovered])

  const value = useMemo(() => ({ covered, toggle, setCovered }), [covered, toggle, setCovered])
  return (
    <CoverContext.Provider value={value}>
      {children}
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
    </CoverContext.Provider>
  )
}

export function useCover(): CoverContextValue {
  const context = useContext(CoverContext)
  if (!context) throw new Error('useCover 要放在 CoverProvider 里')
  return context
}
