import type { CSSProperties } from 'react'
import type { NutrientsOut, SummaryOut } from '../../api/types'
import { Sensitive } from '../../components/Sensitive'
import { NUTRIENT_LABELS, nutrientRows } from './nutrientRows'

const fieldLabel = (field: string) => NUTRIENT_LABELS[field as keyof NutrientsOut] ?? field

/**
 * 营养表（设计稿 05）：五种营养素的已摄入、需要、还差，4 像素圆头进度条；钠写“上限”，还差不大于 0 时整行赭色。
 * 有食物缺数据时写明哪几项合计可能偏低；最后是汇总的免责句原文。
 */
export function NutrientTable({ summary }: { summary: SummaryOut }) {
  const rows = nutrientRows(summary)
  return (
    <Sensitive area="nutrients" className="plate">
      <table className="mt">
        <caption className="sr-only">营养素</caption>
        <thead>
          <tr><th scope="col">营养素</th><th scope="col">已摄入</th><th scope="col">需要</th><th scope="col">还差</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className={row.warn ? 'warn' : undefined}>
              <td>
                {row.label}
                {row.limit && <span className="t-cap lim">上限</span>}
                <span className="bar" style={{ '--w': `${row.fill * 100}%` } as CSSProperties} aria-hidden="true" />
              </td>
              <td>{row.intake}<small>{row.unit}</small></td>
              <td>{row.need}</td>
              <td>{row.remaining}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {summary.incomplete_fields.length > 0 && (
        <p className="t-cap mt-note">{`部分食物缺少 ${summary.incomplete_fields.map(fieldLabel).join('、')} 的数据，合计可能偏低`}</p>
      )}
      <p className="t-cap mt-note">{summary.disclaimer}</p>
    </Sensitive>
  )
}
