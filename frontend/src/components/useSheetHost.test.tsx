import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSheetHost } from './useSheetHost'

afterEach(() => {
  vi.useRealTimers()
  document.body.innerHTML = ''
})

describe('sheet host', () => {
  it('returns focus to the trigger when it is still usable and skips an inert trigger', () => {
    vi.useFakeTimers()
    document.body.innerHTML =
      '<div id="area"><button id="origin">打开</button></div><button id="fallback">备用</button>'
    const origin = document.getElementById('origin') as HTMLElement
    const fallback = document.getElementById('fallback') as HTMLElement
    const { result } = renderHook(() => useSheetHost<string>(() => fallback))
    for (const inert of [false, true]) {
      origin.focus()
      act(() => result.current.show('resolve'))
      if (inert) document.getElementById('area')?.setAttribute('inert', '')
      ;(document.activeElement as HTMLElement | null)?.blur()
      act(() => result.current.close(result.current.nonce))
      act(() => {
        vi.advanceTimersByTime(500)
      })
      expect(document.activeElement, inert ? 'inert trigger' : 'usable trigger').toBe(inert ? fallback : origin)
      fallback.blur()
    }
  })

  it('ignores a late close from a sheet that was already swapped out', () => {
    const { result } = renderHook(() => useSheetHost<string>())
    act(() => result.current.show('resolve'))
    const resolveNonce = result.current.nonce
    act(() => result.current.show('continue'))
    expect(result.current.sheet).toBe('continue')
    // 解除面板 1.2 秒后迟到的关闭：不关掉已经换上的继续遵守面板
    act(() => result.current.close(resolveNonce))
    expect(result.current.open).toBe(true)
    act(() => result.current.close(result.current.nonce))
    expect(result.current.open).toBe(false)
  })
})
