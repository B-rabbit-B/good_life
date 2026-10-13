// 本周训练（设计稿 08）：标题与“周一 至 周日”的日期；三个数字：次数（后端的 workout_count）、总时长（七根柱的分钟数之和）、
// 估算消耗（后端的区间加“仅供参考”；缺体重时写后端的说明原文）；七根实心钴蓝柱（顶角 2），整组是一张图，读屏读逐日分钟。
import { useId, type CSSProperties } from 'react'
import type { WeekSummaryOut, WorkoutOut } from '../../api/types'
import { CountUp } from '../../components/CountUp'
import { RefTag } from '../../components/RefTag'
import { Title } from '../../components/Title'
import { formatMonthDay } from '../../lib/dates'
import { fmtInt } from '../../lib/format'
import '../../styles/components/training.css'
import { weekBars } from './weekBars'

// 最高的柱占图高的三分之二，上面留出写分钟数的地方
const HEADROOM = 1.5

export function WeekPanel({ summary, workouts, today }: { summary: WeekSummaryOut; workouts: WorkoutOut[]; today: string }) {
  const id = useId()
  const bars = weekBars(summary.week_start, workouts, today)
  const total = bars.reduce((sum, bar) => sum + bar.minutes, 0)
  const top = Math.max(...bars.map((bar) => bar.minutes)) * HEADROOM
  const label = `每日训练分钟：${bars.map((bar) => `${bar.isToday ? '今天' : `周${bar.label}`} ${bar.minutes}`).join('，')}`
  const missing = summary.energy_status === 'missing_body_weight'
  return (
    <section className="plate wk" aria-labelledby={id}>
      <div className="wk-h">
        <Title k="weekTraining" level="h" id={id} />
        <span className="t-cap">{formatMonthDay(summary.week_start)} 至 {formatMonthDay(summary.week_end)}</span>
      </div>
      <div className="wk-figs">
        <div><span className="ns"><CountUp value={summary.workout_count} /><small>次</small></span>训练</div>
        <div><span className="ns"><CountUp value={total} /><small>分钟</small></span>总时长</div>
        {missing
          ? <div><span className="ns">—</span>估算消耗</div>
          : (
            <div>
              <span className="ns rng">
                {fmtInt(summary.energy_low_kcal ?? 0)}–{fmtInt(summary.energy_high_kcal ?? 0)}<small>千卡</small>
              </span>
              估算消耗<RefTag />
            </div>
          )}
      </div>
      {missing && <p className="t-cap wk-note">{summary.note}</p>}
      <div className="wk-cols" role="img" aria-label={label}>
        {bars.map((bar) => (
          <div
            key={bar.date} className={bar.minutes > 0 ? 'wk-col' : 'wk-col zero'}
            style={bar.minutes > 0 ? { '--h': `${(bar.minutes / top) * 100}%` } as CSSProperties : undefined}
          >
            {bar.minutes > 0 && <span className="v">{bar.minutes}</span>}
            <i className="bar" />
          </div>
        ))}
      </div>
      <div className="wk-lbl" aria-hidden="true">
        {bars.map((bar) => <span key={bar.date} className={bar.isToday ? 'on' : undefined}>{bar.label}</span>)}
      </div>
    </section>
  )
}
