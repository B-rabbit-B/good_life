import { CONCLUSION_LABELS, type Conclusion } from '../lib/labels'
import '../styles/components/verdict.css'

export type { Conclusion }

const SHAPE: Record<Conclusion, string> = {
  suitable: 'vd-ok',
  caution: 'vd-warn',
  not_recommended: 'vd-no',
  unchecked: 'vd-un',
}

/** 结论标记：颜色加形状（实心、半填、叉形、虚线方块），文字默认取 CONCLUSION_LABELS 里结论的中文名。 */
export function VerdictMark({ conclusion, label }: { conclusion: Conclusion; label?: string }) {
  return <span className={`vd ${SHAPE[conclusion]}`}>{label ?? CONCLUSION_LABELS[conclusion]}</span>
}
