// 经期的接口：一个内存里的经期与每日记录仓库（开始 POST、结束 PATCH、删除 DELETE、当天记录 PUT 整条替换），预测、阶段、提示与统计
// 返回测试给的数据（不按经期重算）。记下每个写请求供测试核对；errors 里的错误只对那个动作的第一次请求生效，
// hold 里的 Promise 兑现之前那个动作的请求一直不返回（测试“请求进行中”）。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type {
  CycleStatsOut, DayLogIn, DayLogOut, PeriodCreate, PeriodOut, PhaseOut, PredictionOut, TipsOut,
} from '../../../api/types'
import { insufficientPrediction, phase as phaseFixture, stats as statsFixture, tips as tipsFixture } from '../../fixtures/cycle'

export interface CycleError {
  status: number
  code: string
  message: string
  details?: { field: string; message: string }[]
}

type Action = 'createPeriod' | 'updatePeriod' | 'deletePeriod' | 'putDayLog'

export interface CycleOptions {
  /** 经期，新的在前 */
  periods?: PeriodOut[]
  dayLogs?: DayLogOut[]
  prediction?: PredictionOut
  phase?: PhaseOut
  tips?: TipsOut
  stats?: CycleStatsOut
  /** 各个写动作的错误；只对第一次请求生效 */
  errors?: Partial<Record<Action, CycleError>>
  /** 这些动作的请求先等这个 Promise 兑现再处理 */
  hold?: Partial<Record<Action, Promise<void>>>
  /** 这些动作的请求直接断网（fetch 被拒绝）；只对第一次请求生效 */
  networkFail?: Partial<Record<Action, boolean>>
}

const errorResponse = ({ status, code, message, details }: CycleError) =>
  HttpResponse.json({ error: { code, message, ...(details ? { details } : {}) } }, { status })

export function cycleHandlers(opts: CycleOptions = {}) {
  let periods: PeriodOut[] = [...(opts.periods ?? [])]
  let dayLogs: DayLogOut[] = [...(opts.dayLogs ?? [])]
  const errors = { ...opts.errors }
  const networkFail = { ...opts.networkFail }
  let counter = 0
  const record = {
    created: [] as unknown[],
    updated: [] as { id: string; body: unknown }[],
    deleted: [] as string[],
    putLogs: [] as { date: string; body: DayLogIn }[],
    dayLogRanges: [] as { start: string | null; end: string | null }[],
  }
  const take = (action: Action) => {
    const error = errors[action]
    delete errors[action]
    return error
  }
  const failNetwork = (action: Action) => {
    const fail = networkFail[action] === true
    delete networkFail[action]
    return fail
  }
  const sorted = () => [...periods].sort((a, b) => b.start_date.localeCompare(a.start_date))

  const handlers: HttpHandler[] = [
    http.get('/api/cycle/periods', () => HttpResponse.json(sorted())),
    http.post('/api/cycle/periods', async ({ request }) => {
      const body = await request.json() as PeriodCreate
      record.created.push(body)
      await opts.hold?.createPeriod
      if (failNetwork('createPeriod')) return HttpResponse.error()
      const error = take('createPeriod')
      if (error) return errorResponse(error)
      counter += 1
      const created: PeriodOut = {
        id: `50000000-0000-4000-8000-${String(counter).padStart(12, '0')}`,
        start_date: body.start_date, end_date: body.end_date ?? null, created_at: new Date().toISOString(),
      }
      periods = [...periods, created]
      return HttpResponse.json(created, { status: 201 })
    }),
    http.patch('/api/cycle/periods/:id', async ({ params, request }) => {
      const id = String(params.id)
      const body = await request.json() as { end_date: string }
      record.updated.push({ id, body })
      await opts.hold?.updatePeriod
      if (failNetwork('updatePeriod')) return HttpResponse.error()
      const error = take('updatePeriod')
      if (error) return errorResponse(error)
      const found = periods.find((p) => p.id === id)
      if (!found) return errorResponse({ status: 404, code: 'not_found', message: '记录不存在' })
      const next = { ...found, end_date: body.end_date }
      periods = periods.map((p) => (p.id === id ? next : p))
      return HttpResponse.json(next)
    }),
    http.delete('/api/cycle/periods/:id', async ({ params }) => {
      const id = String(params.id)
      record.deleted.push(id)
      await opts.hold?.deletePeriod
      if (failNetwork('deletePeriod')) return HttpResponse.error()
      const error = take('deletePeriod')
      if (error) return errorResponse(error)
      if (!periods.some((p) => p.id === id)) return errorResponse({ status: 404, code: 'not_found', message: '记录不存在' })
      periods = periods.filter((p) => p.id !== id)
      return new HttpResponse(null, { status: 204 })
    }),
    http.get('/api/cycle/day-logs', ({ request }) => {
      const params = new URL(request.url).searchParams
      const start = params.get('start')
      const end = params.get('end')
      record.dayLogRanges.push({ start, end })
      return HttpResponse.json(dayLogs
        .filter((log) => (start === null || log.log_date >= start) && (end === null || log.log_date <= end))
        .sort((a, b) => a.log_date.localeCompare(b.log_date)))
    }),
    http.put('/api/cycle/day-logs/:date', async ({ params, request }) => {
      const date = String(params.date)
      const body = await request.json() as DayLogIn
      record.putLogs.push({ date, body })
      await opts.hold?.putDayLog
      if (failNetwork('putDayLog')) return HttpResponse.error()
      const error = take('putDayLog')
      if (error) return errorResponse(error)
      const saved: DayLogOut = {
        log_date: date, flow: body.flow ?? null, pain: body.pain ?? null, mood: body.mood ?? null,
        symptoms: body.symptoms ?? [], note: body.note ?? null, updated_at: new Date().toISOString(),
      }
      dayLogs = [...dayLogs.filter((log) => log.log_date !== date), saved]
      return HttpResponse.json(saved)
    }),
    http.get('/api/cycle/prediction', () => HttpResponse.json(opts.prediction ?? insufficientPrediction())),
    http.get('/api/cycle/phase', () => HttpResponse.json(opts.phase ?? phaseFixture(undefined, {
      phase: 'unknown', cycle_day: null, days_until_next_period: null, is_predicted: false, reason: 'no_data', flags: [],
    }))),
    http.get('/api/cycle/tips', () => HttpResponse.json(opts.tips ?? tipsFixture(undefined, { tips: [] }))),
    http.get('/api/cycle/stats', () => HttpResponse.json(opts.stats ?? statsFixture({
      cycle_count: 0, period_count: 0, avg_cycle_length: null, cycle_length_std: null, shortest_cycle: null,
      longest_cycle: null, avg_period_length: null, recent_cycle_lengths: [], logged_days: 0,
    }))),
  ]
  return { handlers, record }
}
