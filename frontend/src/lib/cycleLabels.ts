// 经期页的标签映射（只有经期页用，放在 labels.ts 会进对话页首屏的块）。枚举类型在 labels.ts，取自生成的接口类型。
import type { Flow, Mood, Phase } from './labels'
import type { TitleKey } from './titles'

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
