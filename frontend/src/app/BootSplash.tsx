import { useEffect } from 'react'
import { Field } from '../components/Field'
import { LoadingState } from '../components/states/LoadingState'
import '../styles/components/app-shell.css'

export const BOOT_SHELL_ID = 'boot-shell'

/** index.html 里的启动外壳（只在对话页画）在页面接管后的下一帧移除。 */
export function useRemoveBootShell(): void {
  useEffect(() => {
    const frame = requestAnimationFrame(() => document.getElementById(BOOT_SHELL_ID)?.remove())
    return () => cancelAnimationFrame(frame)
  }, [])
}

/**
 * 守卫的请求还没回来时显示：启动外壳还在（对话页）就只垫背景场，让外壳继续撑着首屏；
 * 没有启动外壳的路径显示骨架与“正在加载”。
 */
export function BootSplash() {
  const bootShell = typeof document !== 'undefined' && document.getElementById(BOOT_SHELL_ID) !== null
  return (
    <>
      <Field />
      {bootShell ? (
        <p className="sr-only" role="status">正在加载</p>
      ) : (
        <div className="boot-splash">
          <LoadingState variant="page" text="正在加载" />
        </div>
      )}
    </>
  )
}
