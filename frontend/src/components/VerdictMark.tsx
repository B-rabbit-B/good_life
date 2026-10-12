import '../styles/components/verdict.css'

export type Conclusion = 'suitable' | 'caution' | 'not_recommended' | 'unchecked'

const SHAPE: Record<Conclusion, string> = {
  suitable: 'vd-ok',
  caution: 'vd-warn',
  not_recommended: 'vd-no',
  unchecked: 'vd-un',
}

// 任务 4 改为引用 lib/labels.ts 的 CONCLUSION_LABELS
const DEFAULT_LABELS: Record<Conclusion, string> = {
  suitable: '适合',
  caution: '注意',
  not_recommended: '不建议',
  unchecked: '未核对',
}

/** 结论标记：颜色加形状（实心、半填、叉形、虚线方块），文字默认取结论的中文名。 */
export function VerdictMark({ conclusion, label }: { conclusion: Conclusion; label?: string }) {
  return <span className={`vd ${SHAPE[conclusion]}`}>{label ?? DEFAULT_LABELS[conclusion]}</span>
}
