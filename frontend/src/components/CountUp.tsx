import { useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from '../lib/motion'

const DURATION_MS = 600
const easeOutCubic = (p: number) => 1 - (1 - p) ** 3
const defaultFormat = (n: number) => Math.round(n).toLocaleString('en-US')

/**
 * 数字变化时从旧值数到新值：600 毫秒、三次方缓出，按动画帧更新。
 * 第一次显示与数字没变时不动；减弱动效时直接显示终值（偏好变化随时生效）。
 */
export function CountUp({ value, format = defaultFormat }: { value: number; format?: (n: number) => string }) {
  const reduced = usePrefersReducedMotion()
  const [shown, setShown] = useState(value)
  const shownRef = useRef(value)

  useEffect(() => {
    const from = shownRef.current
    if (from === value) return undefined
    // 减弱动效时终值已经直接显示（见下面的 return），这里只在下一帧把内部状态对齐
    const duration = reduced ? 0 : DURATION_MS
    let frame = 0
    let start: number | null = null
    const step = (time: number) => {
      start ??= time
      const progress = duration === 0 ? 1 : Math.min(1, (time - start) / duration)
      const next = progress === 1 ? value : from + (value - from) * easeOutCubic(progress)
      shownRef.current = next
      setShown(next)
      if (progress < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, reduced])

  return <>{format(reduced ? value : shown)}</>
}
