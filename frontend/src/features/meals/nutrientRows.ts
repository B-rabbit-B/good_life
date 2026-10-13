// 营养表的五行：已摄入、需要（区间写“低–高”）、还差（只有汇总的 remaining 里有的项，其余写“—”）。
// 数字都来自后端，界面只排版：进度条是已摄入除以需要（区间按下限），超过一满格按满格画；
// 钠的需要是上限；remaining.sodium_mg 不大于 0 时整行赭色。
import type { NutrientsOut, SummaryOut } from '../../api/types'
import { fmtFixed, fmtInt, fmtNum } from '../../lib/format'

/**
 * 营养素字段的中文名（NutrientsOut 的键，也是汇总里 incomplete_fields 的取值）。
 * 只有饮食页用到，所以放在这里而不是 lib/labels.ts（那个模块在对话页的首屏块里）。
 */
export const NUTRIENT_LABELS: Record<keyof NutrientsOut, string> = {
  energy_kcal: '热量',
  protein_g: '蛋白质',
  fat_g: '脂肪',
  carbohydrate_g: '碳水化合物',
  fiber_g: '膳食纤维',
  sodium_mg: '钠',
  iron_mg: '铁',
  calcium_mg: '钙',
}

export interface NutrientRow {
  key: 'protein' | 'fat' | 'carbohydrate' | 'fiber' | 'sodium'
  label: string
  /** 已摄入，已格式化（克保留一位小数，毫克去掉末尾的 0） */
  intake: string
  unit: '克' | '毫克'
  need: string
  remaining: string
  /** 进度条填满的比例，0 到 1 */
  fill: number
  /** 需要是上限（钠） */
  limit: boolean
  warn: boolean
}

const DASH = '—'

interface Spec {
  key: NutrientRow['key']
  field: keyof NutrientsOut
  unit: NutrientRow['unit']
  need: (needs: SummaryOut['needs']) => [number | null, number | null]
  remaining?: string
  limit?: boolean
}

const SPECS: Spec[] = [
  { key: 'protein', field: 'protein_g', unit: '克', need: (n) => [n.protein_g, null], remaining: 'protein_g' },
  { key: 'fat', field: 'fat_g', unit: '克', need: (n) => [n.fat_g_low, n.fat_g_high] },
  { key: 'carbohydrate', field: 'carbohydrate_g', unit: '克', need: (n) => [n.carbohydrate_g_low, n.carbohydrate_g_high] },
  { key: 'fiber', field: 'fiber_g', unit: '克', need: (n) => [n.fiber_g_low, n.fiber_g_high] },
  { key: 'sodium', field: 'sodium_mg', unit: '毫克', need: (n) => [n.sodium_mg_max, null], remaining: 'sodium_mg', limit: true },
]

const amount = (value: number, unit: NutrientRow['unit']) => (unit === '克' ? fmtFixed(value, 1) : fmtNum(value, 1))

export function nutrientRows(summary: SummaryOut): NutrientRow[] {
  return SPECS.map((spec) => {
    const intake = summary.total[spec.field] ?? null
    const [low, high] = spec.need(summary.needs)
    const left = spec.remaining ? summary.remaining?.[spec.remaining] : undefined
    let need = DASH
    if (low !== null) need = high === null ? fmtInt(low) : `${fmtInt(low)}–${fmtInt(high)}`
    return {
      key: spec.key,
      label: NUTRIENT_LABELS[spec.field],
      intake: intake === null ? DASH : amount(intake, spec.unit),
      unit: spec.unit,
      need,
      remaining: left === undefined ? DASH : amount(left, spec.unit),
      fill: intake === null || low === null || low <= 0 ? 0 : Math.min(1, Math.max(0, intake / low)),
      limit: spec.limit ?? false,
      warn: spec.key === 'sodium' && left !== undefined && left <= 0,
    }
  })
}
