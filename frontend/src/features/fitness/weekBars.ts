// 本周七根训练柱的数字（只做显示换算）：每天的分钟数是当天各次训练的整次时长之和，某次没填整次时长时取它各项有氧的时长之和。
import type { WorkoutOut } from '../../api/types'
import { addDays } from '../../lib/dates'

const LABELS = ['一', '二', '三', '四', '五', '六', '日'] as const

export interface WeekBar {
  date: string
  label: string
  minutes: number
  isToday: boolean
}

/** 一次训练算多少分钟：整次时长，没填时取各项有氧的时长之和 */
export function workoutMinutes(workout: WorkoutOut): number {
  return workout.duration_minutes ?? workout.cardio.reduce((sum, item) => sum + item.duration_minutes, 0)
}

/** weekStart 是星期一；标签“一”到“日”，今天写“今天” */
export function weekBars(weekStart: string, workouts: readonly WorkoutOut[], today: string): WeekBar[] {
  return LABELS.map((label, i) => {
    const date = addDays(weekStart, i)
    const minutes = workouts.filter((w) => w.performed_on === date).reduce((sum, w) => sum + workoutMinutes(w), 0)
    return { date, label: date === today ? '今天' : label, minutes, isToday: date === today }
  })
}
