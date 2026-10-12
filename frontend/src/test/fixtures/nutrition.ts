// 饮食记录的测试数据：照设计稿 05 的一天（早餐、午餐来自拍照识别、加餐，晚餐未记），需求按后端的估算规则写出。
// 文案取自后端（app/nutrition/needs.py、schemas.py 与 router.py）。
import type {
  FoodDetailOut, MealOut, NutritionSearchOut, NutrientsOut, SummaryOut,
} from '../../api/types'
import type { MealType } from '../../lib/labels'
import { PHOTO_MEAL_NOTE } from '../../lib/contract'
import { todayISO } from '../../lib/dates'

export const SUMMARY_DISCLAIMER = '以上汇总与需求都是估算，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。'
export const ESTIMATE_NOTE = '以上是根据档案估算的大致需求，不是医疗指标；有医嘱或慢性病时以医嘱为准。'
export const INSUFFICIENT_NOTE = '档案缺少估算所需的信息，补充后才能估算每日需求。'
export const PARTIAL_MATCH_MESSAGE = '没有完全一致的食物，下面是名称相近的候选，请确认是否是你要找的'

const zero = (): NutrientsOut => ({
  energy_kcal: 0, protein_g: 0, fat_g: 0, carbohydrate_g: 0, fiber_g: 0, sodium_mg: 0, iron_mg: 0, calcium_mg: 0,
})

export function summary(over: Partial<SummaryOut> = {}): SummaryOut {
  return {
    date: todayISO(),
    meals: {
      breakfast: { ...zero(), energy_kcal: 412, protein_g: 21.3 },
      lunch: { ...zero(), energy_kcal: 515, protein_g: 23.1 },
      dinner: zero(),
      snack: { ...zero(), energy_kcal: 158, protein_g: 8 },
    },
    total: {
      energy_kcal: 1085, protein_g: 52.4, fat_g: 38.1, carbohydrate_g: 128, fiber_g: 9.2, sodium_mg: 1640,
      iron_mg: 9.1, calcium_mg: 420,
    },
    incomplete_fields: [],
    needs: {
      status: 'ok', missing_fields: [], energy_kcal: 1850, energy_kcal_low: 1665, energy_kcal_high: 2035, protein_g: 70,
      fat_g_low: 41, fat_g_high: 62, carbohydrate_g_low: 231, carbohydrate_g_high: 301, fiber_g_low: 25, fiber_g_high: 30,
      sodium_mg_max: 2000, notes: [ESTIMATE_NOTE],
    },
    remaining: { energy_kcal: 765, protein_g: 17.6, sodium_mg: 360 },
    disclaimer: SUMMARY_DISCLAIMER,
    ...over,
  }
}

/** 档案不全、估算不了需求的一天 */
export function insufficientSummary(over: Partial<SummaryOut> = {}): SummaryOut {
  return summary({
    needs: {
      status: 'insufficient_profile', missing_fields: ['height_cm'], energy_kcal: null, energy_kcal_low: null,
      energy_kcal_high: null, protein_g: null, fat_g_low: null, fat_g_high: null, carbohydrate_g_low: null,
      carbohydrate_g_high: null, fiber_g_low: null, fiber_g_high: null, sodium_mg_max: null, notes: [INSUFFICIENT_NOTE],
    },
    remaining: null,
    ...over,
  })
}

/** 一条记录也没有的一天 */
export function emptySummary(date = todayISO()): SummaryOut {
  return summary({
    date,
    meals: { breakfast: zero(), lunch: zero(), dinner: zero(), snack: zero() },
    total: zero(),
    remaining: { energy_kcal: 1850, protein_g: 70, sodium_mg: 2000 },
  })
}

let seq = 0
const at = (date: string, hour: number, minute: number) => {
  const [y = 2026, m = 1, d = 1] = date.split('-').map(Number)
  return new Date(y, m - 1, d, hour, minute).toISOString()
}

export function mealEntry(over: Partial<MealOut> & { time?: [number, number] } = {}): MealOut {
  seq += 1
  const { time = [12, 0], ...rest } = over
  const eatenOn = rest.eaten_on ?? todayISO()
  const created = at(eatenOn, time[0], time[1])
  return {
    id: `00000000-0000-4000-8000-2000000000${String(seq).padStart(2, '0')}`,
    eaten_on: eatenOn,
    meal_type: 'lunch',
    food_id: 'cfcd:rice',
    food_name: '米饭',
    grams: 150,
    nutrients: { ...zero(), energy_kcal: 174 },
    note: null,
    created_at: created,
    updated_at: created,
    ...rest,
  }
}

const entry = (meal_type: MealType, food_name: string, grams: number, kcal: number, time: [number, number], note?: string) =>
  mealEntry({ meal_type, food_name, grams, time, note: note ?? null, nutrients: { ...zero(), energy_kcal: kcal } })

/** 设计稿 05 的三餐：午餐来自拍照识别 */
export function dayMeals(): MealOut[] {
  return [
    entry('breakfast', '燕麦牛奶粥', 300, 186, [7, 40]),
    entry('breakfast', '水煮蛋', 50, 72, [7, 41]),
    entry('breakfast', '全麦面包', 60, 154, [7, 42]),
    entry('lunch', '米饭', 200, 232, [12, 20], PHOTO_MEAL_NOTE),
    entry('lunch', '番茄炒蛋', 160, 155, [12, 20], PHOTO_MEAL_NOTE),
    entry('lunch', '清炒油麦菜', 250, 128, [12, 20], PHOTO_MEAL_NOTE),
    entry('snack', '苹果', 180, 95, [15, 30]),
    entry('snack', '无糖酸奶', 100, 63, [15, 31]),
  ]
}

export function foodDetail(over: Partial<FoodDetailOut> = {}): FoodDetailOut {
  return {
    id: 'cfcd:rice',
    name: '米饭',
    aliases: ['白米饭'],
    category: '谷类及制品',
    kind: 'ingredient',
    nutrients_per_100g: { ...zero(), energy_kcal: 116, protein_g: 2.6 },
    tags: [],
    portions: [{ unit: '碗', grams: 150 }, { unit: '勺', grams: 30 }],
    default_grams: 150,
    source: { dataset: '中国食物成分表', reference: '第 6 版', license_status: 'reference_only', note: '' },
    ...over,
  }
}

export function searchResult(q: string, over: Partial<NutritionSearchOut> = {}): NutritionSearchOut {
  return {
    query: q,
    found: true,
    exact: true,
    results: [{ id: 'cfcd:rice', name: '米饭', aliases: ['白米饭'], category: '谷类及制品', kind: 'ingredient', match: 'exact_name' }],
    message: '',
    ...over,
  }
}

/** 名称相近、没有完全一致的搜索结果（后端给出 PARTIAL_MATCH_MESSAGE） */
export function partialSearchResult(q: string): NutritionSearchOut {
  return searchResult(q, {
    exact: false,
    message: PARTIAL_MATCH_MESSAGE,
    results: [
      { id: 'cfcd:rice', name: '米饭', aliases: ['白米饭'], category: '谷类及制品', kind: 'ingredient', match: 'contains' },
      { id: 'cfcd:fried_rice', name: '蛋炒饭', aliases: [], category: '菜肴', kind: 'dish', match: 'contains' },
    ],
  })
}
