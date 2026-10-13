// 动作趋势（设计稿 08）：最近一次训练里的第一个力量动作，最近几次的最大重量画成阶梯线加圆点，最近一次是实心钴蓝；
// 旁边写“最大重量，近 N 次”与“X 到 Y 千克”。数字都来自后端的趋势接口，这里只取最后几次画出来。
import { useExerciseTrend } from '../../api/hooks/fitness'
import type { WorkoutOut } from '../../api/types'
import { fmtNum } from '../../lib/format'
import '../../styles/components/training.css'

// 图里最多画最近 6 次；横向 2 到 112 均分，阶梯线延到 130，纵向重量从低到高画在 36 到 14
const MAX_POINTS = 6
const X0 = 2
const X1 = 112
const X_END = 130
const Y_LOW = 36
const Y_HIGH = 14

export function TrendRow({ workouts }: { workouts: WorkoutOut[] }) {
  const id = workouts.find((w) => w.strength.length > 0)?.strength[0]?.exercise_id ?? null
  const trend = useExerciseTrend(id)
  const points = (trend.data?.points ?? []).slice(-MAX_POINTS)
  if (!trend.data || points.length === 0) return null

  const weights = points.map((p) => p.max_weight_kg)
  const low = Math.min(...weights)
  const high = Math.max(...weights)
  const x = (i: number) => (points.length === 1 ? X1 : X0 + (i * (X1 - X0)) / (points.length - 1))
  const y = (w: number) => (high === low ? (Y_LOW + Y_HIGH) / 2 : Y_LOW - ((w - low) / (high - low)) * (Y_LOW - Y_HIGH))
  const path = points.reduce((d, p, i) => (i === 0 ? `M${x(0)} ${y(p.max_weight_kg)}` : `${d} H${x(i)} V${y(p.max_weight_kg)}`), '')
    + ` H${X_END}`
  const range = low === high ? `${fmtNum(low, 1)} 千克` : `${fmtNum(low, 1)} 到 ${fmtNum(high, 1)} 千克`

  return (
    <li className="trend">
      <div>
        <b>{trend.data.exercise_name}</b>
        <div className="t-cap">最大重量，近 {points.length} 次</div>
        <div className="t-cap">{range}</div>
      </div>
      <svg viewBox="0 0 132 44" aria-hidden="true">
        <path d={path} />
        {points.map((p, i) => (
          <circle
            key={p.day} cx={x(i)} cy={y(p.max_weight_kg)} r={i === points.length - 1 ? 3.5 : 2.5}
            className={i === points.length - 1 ? 'last' : undefined}
          />
        ))}
      </svg>
    </li>
  )
}
