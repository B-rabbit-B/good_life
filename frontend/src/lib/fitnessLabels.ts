// 训练的标签映射（只有记一次训练用，放在 labels.ts 会进对话页首屏的块）。枚举类型在 labels.ts，取自生成的接口类型。
import type { Equipment, Muscle } from './labels'

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
