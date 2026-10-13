import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setMediaMatches } from '../test/setup'
import { CountUp } from './CountUp'

const REDUCED = '(prefers-reduced-motion: reduce)'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('CountUp', () => {
  it('shows the final value at once when motion is reduced', () => {
    setMediaMatches((query) => query === REDUCED)
    const view = render(<CountUp value={100} />)
    expect(screen.getByText('100')).toBeInTheDocument()
    view.rerender(<CountUp value={1085} />)
    expect(screen.getByText('1,085')).toBeInTheDocument()
  })

  it('counts to the final value within 600 ms', () => {
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => setTimeout(() => cb(Date.now()), 16))
    vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))
    const view = render(<CountUp value={0} format={(n) => `${Math.round(n)} 千卡`} />)
    expect(screen.getByText('0 千卡')).toBeInTheDocument()
    view.rerender(<CountUp value={600} format={(n) => `${Math.round(n)} 千卡`} />)
    act(() => {
      vi.advanceTimersByTime(200)
    })
    const midway = Number.parseInt(screen.getByText(/千卡/).textContent ?? '', 10)
    expect(midway).toBeGreaterThan(0)
    expect(midway).toBeLessThan(600)
    act(() => {
      vi.advanceTimersByTime(450)
    })
    expect(screen.getByText('600 千卡')).toBeInTheDocument()
  })

  it('does not animate when the number stays the same', () => {
    const raf = vi.fn()
    vi.stubGlobal('requestAnimationFrame', raf)
    const view = render(<CountUp value={765} />)
    view.rerender(<CountUp value={765} />)
    expect(raf).not.toHaveBeenCalled()
    expect(screen.getByText('765')).toBeInTheDocument()
  })
})
