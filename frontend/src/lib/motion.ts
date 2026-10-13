import { useSyncExternalStore } from 'react'

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

function subscribe(onChange: () => void): () => void {
  const list = window.matchMedia(REDUCED_MOTION)
  list.addEventListener('change', onChange)
  return () => list.removeEventListener('change', onChange)
}

const read = () => window.matchMedia(REDUCED_MOTION).matches

/** 系统是否开启“减弱动态效果”；偏好变化时组件随之重绘。脚本驱动的计数与流式在开始前读它。 */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, read, () => false)
}
