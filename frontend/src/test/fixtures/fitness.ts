// 训练的测试数据（设计稿 08 的样子）：力量训练（哑铃卧推、腿屈伸）、快走、动感单车与带冲突说明的开合跳；
// 说明原文照抄后端（app/fitness/calc.py、router.py、conflicts.py）。
import type {
  ConflictOut, ExerciseSearchOut, ExerciseSummaryOut, ExerciseTrendOut, WeekSummaryOut, WorkoutOut,
} from '../../api/types'
import { addDays, mondayOf, todayISO } from '../../lib/dates'

export const ESTIMATE_NOTE = '能量消耗仅为估算：按代谢当量粗略计算，个体差异很大，给出的是大致区间。'
export const MISSING_WEIGHT_NOTE = '还不能估算能量消耗：请先在档案里填写体重。能量消耗仅为估算，需要体重才能计算。'
export const PARTIAL_MATCH_MESSAGE = '没有完全一致的动作，下面是名称相近的候选，请确认是否是你要找的'
export const KNEE_LIMIT = '膝关节术后六周内避免跑跳'
export const KNEE_CONFLICT_MESSAGE = `与运动限制冲突：${KNEE_LIMIT}`

let seq = 0
const uuid = () => {
  seq += 1
  return `60000000-0000-4000-8000-${String(seq).padStart(12, '0')}`
}

const base = (date: string): Omit<WorkoutOut, 'strength' | 'cardio' | 'duration_minutes'> => ({
  id: uuid(), performed_on: date, rpe: null, note: null, conflicts: [],
  created_at: `${date}T10:00:00Z`, updated_at: `${date}T10:00:00Z`,
})

/** 力量训练：哑铃卧推 4 组 × 10 次 12 千克，腿屈伸 3 组 × 12 次 25 千克，50 分钟 */
export function strengthWorkout(date: string, overrides: Partial<WorkoutOut> = {}): WorkoutOut {
  const sets = (n: number, weight: number, reps: number) =>
    Array.from({ length: n }, (_, i) => ({ set_index: i + 1, weight_kg: weight, reps, rest_seconds: null, rpe: null }))
  return {
    ...base(date),
    duration_minutes: 50,
    strength: [
      { exercise_id: 'ex:dumbbell_bench_press', exercise_name: '哑铃卧推', position: 1, sets: sets(4, 12, 10) },
      { exercise_id: 'ex:leg_extension', exercise_name: '腿屈伸', position: 2, sets: sets(3, 25, 12) },
    ],
    cardio: [],
    ...overrides,
  }
}

/** 只有一项有氧的训练；duration 为 null 时整次时长没填（按有氧时长算） */
export function cardioWorkout(
  date: string, id: string, name: string, minutes: number, overrides: Partial<WorkoutOut> = {},
): WorkoutOut {
  return {
    ...base(date),
    duration_minutes: null,
    strength: [],
    cardio: [{ exercise_id: id, exercise_name: name, position: 1, duration_minutes: minutes, distance_km: null, rpe: null }],
    ...overrides,
  }
}

export const kneeConflict = (workoutIds: string[]): ConflictOut => ({
  item_id: '20000000-0000-4000-8000-000000000009', content: KNEE_LIMIT, subject: '跳', level: 'conflict',
  message: KNEE_CONFLICT_MESSAGE, workout_ids: workoutIds,
})

/** 近 30 天的四次训练（新的在前）：今天快走、昨天力量、前天动感单车、5 天前开合跳（与运动限制冲突） */
export function recentWorkouts(today = todayISO()): WorkoutOut[] {
  const jump = cardioWorkout(addDays(today, -5), 'ex:jumping_jacks', '开合跳', 15)
  return [
    cardioWorkout(today, 'ex:brisk_walking', '快走', 35),
    strengthWorkout(addDays(today, -1)),
    cardioWorkout(addDays(today, -2), 'ex:spinning', '动感单车', 38, { duration_minutes: 40 }),
    { ...jump, conflicts: [kneeConflict([jump.id])] },
  ]
}

export function weekSummary(today = todayISO(), overrides: Partial<WeekSummaryOut> = {}): WeekSummaryOut {
  const start = mondayOf(today)
  return {
    week_start: start,
    week_end: addDays(start, 6),
    workout_count: 4,
    training_days: 4,
    total_volume: 2380,
    muscle_volumes: { chest: 480, quads: 900 },
    cardio_minutes: 88,
    energy_low_kcal: 820,
    energy_high_kcal: 1020,
    energy_status: 'ok',
    note: ESTIMATE_NOTE,
    ...overrides,
  }
}

export function missingWeightSummary(today = todayISO()): WeekSummaryOut {
  return weekSummary(today, {
    energy_low_kcal: null, energy_high_kcal: null, energy_status: 'missing_body_weight', note: MISSING_WEIGHT_NOTE,
  })
}

export function exercise(overrides: Partial<ExerciseSummaryOut> & Pick<ExerciseSummaryOut, 'id' | 'name'>): ExerciseSummaryOut {
  return {
    kind: 'strength', primary_muscles: ['chest'], equipment: 'barbell', custom: false, match: 'exact_name', ...overrides,
  }
}

export const BENCH = exercise({ id: 'ex:dumbbell_bench_press', name: '哑铃卧推', equipment: 'dumbbell', primary_muscles: ['chest', 'triceps', 'shoulders'] })
export const SQUAT = exercise({ id: 'ex:squat', name: '深蹲', primary_muscles: ['quads', 'glutes'] })
export const WALK = exercise({ id: 'ex:brisk_walking', name: '快走', kind: 'cardio', equipment: 'none', primary_muscles: ['quads', 'hamstrings', 'calves'] })

export function searchOut(q: string, results: ExerciseSummaryOut[], message = ''): ExerciseSearchOut {
  return { query: q, found: results.length > 0, exact: message === '' && results.length > 0, results, message }
}

/** 哑铃卧推的六次最大重量：8、8、10、10、12、12 千克 */
export function benchTrend(today = todayISO()): ExerciseTrendOut {
  const weights = [8, 8, 10, 10, 12, 12]
  return {
    exercise_id: 'ex:dumbbell_bench_press',
    exercise_name: '哑铃卧推',
    points: weights.map((w, i) => ({
      day: addDays(today, (i - weights.length) * 4), max_weight_kg: w, total_volume: w * 40, total_reps: 40, sets: 4,
    })),
  }
}
