// 拍照识别的测试数据：照设计稿 04b 的四道菜（杂粮饭、清蒸鲈鱼、把握较低且克数估算的卤猪肝、没匹配到营养库的酸汤肥牛）
// 与它们的整餐评价。文案取自后端（app/photos/service.py 与 app/nutrition/engine.py）。
import type { NutrientsOut, PhotoEvaluationOut, PhotoItemOut, RecognitionOut } from '../../api/types'

export const REC_ID = '00000000-0000-4000-8000-0000000000a1'
export const PHOTO_DISCLAIMER = '菜品与份量由模型估算，热量与营养由营养库按份量计算，仅供参考；请核对后再确认入库。'
export const ENGINE_DISCLAIMER = '以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。'
export const UNCHECKED_NOTICE = '以下菜品没能匹配到营养库，暂时没有按你的医嘱和饮食约束核对：酸汤肥牛。'
  + '请先从候选里选择对应的食物或改名，核对之后再吃或再确认入库。'

export function nutrients(over: Partial<NutrientsOut> = {}): NutrientsOut {
  return {
    energy_kcal: 207, protein_g: 4.9, fat_g: 1.1, carbohydrate_g: 44.3, fiber_g: 2.2, sodium_mg: 3.6,
    iron_mg: 0.9, calcium_mg: 12, ...over,
  }
}

export function photoItem(over: Partial<PhotoItemOut> = {}): PhotoItemOut {
  return {
    id: 'item-rice',
    name: '杂粮饭',
    portion_text: '一碗',
    grams: 180,
    grams_source: 'portion',
    confidence: 0.91,
    status: 'matched',
    food_id: 'cfcd:mixed_rice',
    food_name: '杂粮饭',
    match_type: 'exact_name',
    candidates: [],
    nutrients: nutrients(),
    source: { dataset: '中国食物成分表', license_status: 'reference_only', note: '' },
    review_reasons: [],
    ...over,
  }
}

export const rice = () => photoItem()
export const fish = () => photoItem({
  id: 'item-fish', name: '清蒸鲈鱼', portion_text: '半条', grams: 220, confidence: 0.84,
  food_id: 'dish:steamed_bass', food_name: '鲈鱼（蒸）', match_type: 'common_name',
  nutrients: nutrients({ energy_kcal: 231, protein_g: 40.9, fat_g: 7.3, sodium_mg: 312 }),
})
export const liver = () => photoItem({
  id: 'item-liver', name: '卤猪肝', portion_text: '一小碟', grams: 80, grams_source: 'model', confidence: 0.58,
  food_id: 'dish:braised_liver', food_name: '猪肝（卤）',
  nutrients: nutrients({ energy_kcal: 129, protein_g: 15.6, fat_g: 5.8, sodium_mg: 696 }),
  review_reasons: ['low_confidence', 'estimated_grams'],
})
export const beef = () => photoItem({
  id: 'item-beef', name: '酸汤肥牛', portion_text: '一份', grams: 250, grams_source: 'group', confidence: 0.77,
  status: 'needs_confirmation', food_id: null, food_name: null, match_type: null, nutrients: null, source: null,
  candidates: [
    { food_id: 'cfcd:beef_hotpot', name: '肥牛（火锅用）' },
    { food_id: 'cfcd:beef_fat', name: '牛肉（肥瘦）' },
    { food_id: 'dish:pickled_fish', name: '酸菜鱼' },
  ],
  review_reasons: ['needs_confirmation', 'estimated_grams'],
})

export function evaluation(over: Partial<PhotoEvaluationOut> = {}): PhotoEvaluationOut {
  return {
    conclusion: 'not_recommended',
    unchecked_items: ['酸汤肥牛'],
    unchecked_notice: UNCHECKED_NOTICE,
    items: [
      { item_id: 'item-rice', food_name: '杂粮饭', conclusion: 'suitable', reasons: [], tradeoff: '' },
      {
        item_id: 'item-fish', food_name: '鲈鱼（蒸）', conclusion: 'suitable', tradeoff: '',
        reasons: [{ source: 'goal', effect: 'prefer', code: 'goal_protein', message: '补足今天还差的蛋白质', ref: 'lose_fat' }],
      },
      {
        item_id: 'item-liver', food_name: '猪肝（卤）', conclusion: 'not_recommended', tradeoff: '',
        reasons: [
          { source: 'medical', effect: 'block', code: 'medical_avoid', message: '避免动物内脏与浓肉汤（高嘌呤）', ref: 'item-1' },
          {
            source: 'intake', effect: 'caution', code: 'intake_sodium',
            message: '加上这一餐，今天的钠预计 2,652 毫克，超过上限 2,000 毫克', ref: 'sodium_mg',
          },
        ],
      },
    ],
    disclaimer: ENGINE_DISCLAIMER,
    ...over,
  }
}

export function recognition(over: Partial<RecognitionOut> = {}): RecognitionOut {
  return {
    id: REC_ID,
    status: 'draft',
    items: [rice(), fish(), liver(), beef()],
    totals: nutrients({ energy_kcal: 567, protein_g: 61.4, fat_g: 14.2, carbohydrate_g: 70.1, sodium_mg: 1012 }),
    needs_review: true,
    disclaimer: PHOTO_DISCLAIMER,
    image_kept: false,
    model_id: 'qwen-vl-max',
    eaten_on: null,
    meal_type: null,
    meal_entry_ids: null,
    created_at: '2026-10-12T10:52:00Z',
    updated_at: '2026-10-12T10:52:00Z',
    evaluation: evaluation(),
    ...over,
  }
}
