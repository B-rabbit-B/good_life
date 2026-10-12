// 饮食记录的接口：每日汇总、当天的记录、搜索食物、食物详情与记一餐。按日期返回测试给的数据（没给的日期是空的一天），
// 记下记一餐的请求体，供测试核对。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { FoodDetailOut, MealOut, NutritionSearchOut, SummaryOut } from '../../../api/types'
import { todayISO } from '../../../lib/dates'
import { emptySummary, foodDetail, mealEntry } from '../../fixtures/nutrition'

export interface NutritionOptions {
  /** 按日期的汇总；没给的日期是空的一天 */
  summaries?: Record<string, SummaryOut>
  /** 按日期的记录 */
  meals?: Record<string, MealOut[]>
  /** 汇总的错误（例如 500）；每次请求都返回 */
  summaryError?: { status: number; code: string; message: string }
  /** 按搜索词的结果；没给的词按后端的“未找到”回答 */
  search?: Record<string, NutritionSearchOut>
  foods?: FoodDetailOut[]
  /** 记一餐的错误；只对第一次请求生效 */
  createError?: { status: number; code: string; message: string }
}

const error = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status })

export function nutritionHandlers(opts: NutritionOptions = {}) {
  const created: unknown[] = []
  const summaryDates: string[] = []
  let createError = opts.createError
  const handlers: HttpHandler[] = [
    http.get('/api/nutrition/summary', ({ request }) => {
      const date = new URL(request.url).searchParams.get('date') ?? todayISO()
      summaryDates.push(date)
      if (opts.summaryError) return error(opts.summaryError.status, opts.summaryError.code, opts.summaryError.message)
      return HttpResponse.json(opts.summaries?.[date] ?? emptySummary(date))
    }),
    http.get('/api/nutrition/meals', ({ request }) => {
      const date = new URL(request.url).searchParams.get('date') ?? todayISO()
      return HttpResponse.json(opts.meals?.[date] ?? [])
    }),
    http.get('/api/nutrition/foods/search', ({ request }) => {
      const q = new URL(request.url).searchParams.get('q') ?? ''
      return HttpResponse.json(opts.search?.[q] ?? {
        query: q, found: false, exact: false, results: [], message: `未找到与“${q}”匹配的食物，请换个说法或检查错别字`,
      })
    }),
    http.get('/api/nutrition/foods/:id', ({ params }) => {
      const food = (opts.foods ?? [foodDetail()]).find((f) => f.id === String(params.id))
      return food ? HttpResponse.json(food) : error(404, 'food_not_found', '营养库里没有这个食物')
    }),
    http.post('/api/nutrition/meals', async ({ request }) => {
      const body = (await request.json()) as { eaten_on: string; meal_type: MealOut['meal_type']; food_id: string; grams?: number }
      created.push(body)
      if (createError) {
        const { status, code, message } = createError
        createError = undefined
        return error(status, code, message)
      }
      return HttpResponse.json(mealEntry({ eaten_on: body.eaten_on, meal_type: body.meal_type, food_id: body.food_id }), { status: 201 })
    }),
  ]
  return { handlers, created, summaryDates }
}
