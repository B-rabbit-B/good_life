import '../styles/components/conf.css'

const HIGH = 0.85
// 与后端“把握较低”的阈值一致；任务 4 改为引用 lib/contract.ts 的 LOW_CONFIDENCE
const LOW = 0.6
const CELLS = 5

/** 把握程度：五格（亮格数 max(1, round(value × 5))）加“高、中、低”，读屏读出两位小数。 */
export function ConfidenceCells({ value }: { value: number }) {
  const lit = Math.max(1, Math.round(value * CELLS))
  const word = value >= HIGH ? '高' : value < LOW ? '低' : '中'
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
