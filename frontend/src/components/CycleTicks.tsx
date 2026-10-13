import '../styles/components/cycle-ticks.css'

/**
 * 周期刻度：一行压缩整个周期。每天一根刻度；经期的几天是加粗的海军蓝，预计开始范围是虚线，今天是一根钴蓝针。
 * 刻度数取周期长度与“预计范围末尾 + 2”中的较大者，让预计范围不贴着右边。整块是一张图，读屏读 label 原文。
 */
export function CycleTicks({ length, periodDays, predicted, today, label }: {
  length: number
  periodDays: number
  predicted: [number, number] | null
  today: number | null
  label: string
}) {
  const count = Math.max(length, predicted ? predicted[1] + 2 : 0, today ?? 0)
  const days = Array.from({ length: count }, (_, i) => i + 1)
  const kind = (day: number) => {
    if (day <= periodDays) return 'm'
    if (predicted && day >= predicted[0] && day <= predicted[1]) return 'p'
    return undefined
  }
  const at = (day: number) => (count > 1 ? (day - 1) / (count - 1) : 0)
  return (
    <div className="cyc" role="img" aria-label={label}>
      <div className="cyc-t">
        {days.map((day) => <i key={day} className={kind(day)} />)}
      </div>
      {today !== null && (
        <div className={`cyc-now${at(today) > 0.75 ? ' end' : ''}`} style={{ left: `calc((100% - 3px) * ${at(today)})` }}>
          <span>今天</span>
        </div>
      )}
      <div className="cyc-l">
        <span>第 1 天</span>
        {today !== null && <span>第 {today} 天</span>}
        <span>{predicted ? '预计下次' : `第 ${count} 天`}</span>
      </div>
    </div>
  )
}
