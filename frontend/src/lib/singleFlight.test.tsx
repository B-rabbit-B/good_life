import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useSingleFlight } from './singleFlight'

describe('single flight', () => {
  it('skips a second task while the first is running', async () => {
    const { result } = renderHook(() => useSingleFlight())
    let release: () => void = () => {}
    const first = result.current(() => new Promise<string>((resolve) => {
      release = () => resolve('first')
    }))
    expect(result.current(() => Promise.resolve('second'))).toBeNull()
    await Promise.resolve()
    release()
    await expect(first).resolves.toBe('first')
    await expect(result.current(() => Promise.resolve('third'))).resolves.toBe('third')
  })

  it('releases the lock when a task fails so it can be retried', async () => {
    const { result } = renderHook(() => useSingleFlight())
    await expect(result.current(() => Promise.reject(new Error('失败')))).rejects.toThrow('失败')
    await expect(result.current(() => Promise.resolve('重试'))).resolves.toBe('重试')
  })

  it('releases the lock when a task throws synchronously', async () => {
    const { result } = renderHook(() => useSingleFlight())
    const run = result.current((): Promise<string> => {
      throw new Error('同步抛出')
    })
    expect(run).not.toBeNull()
    await expect(run).rejects.toThrow('同步抛出')
    await expect(result.current(() => Promise.resolve('重试'))).resolves.toBe('重试')
  })
})
