import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubAnimationFrames } from '../../test/frames'
import { setMediaMatches } from '../../test/setup'
import { computeGlass, GlassModeProvider, useGlassPreference, useSheetGlass } from './GlassModeProvider'
import { LOW_END_STORAGE_KEY } from './lowEnd'

const REDUCE = '(prefers-reduced-transparency: reduce)'
const PREF_KEY = 'goodlife.reduceTransparency'
const root = document.documentElement

function setDeviceMemory(value: number | undefined) {
  Object.defineProperty(navigator, 'deviceMemory', { value, configurable: true })
}

function PrefSwitcher() {
  const [pref, setPref] = useGlassPreference()
  return (
    <div>
      <span>当前 {pref}</span>
      <button type="button" onClick={() => setPref('on')}>开</button>
      <button type="button" onClick={() => setPref('system')}>跟随系统</button>
    </div>
  )
}

function SheetFlag({ open }: { open: boolean }) {
  useSheetGlass(open)
  return null
}

function setWebdriver(value: boolean) {
  Object.defineProperty(navigator, 'webdriver', { value, configurable: true })
}

/** 渲染外壳、走完“load 之后空闲 1.5 秒”，再在滚动容器上连续滚动 70 帧、每帧 30 毫秒（低端机的帧间隔） */
function scrollSlowly() {
  vi.useFakeTimers()
  const frames = stubAnimationFrames()
  const scroller = document.createElement('div')
  document.body.appendChild(scroller)
  render(<GlassModeProvider><p>内容</p></GlassModeProvider>)
  act(() => {
    vi.advanceTimersByTime(1500)
  })
  act(() => {
    for (let i = 0; i < 70; i += 1) {
      scroller.dispatchEvent(new Event('scroll'))
      frames.frame(30)
    }
  })
  scroller.remove()
}

afterEach(() => {
  setDeviceMemory(undefined)
  setWebdriver(false)
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('glass mode', () => {
  it('turns glass on by default', () => {
    render(<GlassModeProvider><p>内容</p></GlassModeProvider>)
    expect(root).toHaveAttribute('data-glass', 'on')
  })

  it('turns glass off when the system reduces transparency', () => {
    setMediaMatches((query) => query === REDUCE)
    render(<GlassModeProvider><p>内容</p></GlassModeProvider>)
    expect(root).toHaveAttribute('data-glass', 'off')
  })

  it('lets the user setting override the system and the low-end verdict', async () => {
    // 设置为“关”（不减少透明）：系统减少透明、设备内存 1 GB（按低端起步）都不算数
    setMediaMatches((query) => query === REDUCE)
    setDeviceMemory(1)
    window.localStorage.setItem(PREF_KEY, 'off')
    const first = render(<GlassModeProvider><PrefSwitcher /></GlassModeProvider>)
    expect(root).toHaveAttribute('data-glass', 'on')
    first.unmount()

    // 设置为“开”（减少透明）：系统与机器都正常也关
    setMediaMatches(() => false)
    setDeviceMemory(8)
    window.localStorage.setItem(PREF_KEY, 'on')
    render(<GlassModeProvider><PrefSwitcher /></GlassModeProvider>)
    expect(root).toHaveAttribute('data-glass', 'off')

    await userEvent.click(screen.getByRole('button', { name: '跟随系统' }))
    expect(root).toHaveAttribute('data-glass', 'on')
    expect(window.localStorage.getItem(PREF_KEY)).toBe('system')
    await userEvent.click(screen.getByRole('button', { name: '开' }))
    expect(root).toHaveAttribute('data-glass', 'off')
    expect(screen.getByText('当前 on')).toBeInTheDocument()

    expect(computeGlass({ pref: 'system', systemReduce: false, lowEnd: true })).toBe('off')
    expect(computeGlass({ pref: 'off', systemReduce: true, lowEnd: true })).toBe('on')
    expect(computeGlass({ pref: 'on', systemReduce: false, lowEnd: false })).toBe('off')
  })

  it('follows a change of the system preference', () => {
    render(<GlassModeProvider><p>内容</p></GlassModeProvider>)
    expect(root).toHaveAttribute('data-glass', 'on')
    act(() => setMediaMatches((query) => query === REDUCE))
    expect(root).toHaveAttribute('data-glass', 'off')
    act(() => setMediaMatches(() => false))
    expect(root).toHaveAttribute('data-glass', 'on')
  })

  it('turns glass off when real scrolling is slow', () => {
    scrollSlowly()
    expect(root).toHaveAttribute('data-glass', 'off')
    expect(window.localStorage.getItem(LOW_END_STORAGE_KEY)).toContain('"lowEnd":true')
  })

  it('skips the low-end probe under browser automation', () => {
    setWebdriver(true)
    scrollSlowly()
    expect(root).toHaveAttribute('data-glass', 'on')
    expect(window.localStorage.getItem(LOW_END_STORAGE_KEY)).toBeNull()
  })

  it('marks the root while a sheet is open', () => {
    const view = render(<GlassModeProvider><SheetFlag open={false} /></GlassModeProvider>)
    expect(root).not.toHaveAttribute('data-sheet-open')
    view.rerender(<GlassModeProvider><SheetFlag open /></GlassModeProvider>)
    expect(root).toHaveAttribute('data-sheet-open')
    view.rerender(<GlassModeProvider><SheetFlag open={false} /></GlassModeProvider>)
    expect(root).not.toHaveAttribute('data-sheet-open')
    view.unmount()
    expect(root).not.toHaveAttribute('data-glass')
  })
})
