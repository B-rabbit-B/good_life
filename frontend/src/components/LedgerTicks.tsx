import type { CSSProperties } from 'react'
import '../styles/components/ledger.css'

export interface LedgerSegment {
  kcal: number
  tone: 1 | 2 | 3 | 4
}

const SCALE_STEP = 500
// “需要 N”标签大约占刻度宽度的四分之一，离它太近的刻度数字不画
const NEED_LABEL_ROOM = 0.25
const fmt = (n: number) => Math.round(n).toLocaleString('en-US')

/**
 * 能量账本刻度：每格 step 千卡（默认 25），格数 round(max(合计, 需要) / step)；
 * 格中点落在第几段就用那一段的颜色（1 海军蓝、2 钴蓝、3 天青、4 --sky-soft）。
 * 需要线与“需要 N”收在面板内；整块是一张图，读屏读 label 原文。
 */
export function LedgerTicks({ segments, need, step = 25, label }: {
  segments: LedgerSegment[]
  need: number | null
  step?: number
  label: string
}) {
  const total = segments.reduce((sum, s) => sum + s.kcal, 0)
  const count = Math.max(1, Math.round(Math.max(total, need ?? 0) / step))
  const span = count * step
  const ends: { end: number; tone: number }[] = []
  let acc = 0
  for (const s of segments) {
    acc += s.kcal
    ends.push({ end: acc, tone: s.tone })
  }
  const ticks = Array.from({ length: count }, (_, i) => {
    const mid = (i + 0.5) * step
    return ends.find((e) => mid <= e.end)?.tone
  })
  const needAt = need === null ? null : Math.min(1, need / span)
  const scale: number[] = []
  for (let v = 0; v <= span; v += SCALE_STEP) {
    if (needAt === null ? v / span <= 1 - NEED_LABEL_ROOM / 2 : v / span <= needAt - NEED_LABEL_ROOM) scale.push(v)
  }
  const at = (fraction: number): CSSProperties => ({ left: `calc((100% - 3px) * ${fraction} + 3px)` })

  return (
    <div className="lt lt-anim" role="img" aria-label={label}>
      <div className="lt-ticks">
        {ticks.map((tone, i) => (
          <i key={i} className={tone ? `s${tone}` : undefined} style={{ '--i': i } as CSSProperties} />
        ))}
      </div>
      <div className="lt-base" />
      {needAt !== null && <div className="lt-need" style={at(needAt)} />}
      <div className="lt-scale" aria-hidden="true">
        {scale.map((v) => <span key={v} style={{ left: `${(v / span) * 100}%` }}>{v}</span>)}
        {needAt !== null && need !== null && (
          <span className={`need ${needAt > 0.5 ? 'end' : 'start'}`} style={at(needAt)}>需要 {fmt(need)}</span>
        )}
      </div>
    </div>
  )
}
