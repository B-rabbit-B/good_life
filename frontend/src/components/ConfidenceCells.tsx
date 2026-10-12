import { LOW_CONFIDENCE } from '../lib/contract'
import { CONFIDENCE_LABELS } from '../lib/labels'
import '../styles/components/conf.css'

// 不低于 0.85 为高（DESIGN.md 第二节“把握程度”）；低于后端“把握较低”的阈值 LOW_CONFIDENCE 为低
const HIGH = 0.85
const CELLS = 5

/** 把握程度：五格（亮格数 max(1, round(value × 5))）加“高、中、低”，读屏读出两位小数。 */
export function ConfidenceCells({ value }: { value: number }) {
  const lit = Math.max(1, Math.round(value * CELLS))
  const word = CONFIDENCE_LABELS[value >= HIGH ? 'high' : value < LOW_CONFIDENCE ? 'low' : 'medium']
  return (
    <span className="conf" role="img" aria-label={`把握程度 ${value.toFixed(2)}，${word}`}>
      把握
      <i className="cells" aria-hidden="true">
        {Array.from({ length: CELLS }, (_, i) => <b key={i} className={i < lit ? 'on' : undefined} />)}
      </i>
      {word}
    </span>
  )
}
