// 经期的接口：经期记录、每日记录、预测、阶段、提示与统计。任何一次修改之后刷新全部经期查询（预测、阶段与统计都按经期重算）。
// 读取只在经期模块开放且已单独同意时请求（否则后端回 403 consent_required）。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { invalidateDomain } from '../invalidation'
import { qk } from '../keys'
import type { CycleStatsOut, DayLogIn, DayLogOut, PeriodCreate, PeriodOut, PhaseOut, PredictionOut, TipsOut } from '../types'
import { useModuleReady } from './consents'

const base = '/api/cycle'

function useRefreshCycle() {
  const queryClient = useQueryClient()
  return () => invalidateDomain(queryClient, 'cycle')
}

/** 全部经期记录，新的在前 */
export function usePeriods() {
  const enabled = useModuleReady('cycle')
  return useQuery({ queryKey: qk.periods, queryFn: ({ signal }) => api<PeriodOut[]>(`${base}/periods`, { signal }), enabled })
}

/** 记录一次经期开始（补记以前的经期时一起带上结束日期，不带则为还没结束） */
export function useCreatePeriod() {
  const refresh = useRefreshCycle()
  return useMutation({
    mutationFn: (body: PeriodCreate) => api<PeriodOut>(`${base}/periods`, { method: 'POST', json: body }),
    onSuccess: refresh,
  })
}

/** 给一次经期填结束日期 */
export function useUpdatePeriod() {
  const refresh = useRefreshCycle()
  return useMutation({
    mutationFn: ({ id, end_date }: { id: string; end_date: string }) =>
      api<PeriodOut>(`${base}/periods/${id}`, { method: 'PATCH', json: { end_date } }),
    onSuccess: refresh,
  })
}

/** 删除一次经期（后端只删这条经期，当天的每日记录不动；预测与统计随之重算） */
export function useDeletePeriod() {
  const refresh = useRefreshCycle()
  return useMutation({
    mutationFn: (id: string) => api<void>(`${base}/periods/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
}

/** 一段日期里的每日记录（含两端） */
export function useDayLogs(start: string, end: string) {
  const enabled = useModuleReady('cycle')
  return useQuery({
    queryKey: qk.dayLogs(start, end),
    queryFn: ({ signal }) => api<DayLogOut[]>(`${base}/day-logs`, { query: { start, end }, signal }),
    enabled,
  })
}

/** 写某一天的记录（整条替换） */
export function usePutDayLog() {
  const refresh = useRefreshCycle()
  return useMutation({
    mutationFn: ({ date, body }: { date: string; body: DayLogIn }) =>
      api<DayLogOut>(`${base}/day-logs/${date}`, { method: 'PUT', json: body }),
    onSuccess: refresh,
  })
}

export function usePrediction() {
  const enabled = useModuleReady('cycle')
  return useQuery({ queryKey: qk.prediction, queryFn: ({ signal }) => api<PredictionOut>(`${base}/prediction`, { signal }), enabled })
}

export function usePhase() {
  const enabled = useModuleReady('cycle')
  return useQuery({ queryKey: qk.phase, queryFn: ({ signal }) => api<PhaseOut>(`${base}/phase`, { signal }), enabled })
}

export function useTips() {
  const enabled = useModuleReady('cycle')
  return useQuery({ queryKey: qk.tips, queryFn: ({ signal }) => api<TipsOut>(`${base}/tips`, { signal }), enabled })
}

export function useCycleStats() {
  const enabled = useModuleReady('cycle')
  return useQuery({ queryKey: qk.cycleStats, queryFn: ({ signal }) => api<CycleStatsOut>(`${base}/stats`, { signal }), enabled })
}
