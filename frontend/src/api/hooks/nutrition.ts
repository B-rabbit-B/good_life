import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import { qk } from '../keys'
import type { FoodDetailOut, MealCreate, MealOut, NutritionSearchOut, SummaryOut } from '../types'

/** 某一天的汇总：摄入、需求与还可摄入（YYYY-MM-DD） */
export function useSummary(date: string) {
  return useQuery({
    queryKey: qk.summary(date),
    queryFn: ({ signal }) => api<SummaryOut>('/api/nutrition/summary', { query: { date }, signal }),
  })
}

/** 某一天的饮食记录（按餐次与时间排好） */
export function useMeals(date: string) {
  return useQuery({
    queryKey: qk.meals(date),
    queryFn: ({ signal }) => api<MealOut[]>('/api/nutrition/meals', { query: { date }, signal }),
  })
}

/** 搜索食物；q 为空不请求 */
export function useFoodSearch(q: string) {
  return useQuery({
    queryKey: qk.foodSearch(q),
    queryFn: ({ signal }) => api<NutritionSearchOut>('/api/nutrition/foods/search', { query: { q }, signal }),
    enabled: q.length > 0,
  })
}

/** 一种食物的详情（常用份量在 portions 里）；id 为空不请求 */
export function useFood(id: string | null) {
  return useQuery({
    queryKey: qk.food(id ?? ''),
    queryFn: ({ signal }) => api<FoodDetailOut>(`/api/nutrition/foods/${id ?? ''}`, { signal }),
    enabled: id !== null,
  })
}

/**
 * 记一餐的请求体：克数或份数是用户填的原文时（不是有限的数字）原样发出，让后端给出说明；
 * 克数与 portion 二选一（后端规则）。
 */
export type MealInput = Omit<MealCreate, 'grams' | 'portion'> & {
  grams?: number | string | null
  portion?: { unit: string; count: number | string } | null
}

/** 记一餐；成功后那一天的汇总与记录重新取 */
export function useCreateMeal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MealInput) => api<MealOut>('/api/nutrition/meals', { method: 'POST', json: body }),
    onSuccess: async (_meal, { eaten_on }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: qk.summary(eaten_on) }),
        queryClient.invalidateQueries({ queryKey: qk.meals(eaten_on) }),
      ])
    },
  })
}
