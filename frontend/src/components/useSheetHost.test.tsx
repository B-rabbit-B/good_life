import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useSheetHost } from './useSheetHost'

describe('sheet host', () => {
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
