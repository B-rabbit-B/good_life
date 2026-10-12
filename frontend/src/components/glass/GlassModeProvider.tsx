import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, useSyncExternalStore, type ReactNode,
} from 'react'
import { version as APP_VERSION } from '../../../package.json'
import { initialLowEnd, needsProbe, readStoredVerdict, startLowEndProbe, verdictKey } from './lowEnd'

/** “减少透明”设置：跟随系统 / 开（减少透明，玻璃关）/ 关（不减少，玻璃开） */
export type ReduceTransparencyPref = 'system' | 'on' | 'off'

const PREF_KEY = 'goodlife.reduceTransparency'
const REDUCE_TRANSPARENCY = '(prefers-reduced-transparency: reduce)'

/** 用户的设置永远优先于系统偏好与低端机判定。 */
export function computeGlass({ pref, systemReduce, lowEnd }: {
  pref: ReduceTransparencyPref
  systemReduce: boolean
  lowEnd: boolean
}): 'on' | 'off' {
  if (pref === 'on') return 'off'
  if (pref === 'off') return 'on'
  return systemReduce || lowEnd ? 'off' : 'on'
}

function readPref(): ReduceTransparencyPref {
  try {
    const raw = window.localStorage.getItem(PREF_KEY)
    return raw === 'on' || raw === 'off' ? raw : 'system'
  } catch {
    return 'system'
  }
}

function subscribeSystem(onChange: () => void): () => void {
  const list = window.matchMedia(REDUCE_TRANSPARENCY)
  list.addEventListener('change', onChange)
  return () => list.removeEventListener('change', onChange)
}
const readSystem = () => window.matchMedia(REDUCE_TRANSPARENCY).matches

// ---------- 面板打开时根节点带 data-sheet-open（可以同时开多个，按计数） ----------

let openSheets = 0
const sheetListeners = new Set<() => void>()

function changeOpenSheets(delta: number): void {
  openSheets += delta
  document.documentElement.toggleAttribute('data-sheet-open', openSheets > 0)
  for (const listener of sheetListeners) listener()
}

function subscribeSheets(listener: () => void): () => void {
  sheetListeners.add(listener)
  return () => sheetListeners.delete(listener)
}

/** 打开期间让根节点带 data-sheet-open：遮罩下面的外壳关掉模糊，轻提示隐藏。 */
export function useSheetGlass(open: boolean): void {
  useLayoutEffect(() => {
    if (!open) return undefined
    changeOpenSheets(1)
    return () => changeOpenSheets(-1)
  }, [open])
}

/** 当前是否有底部面板打开（轻提示用它与面板互斥）。 */
export function useSheetOpen(): boolean {
  return useSyncExternalStore(subscribeSheets, () => openSheets > 0, () => false)
}

// ---------- 玻璃模式 ----------

interface GlassContextValue {
  pref: ReduceTransparencyPref
  setPref: (pref: ReduceTransparencyPref) => void
}

const GlassContext = createContext<GlassContextValue | null>(null)

const deviceMemory = () => (navigator as Navigator & { deviceMemory?: number }).deviceMemory

/**
 * 在根节点设 data-glass="on|off"。off 的来源：系统 prefers-reduced-transparency、“减少透明”设置、低端机判定；
 * 设置永远优先。系统跟随时才做低端探测（getScroller 默认监听整个文档的滚动，捕获阶段也收得到外壳滚动容器的滚动）；
 * 浏览器自动化下不探测。
 */
export function GlassModeProvider({ children, getScroller = () => document }: {
  children: ReactNode
  getScroller?: () => EventTarget | null
}) {
  const [pref, setPrefState] = useState<ReduceTransparencyPref>(readPref)
  const systemReduce = useSyncExternalStore(subscribeSystem, readSystem, () => false)
  const [key] = useState(() => verdictKey(APP_VERSION, navigator.userAgent))
  const [lowEnd, setLowEnd] = useState(() => initialLowEnd(readStoredVerdict(), key, deviceMemory()))
  const glass = computeGlass({ pref, systemReduce, lowEnd })

  useLayoutEffect(() => {
    document.documentElement.setAttribute('data-glass', glass)
  }, [glass])
  useLayoutEffect(() => () => document.documentElement.removeAttribute('data-glass'), [])

  // 浏览器自动化（Playwright 等，navigator.webdriver 为真）下不探测：测试机的帧时间不代表真实设备，
  // 探测结果还会让同一套测试时而有玻璃、时而没有。真实用户的浏览器里 webdriver 为假，照常探测。
  const probing = pref === 'system' && !systemReduce && !navigator.webdriver
  useEffect(() => {
    if (!probing || !needsProbe(readStoredVerdict(), key, Date.now())) return undefined
    return startLowEndProbe({ getScroller, key, onVerdict: setLowEnd })
    // getScroller 只在开始探测时读一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [probing, key])

  const setPref = useCallback((next: ReduceTransparencyPref) => {
    setPrefState(next)
    try {
      window.localStorage.setItem(PREF_KEY, next)
    } catch {
      // 存不下时只在本次生效
    }
  }, [])
  const value = useMemo(() => ({ pref, setPref }), [pref, setPref])
  return <GlassContext.Provider value={value}>{children}</GlassContext.Provider>
}

/** “隐私与数据”里的“减少透明”：跟随系统 / 开 / 关，存在本地。 */
export function useGlassPreference(): [ReduceTransparencyPref, (pref: ReduceTransparencyPref) => void] {
  const context = useContext(GlassContext)
  if (!context) throw new Error('useGlassPreference 要放在 GlassModeProvider 里')
  return [context.pref, context.setPref]
}
