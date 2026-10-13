export interface RulerMarks {
  /** 每根刻度的左边位置（1.5 像素宽，已向左偏 0.75 让中心对齐），major 是大刻度 */
  ticks: { x: number; major: boolean }[]
  /** 大刻度的数字标签：x 是中心位置，只保留完整落在容器内的 */
  labels: { x: number; value: number }[]
}

const TICK_HALF = 0.75
const LABEL_HALF = 14
const EPSILON = 1e-6

/**
 * 刻度尺的计算（DESIGN.md 第六节）：中线 c = width / 2，可见范围 value ± c / ppu；
 * 值为 k 的刻度画在 x = c + (k − value) × ppu − 0.75；标签只取 x − 14 >= 0 且 x + 14 <= width 的大刻度。
 */
export function rulerMarks(width: number, value: number, step: number, major: number, ppu: number): RulerMarks {
  const c = width / 2
  const first = Math.ceil((value - c / ppu) / step - EPSILON)
  const last = Math.floor((value + c / ppu) / step + EPSILON)
  const ticks: RulerMarks['ticks'] = []
  const labels: RulerMarks['labels'] = []
  for (let n = first; n <= last; n += 1) {
    const k = Number((n * step).toFixed(6))
    const x = c + (k - value) * ppu
    const isMajor = Math.abs(k / major - Math.round(k / major)) < EPSILON
    ticks.push({ x: x - TICK_HALF, major: isMajor })
    if (isMajor && x - LABEL_HALF >= 0 && x + LABEL_HALF <= width) labels.push({ x, value: k })
  }
  return { ticks, labels }
}
