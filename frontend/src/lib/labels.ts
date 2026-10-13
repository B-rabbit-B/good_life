// 枚举到中文的标签映射（流程文案，不含业务判断）。类型都是 Record<枚举, string>，漏写一项 TypeScript 会报错；
// 枚举尽量取自生成的接口类型，后端加了取值时这里跟着报错。
import type { components } from '../api/schema'
import type { TitleKey } from './titles'
import type { ReviewReasonCode, RiskCategory } from './contract'

type S = components['schemas']
type NonNull<T> = Exclude<T, null | undefined>

export type MealType = S['MealOut']['meal_type']
export type Conclusion = S['ItemEvaluationOut']['conclusion'] | 'unchecked'
export type ItemCategory = S['app__medical__schemas__ItemOut']['category']
export type ItemStatus = S['app__medical__schemas__ItemOut']['status']
export type EventAction =
  | 'created' | 'confirmed' | 'edited' | 'voided' | 'expired' | 'continued'
  | 'review_due' | 'resolution_proposed' | 'resolution_proposal_cancelled' | 'resolved'
export type EventSource = S['EventOut']['source']
export type ItemConfidence = NonNull<S['app__medical__schemas__ItemOut']['confidence']>
export type ActivityLevel = NonNull<S['ProfileOut']['activity_level']>
export type Goal = NonNull<S['ProfileOut']['goal']>
export type Gender = NonNull<S['ProfileOut']['gender']>
export type Flow = NonNull<S['DayLogIn']['flow']>
export type Mood = NonNull<S['DayLogIn']['mood']>
export type Phase = S['PhaseOut']['phase']
export type Muscle = S['ExerciseSummaryOut']['primary_muscles'][number]
export type Equipment = S['ExerciseSummaryOut']['equipment']
export type GrantAccess = S['GrantOut']['access']
export type GrantStatus = S['GrantOut']['status']
export type AuditOutcome = 'ok' | 'error'
export type Purpose = S['AssignmentOut']['purpose']
export type ProviderKind = S['ProviderOut']['kind']
export type ModelCapability = keyof S['CapabilitiesOut']

export const MEAL_LABELS: Record<MealType, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }

export const CONCLUSION_LABELS: Record<Conclusion, string> = {
  suitable: '适合', caution: '注意', not_recommended: '不建议', unchecked: '未核对',
}

export const CATEGORY_LABELS: Record<ItemCategory, string> = {
  diet_avoid: '饮食禁忌',
  diet_require: '饮食要求',
  medication_diet: '用药相关饮食注意',
  exercise_limit: '运动限制',
  other: '其他',
}

// 条目状态、审计动作与来源的标签只有医嘱页用，在 medicalLabels.ts（这个文件在对话页首屏的块里）

export const CONFIDENCE_LABELS: Record<ItemConfidence, string> = { high: '高', medium: '中', low: '低' }

export const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  sedentary: '久坐', light: '轻度', moderate: '中度', active: '活跃', very_active: '非常活跃',
}
export const ACTIVITY_HINTS: Record<ActivityLevel, string> = {
  sedentary: '几乎不运动',
  light: '每周运动 1 到 3 次',
  moderate: '每周运动 3 到 5 次',
  active: '每周运动 6 到 7 次',
  very_active: '体力劳动或每天高强度训练',
}

export const GOAL_LABELS: Record<Goal, string> = { lose_fat: '减脂', gain_muscle: '增肌', maintain: '维持', none: '不设' }

export const GENDER_LABELS: Record<Gender, string> = { female: '女', male: '男', other: '其他' }

export const FLOW_LABELS: Record<Flow, string> = { none: '无', spotting: '点滴', light: '少', medium: '中', heavy: '多' }

export const MOOD_LABELS: Record<Mood, string> = { good: '好', normal: '一般', low: '低落', irritable: '烦躁', anxious: '焦虑' }

/** 经期阶段的宋体标题键（lib/titles.json） */
export const PHASE_TITLE_KEYS: Record<Phase, TitleKey> = {
  menstrual: 'phaseMenstrual',
  follicular: 'phaseFollicular',
  ovulation: 'phaseOvulation',
  luteal: 'phaseLuteal',
  unknown: 'phaseUnknown',
}

export const MUSCLE_LABELS: Record<Muscle, string> = {
  chest: '胸',
  back: '背',
  shoulders: '肩',
  biceps: '肱二头肌',
  triceps: '肱三头肌',
  quads: '股四头肌',
  hamstrings: '腘绳肌',
  glutes: '臀',
  calves: '小腿',
  core: '核心',
  full_body: '全身',
}

export const EQUIPMENT_LABELS: Record<Equipment, string> = {
  barbell: '杠铃',
  dumbbell: '哑铃',
  machine: '器械',
  cable: '绳索',
  bodyweight: '徒手',
  kettlebell: '壶铃',
  band: '弹力带',
  none: '无',
  other: '其他',
}

export const ACCESS_LABELS: Record<GrantAccess, string> = { read: '只读', read_write: '读写' }

export const GRANT_STATUS_LABELS: Record<GrantStatus, string> = { active: '有效', expired: '已过期', revoked: '已吊销' }

export const AUDIT_OUTCOME_LABELS: Record<AuditOutcome, string> = { ok: '成功', error: '失败' }

/** 只有应用内助手有中文名，其他客户端名原样显示（用 clientLabel） */
export const CLIENT_LABELS: Record<string, string> = { agent: '应用内助手' }
export const clientLabel = (name: string) => CLIENT_LABELS[name] ?? name

export const PURPOSE_LABELS: Record<Purpose, string> = { chat: '日常对话', vision: '看图识别' }

export const PROVIDER_KIND_LABELS: Record<ProviderKind, string> = {
  openai_compatible: 'OpenAI 兼容格式', anthropic: 'Anthropic', gemini: 'Gemini',
}

export const CAPABILITY_LABELS: Record<ModelCapability, string> = { vision: '看图', tools: '工具调用', chat: '对话' }

export const REVIEW_REASON_LABELS: Record<ReviewReasonCode, string> = {
  low_confidence: '把握较低，建议核对菜名',
  needs_confirmation: '没有匹配到营养库，不计入合计，请选择对应的食物、改名或删除',
  grams_out_of_range: '克数不在常见范围内，请核对',
  estimated_grams: '克数是估算的，建议核对',
}

/** 就医提示的宋体标题键 */
export const RISK_TITLE_KEYS: Record<RiskCategory, TitleKey> = {
  severe_symptom: 'careSevere',
  pregnancy: 'careSevere',
  self_harm: 'careSelfHarm',
  medication: 'careMedication',
  extreme_diet: 'careDiet',
}

/** 就医提示里可拨打的电话 */
export const RISK_PHONES: Record<RiskCategory, ('120' | '12356')[]> = {
  severe_symptom: ['120'],
  pregnancy: ['120'],
  self_harm: ['120', '12356'],
  medication: ['120'],
  extreme_diet: ['120', '12356'],
}
