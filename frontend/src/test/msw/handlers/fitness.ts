// 训练的接口：周汇总（返回测试给的数据）、一个内存里的训练仓库（按日期范围取，新的在前；记一次训练追加进去）、
// 搜索动作与动作趋势。记下每次记一次训练的请求体与取训练的日期范围；errors 只对第一次请求生效，hold 兑现前请求不返回。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type {
  ConflictOut, ExerciseSearchOut, ExerciseTrendOut, WeekSummaryOut, WorkoutIn, WorkoutOut,
} from '../../../api/types'
import { weekSummary } from '../../fixtures/fitness'

export interface FitnessError {
  status: number
  code: string
  message: string
  details?: { field: string; message: string }[]
}

export interface FitnessOptions {
  summary?: WeekSummaryOut
  summaryError?: FitnessError
  workouts?: WorkoutOut[]
  /** 按搜索词的结果；没给的词按后端的“未找到”回答 */
  search?: Record<string, ExerciseSearchOut>
  /** 按动作编号的趋势；没给的按后端回答 404 */
  trends?: Record<string, ExerciseTrendOut>
  /** 记一次训练的错误；只对第一次请求生效 */
  createError?: FitnessError
  /** 记一次训练成功时附带的冲突提示 */
  createConflicts?: ConflictOut[]
  hold?: { create?: Promise<void> }
}

const errorResponse = ({ status, code, message, details }: FitnessError) =>
  HttpResponse.json({ error: { code, message, ...(details ? { details } : {}) } }, { status })

export function fitnessHandlers(opts: FitnessOptions = {}) {
  let workouts: WorkoutOut[] = [...(opts.workouts ?? [])]
  let createError = opts.createError
  let counter = 0
  const record = {
    created: [] as WorkoutIn[],
    ranges: [] as { start: string | null; end: string | null }[],
    trendRequests: [] as string[],
  }

  const handlers: HttpHandler[] = [
    http.get('/api/fitness/summary/week', () =>
      (opts.summaryError ? errorResponse(opts.summaryError) : HttpResponse.json(opts.summary ?? weekSummary(undefined, {
        workout_count: 0, training_days: 0, total_volume: 0, muscle_volumes: {}, cardio_minutes: 0,
        energy_low_kcal: 0, energy_high_kcal: 0,
      })))),
    http.get('/api/fitness/workouts', ({ request }) => {
      const params = new URL(request.url).searchParams
      const start = params.get('start')
      const end = params.get('end')
      record.ranges.push({ start, end })
      return HttpResponse.json(workouts
        .filter((w) => (start === null || w.performed_on >= start) && (end === null || w.performed_on <= end))
        .sort((a, b) => b.performed_on.localeCompare(a.performed_on)))
    }),
    http.post('/api/fitness/workouts', async ({ request }) => {
      const body = await request.json() as WorkoutIn
      record.created.push(body)
      await opts.hold?.create
      if (createError) {
        const error = createError
        createError = undefined
        return errorResponse(error)
      }
      counter += 1
      const id = `61000000-0000-4000-8000-${String(counter).padStart(12, '0')}`
      const created: WorkoutOut = {
        id, performed_on: body.performed_on, duration_minutes: body.duration_minutes ?? null, rpe: null, note: null,
        strength: (body.strength ?? []).map((block, i) => ({
          exercise_id: block.exercise_id, exercise_name: block.exercise_id, position: i + 1,
          sets: block.sets.map((set, j) => ({ set_index: j + 1, weight_kg: set.weight_kg, reps: set.reps, rest_seconds: null, rpe: null })),
        })),
        cardio: (body.cardio ?? []).map((item, i) => ({
          exercise_id: item.exercise_id, exercise_name: item.exercise_id, position: i + 1,
          duration_minutes: item.duration_minutes, distance_km: item.distance_km ?? null, rpe: null,
        })),
        conflicts: opts.createConflicts ?? [],
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      }
      workouts = [created, ...workouts]
      return HttpResponse.json(created, { status: 201 })
    }),
    http.get('/api/fitness/exercises/search', ({ request }) => {
      const q = new URL(request.url).searchParams.get('q') ?? ''
      return HttpResponse.json(opts.search?.[q] ?? {
        query: q, found: false, exact: false, results: [], message: `未找到与“${q}”匹配的动作，可以新增自定义动作`,
      })
    }),
    http.get('/api/fitness/exercises/:id/trend', ({ params }) => {
      const id = String(params.id)
      record.trendRequests.push(id)
      const trend = opts.trends?.[id]
      return trend ? HttpResponse.json(trend) : errorResponse({ status: 404, code: 'exercise_not_found', message: '没有找到这个动作' })
    }),
  ]
  return { handlers, record }
}
