// 训练的接口：本周汇总、一段日期里的训练、记一次训练、搜索动作与动作趋势。记一次训练之后刷新全部训练查询。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { invalidateDomain } from '../invalidation'
import { qk } from '../keys'
import type { ExerciseSearchOut, ExerciseTrendOut, WeekSummaryOut, WorkoutIn, WorkoutOut } from '../types'

const base = '/api/fitness'

/** 本周（周一到周日）的汇总：次数、能量估算等 */
export function useWeekSummary() {
  return useQuery({ queryKey: qk.weekSummary, queryFn: ({ signal }) => api<WeekSummaryOut>(`${base}/summary/week`, { signal }) })
}

/** 一段日期里的训练（含两端），新的在前；每条带与运动限制的冲突提示 */
export function useWorkouts(start: string, end: string) {
  return useQuery({
    queryKey: qk.workouts(start, end),
    queryFn: ({ signal }) => api<WorkoutOut[]>(`${base}/workouts`, { query: { start, end }, signal }),
  })
}

/**
 * 记一次训练的请求体：重量、次数、时长、距离是用户填的原文时（不是有限的数字）原样发出，让后端给出说明。
 */
export type WorkoutInput = Omit<WorkoutIn, 'duration_minutes' | 'strength' | 'cardio'> & {
  duration_minutes: number | string | null
  strength: { exercise_id: string; sets: { weight_kg: number | string; reps: number | string }[] }[]
  cardio: { exercise_id: string; duration_minutes: number | string; distance_km: number | string | null }[]
}

export function useCreateWorkout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: WorkoutInput) => api<WorkoutOut>(`${base}/workouts`, { method: 'POST', json: body }),
    onSuccess: () => invalidateDomain(queryClient, 'fitness'),
  })
}

/** 搜索动作；q 为空不请求 */
export function useExerciseSearch(q: string) {
  return useQuery({
    queryKey: qk.exerciseSearch(q),
    queryFn: ({ signal }) => api<ExerciseSearchOut>(`${base}/exercises/search`, { query: { q }, signal }),
    enabled: q.length > 0,
  })
}

/** 一个力量动作每次训练的最大重量等（按日期升序）；id 为空不请求 */
export function useExerciseTrend(id: string | null) {
  return useQuery({
    queryKey: qk.exerciseTrend(id ?? ''),
    queryFn: ({ signal }) => api<ExerciseTrendOut>(`${base}/exercises/${id ?? ''}/trend`, { signal }),
    enabled: id !== null,
  })
}
