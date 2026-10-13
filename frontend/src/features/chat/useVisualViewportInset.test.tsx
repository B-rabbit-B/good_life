import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useVisualViewportInset } from './useVisualViewportInset'

class FakeViewport extends EventTarget {
  height = 844
  offsetTop = 0
  scale = 1
}

function stubViewport(): FakeViewport {
  const viewport = new FakeViewport()
  Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true })
  Object.defineProperty(window, 'innerHeight', { value: 844, configurable: true })
  return viewport
}

const root = document.documentElement

afterEach(() => {
  Object.defineProperty(window, 'visualViewport', { value: null, configurable: true })
})

describe('visual viewport inset', () => {
  it('lifts the dock over the keyboard and clears it again', () => {
    const viewport = stubViewport()
    const { unmount } = renderHook(() => useVisualViewportInset())
    expect(root.hasAttribute('data-kb')).toBe(false)
    act(() => {
      viewport.height = 500
      viewport.dispatchEvent(new Event('resize'))
    })
    expect(root.hasAttribute('data-kb')).toBe(true)
    expect(root.style.getPropertyValue('--kb')).toBe('344px')
    act(() => {
      viewport.height = 844
      viewport.dispatchEvent(new Event('resize'))
    })
    expect(root.hasAttribute('data-kb')).toBe(false)
    unmount()
  })

  it('ignores pinch zoom', () => {
    const viewport = stubViewport()
    const { unmount } = renderHook(() => useVisualViewportInset())
    act(() => {
      viewport.scale = 2
      viewport.height = 422
      viewport.dispatchEvent(new Event('resize'))
    })
    expect(root.hasAttribute('data-kb')).toBe(false)
    expect(root.style.getPropertyValue('--kb')).toBe('')
    unmount()
  })
})
