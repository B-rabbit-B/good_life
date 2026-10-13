import '../styles/components/status-mark.css'
import { Icon } from './Icon'

export type StatusState = 'todo' | 'current' | 'running' | 'ok' | 'bad'

const STATE_CLASS: Record<StatusState, string> = { todo: '', current: ' cur', running: ' run', ok: ' ok', bad: ' bad' }

/**
 * 步骤号圈：有 index 时是 28 的步骤号（.fs-m），没有时是 22 的进度点（.pm）。
 * running 时是一圈转动的钴蓝弧线（减弱动效时静止，只靠旁边的文字）；完成是钴蓝圆点加勾；失败是朱色圈。
 * 纯图形，对读屏隐藏：步骤的名称与状态由旁边的文字说明。
 */
export function StatusMark({ state, index }: { state: StatusState; index?: number }) {
  const base = index === undefined ? 'pm' : 'fs-m'
  let content = null
  if (state === 'ok') content = <Icon name="check" size={18} />
  else if (state === 'bad' && index === undefined) content = <Icon name="x" size={18} />
  else if (state !== 'running' && index !== undefined) content = index
  return <span className={base + STATE_CLASS[state]} aria-hidden="true">{content}</span>
}
