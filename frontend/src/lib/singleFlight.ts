import { useCallback, useRef } from 'react'

/**
 * 同一时间只跑一个提交：双击或连按时，第二次在第一次结束前直接跳过（返回 null）。
 * 不能只靠按钮的 isPending：它要等下一次渲染才生效，同一帧里的第二次按下照样会发出请求。
 * 任务同步抛错也算失败（经 Promise.resolve().then 调用）：锁照样释放，可以重试。
 */
export function useSingleFlight(): <T>(task: () => Promise<T>) => Promise<T> | null {
  const running = useRef(false)
  return useCallback(<T,>(task: () => Promise<T>): Promise<T> | null => {
    if (running.current) return null
    running.current = true
    return Promise.resolve().then(task).finally(() => {
      running.current = false
    })
  }, [])
}
