// 只有医嘱页（健康页的医嘱与录入医嘱）用的接口：医嘱单、证据、手动补充、修改、确认生效、作废、确认解除、审计与约束。
// 对话页也用的待处理列表、条目、事件、继续遵守与不解除在 medical.ts（放在一起会让这些代码进对话页的首屏）。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, handleErrorResponse, networkError } from '../client'
import { qk } from '../keys'
import { getToken } from '../token'
import type {
  ConstraintsOut, EvidenceOut, ItemUpdate, ManualItemCreate, MedicalEventOut, MedicalItemOut, OrderCreate, OrderOut,
} from '../types'
import { base, useRefreshMedical } from './medical'
import { useCapabilities } from './profile'

/** 录入过的医嘱（新的在前），每份带它的条目、证据清单、未提取的句子与说明 */
export function useOrders() {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.orders,
    queryFn: ({ signal }) => api<OrderOut[]>(`${base}/orders`, { signal }),
    enabled: caps.data?.medical === true,
  })
}

/** 本人全部条目的事件（新的在前），历史与审计用 */
export function useMedicalEvents(limit = 50) {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.medicalEvents(limit),
    queryFn: ({ signal }) => api<MedicalEventOut[]>(`${base}/events`, { signal, query: { limit } }),
    enabled: caps.data?.medical === true,
  })
}

/** 今天生效的医嘱约束（生效中与待复核），可按类别筛 */
export function useConstraints(category?: string) {
  const caps = useCapabilities()
  return useQuery({
    queryKey: qk.constraints(category),
    queryFn: ({ signal }) => api<ConstraintsOut>(`${base}/constraints`, { signal, query: { category } }),
    enabled: caps.data?.medical === true,
  })
}

/** 录入一份医嘱：后端提取出的条目全部是待核对 */
export function useCreateOrder() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: (body: OrderCreate) => api<OrderOut>(`${base}/orders`, { method: 'POST', json: body }),
    onSuccess: refresh,
  })
}

/**
 * 给一份医嘱上传一个证据文件（multipart 字段 file）。大小与类型由后端按文件头判断，界面只先提示。
 * 医嘱的编号在建好医嘱之后才有，所以随文件一起传入。
 */
export function useUploadEvidence() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, file }: { orderId: string; file: File }) => {
      const form = new FormData()
      form.append('file', file, file.name)
      return api<EvidenceOut>(`${base}/orders/${orderId}/evidence`, { method: 'POST', body: form })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.orders }),
  })
}

/** 取证据文件的字节；与 api() 一样带令牌、解析错误 */
async function fetchEvidence(id: string, signal: AbortSignal): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(new URL(`${base}/evidence/${id}`, window.location.href), { headers, signal })
  } catch (error) {
    if (signal.aborted) throw error
    throw networkError()
  }
  if (!response.ok) return handleErrorResponse(response)
  return response.blob()
}

/**
 * 证据文件（加密保存的图片或 PDF）：只在查看时请求，不留在缓存里（gcTime 0）。
 * 键不在 ['medical'] 下，刷新医嘱时不会重新下载。取不到时返回后端的错误（界面原样显示说明与错误码）。
 */
export function useEvidenceBlob(evidenceId: string | null): { blob: Blob | null; error: ApiError | null } {
  const evidence = useQuery({
    queryKey: ['medical-evidence', evidenceId ?? ''],
    queryFn: ({ signal }) => fetchEvidence(evidenceId ?? '', signal),
    enabled: evidenceId !== null,
    gcTime: 0,
    staleTime: Infinity,
  })
  if (evidenceId === null || evidence.data !== undefined || !evidence.isError) return { blob: evidence.data ?? null, error: null }
  const caught = evidence.error
  return { blob: null, error: caught instanceof ApiError ? caught : new ApiError(0, 'unknown_error', String(caught)) }
}

/** 给一份医嘱手动补充一条（同样先进入待核对） */
export function useAddManualItem(orderId: string) {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: (body: ManualItemCreate) =>
      api<MedicalItemOut>(`${base}/orders/${orderId}/items`, { method: 'POST', json: body }),
    onSuccess: refresh,
  })
}

/** 修改条目：只发改动了的字段（结束日期与复查日期发 null 表示清除） */
export function useUpdateItem() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: ItemUpdate }) =>
      api<MedicalItemOut>(`${base}/items/${id}`, { method: 'PATCH', json: changes }),
    onSuccess: refresh,
  })
}

/** 确认生效：不带请求体（要改先用“修改”），只能在医嘱页的确认面板里调用 */
export function useConfirmItem() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: (id: string) => api<MedicalItemOut>(`${base}/items/${id}/confirm`, { method: 'POST' }),
    onSuccess: refresh,
  })
}

/** 作废：可带原因；不填原因时不带请求体 */
export function useVoidItem() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      api<MedicalItemOut>(`${base}/items/${id}/void`, { method: 'POST', ...(reason ? { json: { reason } } : {}) }),
    onSuccess: refresh,
  })
}

/** 确认解除：不带请求体，只能在医嘱页的解除面板里勾选“不能撤销”后调用 */
export function useResolveItem() {
  const refresh = useRefreshMedical()
  return useMutation({
    mutationFn: (id: string) => api<MedicalItemOut>(`${base}/items/${id}/resolve`, { method: 'POST' }),
    onSuccess: refresh,
  })
}
