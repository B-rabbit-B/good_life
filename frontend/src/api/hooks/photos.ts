import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, type RefObject } from 'react'
import { api, handleErrorResponse, networkError } from '../client'
import { qk } from '../keys'
import { getToken } from '../token'
import type { PhotoItemIn, RecognitionOut, RecognitionSummaryOut } from '../types'
import type { MealType } from '../../lib/labels'

const base = '/api/photos/recognitions'

/** 本人的识别记录（新的在前，不带评价） */
export function useRecognitions() {
  return useQuery({
    queryKey: qk.recognitions,
    queryFn: ({ signal }) => api<RecognitionSummaryOut[]>(base, { signal }),
  })
}

/** 一条识别记录（草稿才带整餐评价） */
export function useRecognition(id: string) {
  return useQuery({
    queryKey: qk.recognition(id),
    queryFn: ({ signal }) => api<RecognitionOut>(`${base}/${id}`, { signal }),
  })
}

/** 返回的记录写进缓存，列表另行刷新 */
function useStoreRecognition(id: string) {
  const queryClient = useQueryClient()
  return async (record: RecognitionOut) => {
    queryClient.setQueryData(qk.recognition(id), record)
    await queryClient.invalidateQueries({ queryKey: qk.recognitions, exact: true })
  }
}

/** 修正后的一项：克数可以是用户填的原文（不是有限的数字时原样发出，让后端给出说明） */
export type PhotoItemPatch = Omit<PhotoItemIn, 'grams'> & { grams?: number | string | null }

/** 修正识别项：整组替换（items 由 features/photos/itemsUpdate.ts 生成） */
export function useUpdateRecognitionItems(id: string) {
  const store = useStoreRecognition(id)
  return useMutation({
    mutationFn: (items: PhotoItemPatch[]) => api<RecognitionOut>(`${base}/${id}/items`, { method: 'PUT', json: { items } }),
    onSuccess: store,
  })
}

/** 确认入库：写入那一天的饮食记录，所以那一天的汇总与记录也要重新取 */
export function useConfirmRecognition(id: string) {
  const store = useStoreRecognition(id)
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { eaten_on: string; meal_type: MealType }) =>
      api<RecognitionOut>(`${base}/${id}/confirm`, { method: 'POST', json: body }),
    onSuccess: async (record, { eaten_on }) => {
      await Promise.all([
        store(record),
        queryClient.invalidateQueries({ queryKey: qk.summary(eaten_on) }),
        queryClient.invalidateQueries({ queryKey: qk.meals(eaten_on) }),
      ])
    },
  })
}

export function useDiscardRecognition(id: string) {
  const store = useStoreRecognition(id)
  return useMutation({
    mutationFn: () => api<RecognitionOut>(`${base}/${id}/discard`, { method: 'POST' }),
    onSuccess: store,
  })
}

/** 取保留的图片（JPEG 字节）；与 api() 同样带令牌、解析错误 */
async function fetchImage(id: string, signal: AbortSignal): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(new URL(`${base}/${id}/image`, window.location.href), { headers, signal })
  } catch (error) {
    if (signal.aborted) throw error
    throw networkError()
  }
  if (!response.ok) return handleErrorResponse(response)
  return response.blob()
}

/**
 * 保留的照片：只在 image_kept 为真时请求（enabled）。图片不留在查询缓存里（gcTime 0），离开页面就丢掉。
 * 返回图片的字节；显示时用 useObjectUrl 生成 object URL（卸载时释放）。
 */
export function useRecognitionImage(id: string, enabled: boolean): Blob | null {
  const image = useQuery({
    queryKey: qk.recognitionImage(id),
    queryFn: ({ signal }) => fetchImage(id, signal),
    enabled,
    gcTime: 0,
    staleTime: Infinity,
  })
  return enabled ? image.data ?? null : null
}

/**
 * 把 blob 交给 <img>：在副作用里生成 object URL 写到图片的 src 上，换图或卸载时释放
 * （严格模式下副作用跑两遍也是先释放、再生成新的，不会把还在用的地址释放掉）。
 */
export function useObjectUrl(blob: Blob): RefObject<HTMLImageElement | null> {
  const ref = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const img = ref.current
    if (!img || typeof URL.createObjectURL !== 'function') return undefined
    const url = URL.createObjectURL(blob)
    img.src = url
    return () => {
      img.removeAttribute('src')
      URL.revokeObjectURL(url)
    }
  }, [blob])
  return ref
}
