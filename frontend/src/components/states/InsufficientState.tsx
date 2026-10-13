import { useId, type ReactNode } from 'react'
import type { TitleKey } from '../../lib/titles'
import '../../styles/components/states.css'
import { Title } from '../Title'

const PROGRESS = /^\s*(\d+)\s*\/\s*(\d+)/

/**
 * 数据不足：说明缺什么（后端原文逐条），可选进度文字。进度文字以“已有 / 需要”开头时（例如“1 / 2 个周期”），
 * 上面画一条分段进度条（只是图形，读屏读文字）。
 */
export function InsufficientState({ titleKey, notes, progressText, actions }: {
  titleKey: TitleKey
  notes: string[]
  progressText?: string
  actions?: ReactNode
}) {
  const id = useId()
  const match = progressText ? PROGRESS.exec(progressText) : null
  const have = match ? Number(match[1]) : 0
  const need = match ? Math.min(12, Number(match[2])) : 0
  return (
    <section className="state" aria-labelledby={id}>
      <Title k={titleKey} level="state" id={id} />
      {notes.map((note) => <p key={note} className="st-p">{note}</p>)}
      {need > 0 && (
        <div className="prog" aria-hidden="true">
          {Array.from({ length: need }, (_, i) => <i key={i} className={i < have ? 'on' : undefined} />)}
        </div>
      )}
      {progressText && <p className="t-cap">{progressText}</p>}
      {actions && <div className="st-acts">{actions}</div>}
    </section>
  )
}
