import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubAnimationFrames } from '../../test/frames'
import {
  initialLowEnd,
  LOW_END_MEDIAN_MS,
  LOW_END_MIN_FRAMES,
  LOW_END_RETEST_DAYS,
  LOW_END_RULE_VERSION,
  LOW_END_STORAGE_KEY,
  medianInterval,
  needsProbe,
  startLowEndProbe,
  verdictKey,
  type StoredVerdict,
} from './lowEnd'

const DAY = 24 * 60 * 60 * 1000
const CHROME_UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.39 Mobile Safari/537.36'
const SAFARI_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

/** 启动探测并走完“load 之后空闲 1.5 秒”，返回滚动目标、帧驱动与收到的结论 */
function armProbe() {
  vi.useFakeTimers()
  const frames = stubAnimationFrames()
  const scroller = document.createElement('div')
  const verdicts: boolean[] = []
  const stop = startLowEndProbe({ getScroller: () => scroller, key: 'k1', onVerdict: (low) => verdicts.push(low) })
  vi.advanceTimersByTime(1500)
  const scrollFrame = (dt: number) => {
    scroller.dispatchEvent(new Event('scroll'))
    frames.frame(dt)
  }
  return { frames, scrollFrame, verdicts, stop }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('low-end detection', () => {
  it('takes the median frame interval', () => {
    expect(medianInterval([16, 40, 17])).toBe(17)
    expect(medianInterval([10, 40, 20, 30])).toBe(25)
    expect(medianInterval([])).toBe(0)
    expect(LOW_END_MEDIAN_MS).toBe(24)
    expect(LOW_END_MIN_FRAMES).toBe(60)
  })

  it('judges 24 ms or more as low end', () => {
    const slow = armProbe()
    for (let i = 0; i <= LOW_END_MIN_FRAMES; i += 1) slow.scrollFrame(24)
    expect(slow.verdicts).toEqual([true])
    const stored = JSON.parse(window.localStorage.getItem(LOW_END_STORAGE_KEY) ?? 'null') as StoredVerdict
    expect(stored).toMatchObject({ key: 'k1', lowEnd: true })
    slow.stop()
    vi.unstubAllGlobals()
    vi.useRealTimers()

    const fast = armProbe()
    for (let i = 0; i <= LOW_END_MIN_FRAMES; i += 1) fast.scrollFrame(23)
    expect(fast.verdicts).toEqual([false])
    fast.stop()
  })

  it('re-probes when the key changes or a low verdict is older than 30 days', () => {
    const now = 100 * DAY
    const fresh: StoredVerdict = { key: 'k1', lowEnd: false, at: now - DAY }
    expect(needsProbe(null, 'k1', now)).toBe(true)
    expect(needsProbe(fresh, 'k1', now)).toBe(false)
    expect(needsProbe(fresh, 'k2', now)).toBe(true)
    expect(needsProbe({ key: 'k1', lowEnd: true, at: now - (LOW_END_RETEST_DAYS - 1) * DAY }, 'k1', now)).toBe(false)
    expect(needsProbe({ key: 'k1', lowEnd: true, at: now - (LOW_END_RETEST_DAYS + 1) * DAY }, 'k1', now)).toBe(true)
    expect(needsProbe({ key: 'k1', lowEnd: false, at: now - 400 * DAY }, 'k1', now)).toBe(false)

    // 键 = 应用版本 + 浏览器主版本 + 规则版本：任何一项变了都不同
    const key = verdictKey('0.1.0', CHROME_UA)
    expect(key).toBe(`0.1.0|chrome-131|r${LOW_END_RULE_VERSION}`)
    expect(verdictKey('0.1.0', SAFARI_UA)).toBe(`0.1.0|safari-17|r${LOW_END_RULE_VERSION}`)
    expect(verdictKey('0.2.0', CHROME_UA)).not.toBe(key)
    expect(verdictKey('0.1.0', CHROME_UA.replace('Chrome/131', 'Chrome/132'))).not.toBe(key)
  })

  it('starts solid when device memory is 2 gb or less', () => {
    expect(initialLowEnd(null, 'k1', 2)).toBe(true)
    expect(initialLowEnd(null, 'k1', 1)).toBe(true)
    expect(initialLowEnd(null, 'k1', 4)).toBe(false)
    expect(initialLowEnd(null, 'k1', undefined)).toBe(false)
    // 已经量过的结论优先于设备内存；键变了的旧结论不算
    expect(initialLowEnd({ key: 'k1', lowEnd: false, at: 0 }, 'k1', 1)).toBe(false)
    expect(initialLowEnd({ key: 'k1', lowEnd: true, at: 0 }, 'k1', 8)).toBe(true)
    expect(initialLowEnd({ key: 'old', lowEnd: false, at: 0 }, 'k1', 2)).toBe(true)
    // 按低端起步仍要复测
    expect(needsProbe(null, 'k1', Date.now())).toBe(true)
  })

  it('ignores frames outside real scrolling', () => {
    const probe = armProbe()
    // 空闲期过后，没有滚动就不请求任何帧
    expect(probe.frames.pending()).toBe(0)
    // 第一次滚动：30 个快帧
    for (let i = 0; i <= 30; i += 1) probe.scrollFrame(16)
    // 滚动停下：慢帧不计入，循环在连续 10 帧没有滚动后停止
    for (let i = 0; i < 40; i += 1) probe.frames.frame(80)
    expect(probe.frames.pending()).toBe(0)
    expect(probe.verdicts).toEqual([])
    // 再滚动：两段之间的间隔也不计入
    for (let i = 0; i <= 30; i += 1) probe.scrollFrame(16)
    expect(probe.verdicts).toEqual([false])
    probe.stop()
  })
})
