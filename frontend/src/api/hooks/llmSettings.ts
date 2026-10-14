// 模型服务设置页的接口（预设、服务的增改删、获取与手动添加模型、测试连通、能力标注、用途分配）。
// 只有设置页用：llm.ts 在对话页首屏的块里，放在那里会让这些代码进首屏（llm.ts 只留“我的”与对话页要的两个列表）。
// 创建与修改服务的请求体里有密钥：变更结束后不在缓存里多留（gcTime 0；页面在每次提交后 reset，变更随即被回收）。
// 查询缓存里只放后端的响应（只含密钥掩码 key_hint）。
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type {
  AssignmentOut, ConnectionReportOut, FetchModelsOut, ModelOut, ModelUpdatedOut, PresetOut, ProviderOut,
} from '../types'
import type { ProviderKind, Purpose } from '../../lib/labels'

const base = '/api/llm'

export interface ProviderCreateBody {
  name: string
  kind: ProviderKind
  base_url: string
  api_key: string
}

export type ProviderChanges = Partial<Pick<ProviderCreateBody, 'name' | 'base_url' | 'api_key'>>

/** 预设（只用来在界面上填入类型、名称与地址） */
export function usePresets() {
  return useQuery({ queryKey: qk.presets, queryFn: ({ signal }) => api<PresetOut[]>(`${base}/presets`, { signal }) })
}

export { useAssignments, useProviders } from './llm'

function useRefreshProviders() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: qk.providers })
}

/** 添加服务；请求体（含密钥）不留在变更缓存里 */
export function useCreateProvider() {
  const refresh = useRefreshProviders()
  return useMutation({
    gcTime: 0,
    mutationFn: (body: ProviderCreateBody) => api<ProviderOut>(`${base}/providers`, { method: 'POST', json: body }),
    onSuccess: refresh,
  })
}

/** 修改服务（只带改了的字段；改了密钥才带 api_key）；请求体不留在变更缓存里 */
export function useUpdateProvider() {
  const refresh = useRefreshProviders()
  return useMutation({
    gcTime: 0,
    mutationFn: ({ id, changes }: { id: string; changes: ProviderChanges }) =>
      api<ProviderOut>(`${base}/providers/${id}`, { method: 'PATCH', json: changes }),
    onSuccess: refresh,
  })
}

/** 删除服务（后端连同它的模型、用途分配与密钥一起删除）；成功后模型服务的全部查询失效 */
export function useDeleteProvider() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`${base}/providers/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm'] }),
  })
}

/** 该服务下现有的全部模型（含手动添加的） */
export function useProviderModels(id: string | null) {
  return useQuery({
    queryKey: qk.providerModels(id ?? ''),
    queryFn: ({ signal }) => api<ModelOut[]>(`${base}/providers/${id ?? ''}/models`, { signal }),
    enabled: id !== null,
  })
}

/**
 * 从服务拉取模型列表（mutate 的参数是服务编号：刚创建的服务在同一次提交里接着获取）；
 * 返回的全部模型直接写进该服务的模型缓存
 */
export function useFetchModels() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (providerId: string) =>
      api<FetchModelsOut>(`${base}/providers/${providerId}/fetch-models`, { method: 'POST' }),
    onSuccess: (result, providerId) => {
      queryClient.setQueryData(qk.providerModels(providerId), result.models)
    },
  })
}

/** 手动添加一个模型编号；新模型直接加进该服务的模型缓存 */
export function useAddModel(id: string | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (modelId: string) =>
      api<ModelOut>(`${base}/providers/${id ?? ''}/models`, { method: 'POST', json: { model_id: modelId } }),
    onSuccess: (model) => {
      queryClient.setQueryData<ModelOut[]>(qk.providerModels(model.provider_id), (models) => [...(models ?? []), model])
    },
  })
}

/** 测试连通（model_id 是模型编号字符串，给了才做对话测试）；服务那边的失败也是 200，结论在报告里 */
export function useTestProvider(id: string | null) {
  return useMutation({
    mutationFn: (modelId: string | undefined) =>
      api<ConnectionReportOut>(`${base}/providers/${id ?? ''}/test`, {
        method: 'POST', json: modelId ? { model_id: modelId } : {},
      }),
  })
}

/** 手动标注能力（值 true，或 null 回到对照表）；返回的模型写回所在服务的模型缓存，分配的用途也刷新 */
export function useUpdateModelOverrides() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ pk, overrides }: { pk: string; overrides: Partial<Record<'vision' | 'tools' | 'chat', true | null>> }) =>
      api<ModelUpdatedOut>(`${base}/models/${pk}`, { method: 'PATCH', json: overrides }),
    onSuccess: (model) => {
      queryClient.setQueryData<ModelOut[]>(qk.providerModels(model.provider_id), (models) =>
        models?.map((m) => (m.id === model.id ? model : m)))
      return queryClient.invalidateQueries({ queryKey: qk.assignments })
    },
  })
}

/** 把某个用途分配给一个模型（model_id 是模型主键） */
export function useSetAssignment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ purpose, modelPk }: { purpose: Purpose; modelPk: string }) =>
      api<AssignmentOut>(`${base}/assignments/${purpose}`, { method: 'PUT', json: { model_id: modelPk } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.assignments }),
  })
}
