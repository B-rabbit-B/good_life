// 训练列表（设计稿 08）：每次训练一行，动作名（只有一个动作时是它的名字，否则按种类写“力量训练”“有氧训练”“力量与有氧”）、
// 时长、日期与星期、每个动作的组次与重量（有氧写时长与距离）；与运动限制冲突的说明原文用赭色写在行内（它带医嘱内容，在敏感区里）。
import type { WorkoutOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { formatMonthDay, formatWeekday } from '../../lib/dates'
import { fmtNum } from '../../lib/format'
import '../../styles/components/training.css'
import { workoutMinutes } from './weekBars'

type Block = WorkoutOut['strength'][number]
type Cardio = WorkoutOut['cardio'][number]

const kg = (n: number) => `${fmtNum(n, 1)} 千克`

/** “4×10，12 千克”；每组不一样时逐组写“12 千克×10、14 千克×8” */
function setsText(block: Block): string {
  const [first] = block.sets
  if (!first) return ''
  const uniform = block.sets.every((s) => s.reps === first.reps && s.weight_kg === first.weight_kg)
  if (uniform) return `${block.sets.length}×${first.reps}，${kg(first.weight_kg)}`
  return block.sets.map((s) => `${kg(s.weight_kg)}×${s.reps}`).join('、')
}

const cardioText = (item: Cardio) =>
  `${item.duration_minutes} 分钟${item.distance_km !== null ? `，${fmtNum(item.distance_km, 2)} 千米` : ''}`

function title(workout: WorkoutOut): string {
  const { strength, cardio } = workout
  if (strength.length + cardio.length === 1) return strength[0]?.exercise_name ?? cardio[0]?.exercise_name ?? ''
  if (cardio.length === 0) return '力量训练'
  if (strength.length === 0) return '有氧训练'
  return '力量与有氧'
}

function details(workout: WorkoutOut): string[] {
  const single = workout.strength.length + workout.cardio.length === 1
  const strength = workout.strength.map((block) => (single ? setsText(block) : `${block.exercise_name} ${setsText(block)}`))
  const cardio = workout.cardio
    .map((item) => (single ? (item.distance_km !== null ? `${fmtNum(item.distance_km, 2)} 千米` : '') : `${item.exercise_name} ${cardioText(item)}`))
  return [...strength, ...cardio].filter(Boolean)
}

export function WorkoutRow({ workout }: { workout: WorkoutOut }) {
  const minutes = workoutMinutes(workout)
  return (
    <li className="trw">
      <div className="trw-h">
        <b>{title(workout)}</b>
        {minutes > 0 && <span className="n">{minutes} 分钟</span>}
      </div>
      <div className="trw-d">
        <span>{formatMonthDay(workout.performed_on)} {formatWeekday(workout.performed_on)}</span>
        {details(workout).map((text) => <span key={text}>{text}</span>)}
      </div>
      {workout.conflicts.length > 0 && (
        <Sensitive area="constraints" className="trw-xs">
          {workout.conflicts.map((conflict) => (
            <div key={`${conflict.item_id}-${conflict.subject}`} className="trw-x">
              <Icon name="alert" size={18} />
              <span>{conflict.message}</span>
            </div>
          ))}
        </Sensitive>
      )}
    </li>
  )
}

/** 一段日期里的训练（新的在前），没有时一句说明 */
export function WorkoutRows({ workouts }: { workouts: WorkoutOut[] }) {
  if (workouts.length === 0) return <li className="trn-empty">近 30 天还没有训练记录。</li>
  return <>{workouts.map((workout) => <WorkoutRow key={workout.id} workout={workout} />)}</>
}
