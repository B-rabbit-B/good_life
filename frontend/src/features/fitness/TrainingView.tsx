// 训练（设计稿 08，记录页的“训练”段）：顶部的运动限制（医嘱内容，在敏感区里）、本周训练面板、“搜索动作”胶囊
// （点按进入记一次训练）、动作趋势与近 30 天的训练列表。页头右上的“记一次训练”在记录页的页头里。
import { Link } from 'react-router'
import { networkError } from '../../api/client'
import { ApiError } from '../../api/errors'
import { useWeekSummary, useWorkouts } from '../../api/hooks/fitness'
import { PATHS } from '../../app/paths'
import { Icon } from '../../components/Icon'
import { ErrorState } from '../../components/states/ErrorState'
import { LoadingState } from '../../components/states/LoadingState'
import { addDays, mondayOf, todayISO } from '../../lib/dates'
import '../../styles/components/training.css'
import { LimitStrip } from './LimitStrip'
import { TrendRow } from './TrendRow'
import { WeekPanel } from './WeekPanel'
import { WorkoutRows } from './WorkoutRows'

// 训练列表的时间窗：近 30 天（含今天）
const RECENT_DAYS = 30

export function TrainingView() {
  const today = todayISO()
  const summary = useWeekSummary()
  const weekStart = summary.data?.week_start ?? mondayOf(today)
  const week = useWorkouts(weekStart, addDays(weekStart, 6))
  const recent = useWorkouts(addDays(today, 1 - RECENT_DAYS), today)
  const queries = [summary, week, recent]

  let body
  if (summary.data && week.data && recent.data) {
    body = (
      <>
        <WeekPanel summary={summary.data} workouts={week.data} today={today} />
        <Link className="srch" to={PATHS.workoutNew}>
          <Icon name="search" size={18} />
          搜索动作，比如 深蹲、卧推
        </Link>
        <section className="plate" aria-label="近 30 天的训练">
          <ul className="trn">
            <TrendRow workouts={recent.data} />
            <WorkoutRows workouts={recent.data} />
          </ul>
        </section>
      </>
    )
  } else if (queries.some((q) => q.isError && !q.data)) {
    const failed = queries.find((q) => q.isError)?.error
    body = (
      <div className="plate">
        <ErrorState
          error={failed instanceof ApiError ? failed : networkError()}
          onRetry={() => queries.forEach((q) => void q.refetch())}
        />
      </div>
    )
  } else {
    body = <LoadingState variant="list" text="正在读取训练记录" />
  }

  return (
    <>
      <LimitStrip />
      {body}
    </>
  )
}
