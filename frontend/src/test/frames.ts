import { vi } from 'vitest'

/**
 * requestAnimationFrame 的替身：回调先排队，测试用 frame(dt) 推进一帧并把时间戳交给回调。
 * 结束时调用 vi.unstubAllGlobals() 恢复。
 */
export function stubAnimationFrames(start = 1000) {
  let queue: FrameRequestCallback[] = []
  let now = start
  let nextId = 1
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    queue.push(callback)
    nextId += 1
    return nextId
  })
  vi.stubGlobal('cancelAnimationFrame', () => {
    queue = []
  })
  return {
    /** 推进 dt 毫秒并运行这一帧排队的回调 */
    frame(dt: number) {
      now += dt
      const run = queue
      queue = []
      for (const callback of run) callback(now)
    },
    pending: () => queue.length,
  }
}
