// 低端机判定（DESIGN.md 第十二节）：不在启动时测；load 之后再空闲 1.5 秒，只在用户第一次真实滚动时
// 用 requestAnimationFrame 记录滚动期间的帧间隔，凑满 60 帧取中位数，达到 24 毫秒判为低端并保存。

export const LOW_END_RULE_VERSION = 1
export const LOW_END_MEDIAN_MS = 24
export const LOW_END_MIN_FRAMES = 60
export const LOW_END_RETEST_DAYS = 30
export const LOW_END_STORAGE_KEY = 'goodlife.lowEnd'

const IDLE_DELAY_MS = 1500
/** 连续这么多帧没有滚动事件，就当这段滚动结束了（之后的帧不计入） */
const QUIET_FRAMES_TO_STOP = 10
const DAY_MS = 24 * 60 * 60 * 1000

export interface StoredVerdict {
  key: string
  lowEnd: boolean
  /** 判定时间（毫秒时间戳） */
  at: number
}

export function medianInterval(deltas: number[]): number {
  if (deltas.length === 0) return 0
  const sorted = [...deltas].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1 ? (sorted[mid] ?? 0) : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2
}

function browserMajor(userAgent: string): string {
  const rules: [RegExp, string][] = [
    [/(?:Chrome|CriOS)\/(\d+)/, 'chrome'],
    [/(?:Firefox|FxiOS)\/(\d+)/, 'firefox'],
    [/Version\/(\d+)[\d.]*.*Safari\//, 'safari'],
  ]
  for (const [pattern, name] of rules) {
    const match = pattern.exec(userAgent)
    if (match?.[1]) return `${name}-${match[1]}`
  }
  return 'other'
}

/** 结论的版本键：应用版本 + 浏览器主版本 + 判定规则版本，任何一项变了就作废重测。 */
export function verdictKey(appVersion: string, userAgent: string): string {
  return `${appVersion}|${browserMajor(userAgent)}|r${LOW_END_RULE_VERSION}`
}

/** 没有记录、键变了、或判为低端且超过 30 天时需要（重新）测。 */
export function needsProbe(stored: StoredVerdict | null, key: string, now: number): boolean {
  if (!stored || stored.key !== key) return true
  return stored.lowEnd && now - stored.at > LOW_END_RETEST_DAYS * DAY_MS
}

/** 起步时是否按低端处理：有同键的结论就用它；没有时 deviceMemory 不大于 2 GB 先按低端起步（仍需复测）。 */
export function initialLowEnd(stored: StoredVerdict | null, key: string, deviceMemory?: number): boolean {
  if (stored && stored.key === key) return stored.lowEnd
  return deviceMemory !== undefined && deviceMemory <= 2
}

export function readStoredVerdict(): StoredVerdict | null {
  try {
    const raw = window.localStorage.getItem(LOW_END_STORAGE_KEY)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<StoredVerdict>
    if (typeof value.key !== 'string' || typeof value.lowEnd !== 'boolean' || typeof value.at !== 'number') return null
    return { key: value.key, lowEnd: value.lowEnd, at: value.at }
  } catch {
    return null
  }
}

function saveVerdict(verdict: StoredVerdict): void {
  try {
    window.localStorage.setItem(LOW_END_STORAGE_KEY, JSON.stringify(verdict))
  } catch {
    // 存不下（隐私模式等）就下次再测
  }
}

/**
 * 开始探测，返回取消函数。getScroller 给出监听滚动的目标（用捕获阶段监听，滚动容器里的滚动也能收到）。
 * 只有两帧之间确实发生过滚动，这一段帧间隔才计入；滚动停下后循环停止，等下一次滚动。
 */
export function startLowEndProbe({ getScroller, key, onVerdict }: {
  getScroller: () => EventTarget | null
  key: string
  onVerdict: (lowEnd: boolean) => void
}): () => void {
  let cancelled = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let idle: number | undefined
  let frame: number | undefined
  let target: EventTarget | null = null
  const deltas: number[] = []
  let looping = false
  let scrolled = false
  let quiet = 0
  let previous: number | null = null

  const stop = () => {
    cancelled = true
    if (timer !== undefined) clearTimeout(timer)
    if (idle !== undefined && typeof cancelIdleCallback === 'function') cancelIdleCallback(idle)
    if (frame !== undefined) cancelAnimationFrame(frame)
    target?.removeEventListener('scroll', onScroll, true)
    window.removeEventListener('load', afterLoad)
  }

  const tick = (time: number) => {
    frame = undefined
    if (cancelled) return
    if (scrolled) {
      if (previous !== null) deltas.push(time - previous)
      quiet = 0
    } else {
      quiet += 1
    }
    scrolled = false
    previous = time
    if (deltas.length >= LOW_END_MIN_FRAMES) {
      const lowEnd = medianInterval(deltas) >= LOW_END_MEDIAN_MS
      stop()
      saveVerdict({ key, lowEnd, at: Date.now() })
      onVerdict(lowEnd)
      return
    }
    if (quiet >= QUIET_FRAMES_TO_STOP) {
      looping = false
      previous = null
      return
    }
    frame = requestAnimationFrame(tick)
  }

  function onScroll() {
    if (cancelled) return
    scrolled = true
    if (!looping) {
      looping = true
      quiet = 0
      previous = null
      frame = requestAnimationFrame(tick)
    }
  }

  const arm = () => {
    if (cancelled) return
    target = getScroller()
    target?.addEventListener('scroll', onScroll, { capture: true, passive: true })
  }

  function afterLoad() {
    timer = setTimeout(() => {
      if (typeof requestIdleCallback === 'function') idle = requestIdleCallback(arm)
      else arm()
    }, IDLE_DELAY_MS)
  }

  if (document.readyState === 'complete') afterLoad()
  else window.addEventListener('load', afterLoad, { once: true })
  return stop
}
