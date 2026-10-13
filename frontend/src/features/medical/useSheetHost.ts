import { useCallback, useEffect, useRef, useState } from 'react'

// 面板退场（200 毫秒）之后再看焦点
const FOCUS_CHECK_MS = 400

const lost = (el: Element | null) => el === null || el === document.body || !el.isConnected

/**
 * 一个子标签里的底部面板：同一时间只开一个，面板拿着打开时的条目（确认、作废、解除之后条目会从列表里消失，
 * 面板仍要能播报结果、正常退场）。换成另一个面板时直接换（例如“返回修改”“继续遵守”），不叠两层。
 * nonce 用作面板的 key：每次打开都是新的面板状态（勾选、错误都清空）。
 * 焦点：React Aria 关面板时把焦点还给打开它时的元素；换过面板时那个元素已经不在了，所以记下第一次打开时的触发按钮，
 * 面板关上后焦点落空就回到它；它也随条目消失了（确认、作废、解除之后），就落到当前子标签上。
 * close(nonce) 只关打开时拿到这个 nonce 的那一次面板：迟到的关闭（例如解除结果播报 1.2 秒后）不会关掉用户已经换上的面板。
 */
export function useSheetHost<S>() {
  const [sheet, setSheet] = useState<S | null>(null)
  const [open, setOpen] = useState(false)
  const [nonce, setNonce] = useState(0)
  const current = useRef(0)
  const opened = useRef(false)
  const origin = useRef<HTMLElement | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const show = useCallback((next: S) => {
    if (!opened.current) {
      const active = document.activeElement
      origin.current = active instanceof HTMLElement && !lost(active) ? active : null
    }
    opened.current = true
    current.current += 1
    setSheet(next)
    setNonce(current.current)
    setOpen(true)
  }, [])

  const close = useCallback((forNonce: number) => {
    if (forNonce !== current.current) return
    opened.current = false
    setOpen(false)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      if (!lost(document.activeElement) || opened.current) return
      const target = origin.current && !lost(origin.current)
        ? origin.current
        : document.querySelector<HTMLElement>('.ttabs.sm [aria-selected="true"]')
      target?.focus()
    }, FOCUS_CHECK_MS)
  }, [])

  return { sheet, open, nonce, show, close }
}
