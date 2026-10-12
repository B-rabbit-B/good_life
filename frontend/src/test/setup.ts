import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './msw/server'

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  cleanup()
  server.resetHandlers()
  if (typeof window !== 'undefined') {
    window.localStorage.clear()
    setMediaMatches(() => false)
  }
})

afterAll(() => {
  server.close()
})

// ---------- jsdom 没有的浏览器接口 ----------

type MediaListener = (event: MediaQueryListEvent) => void

let resolveMatches: (query: string) => boolean = () => false
const mediaLists = new Set<FakeMediaQueryList>()

class FakeMediaQueryList extends EventTarget {
  readonly media: string
  matches: boolean
  onchange: MediaListener | null = null
  private readonly legacy = new Set<MediaListener>()

  constructor(media: string) {
    super()
    this.media = media
    this.matches = resolveMatches(media)
  }

  addListener(listener: MediaListener | null) {
    if (listener) this.legacy.add(listener)
  }

  removeListener(listener: MediaListener | null) {
    if (listener) this.legacy.delete(listener)
  }

  refresh() {
    const next = resolveMatches(this.media)
    if (next === this.matches) return
    this.matches = next
    const event = Object.assign(new Event('change'), { matches: next, media: this.media }) as MediaQueryListEvent
    this.dispatchEvent(event)
    this.onchange?.(event)
    for (const listener of this.legacy) listener(event)
  }
}

/** 测试里改写媒体查询的结果；已经创建的查询会收到 change 事件。每个测试结束后恢复为全部不匹配。 */
export function setMediaMatches(resolve: (query: string) => boolean): void {
  resolveMatches = resolve
  for (const list of mediaLists) list.refresh()
}

class FakeIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = '0px'
  readonly scrollMargin = '0px'
  readonly thresholds: readonly number[] = [0]
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] {
    return []
  }
}

class FakeResizeObserver implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== 'undefined') {
  window.matchMedia = (query: string) => {
    const list = new FakeMediaQueryList(query)
    mediaLists.add(list)
    return list
  }
  window.IntersectionObserver = FakeIntersectionObserver
  window.ResizeObserver = FakeResizeObserver
  window.scrollTo = () => {}
  Element.prototype.scrollTo = () => {}
}
