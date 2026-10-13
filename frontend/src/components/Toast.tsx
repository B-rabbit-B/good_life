import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import '../styles/components/toast.css'
import { useSheetOpen } from './glass/GlassModeProvider'
import { ShellPortal } from './ShellPortal'
import { Surface } from './Surface'

const SHOW_MS = 3200

interface ToastContextValue {
  show: (text: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

/**
 * 轻提示：一个 aria-live="polite" 区域，提示本身是活玻璃胶囊，渲染进 #shell-root。
 * 它占一层模糊名额，所以与底部面板互斥：面板打开期间不显示。
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<{ text: string; id: number } | null>(null)
  const sheetOpen = useSheetOpen()
  const nextId = useRef(0)

  const show = useCallback((text: string) => {
    nextId.current += 1
    setMessage({ text, id: nextId.current })
  }, [])

  useEffect(() => {
    if (!message) return undefined
    const timer = setTimeout(() => setMessage(null), SHOW_MS)
    return () => clearTimeout(timer)
  }, [message])

  const value = useMemo(() => ({ show }), [show])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <ShellPortal>
        <div className="toast-region" aria-live="polite">
          {message && !sheetOpen && <Surface key={message.id} tier="chrome" className="toast">{message.text}</Surface>}
        </div>
      </ShellPortal>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast 要放在 ToastProvider 里')
  return context
}
