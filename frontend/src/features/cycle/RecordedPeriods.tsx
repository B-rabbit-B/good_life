// “已记录的经期”：月历下方的面板（在经期页的敏感区里），按开始日期从近到远列出最近的经期，每行右侧一个“删除”。
// 日期写完整的年月日；还没结束的写“至 今”。没有记录时整块不显示。删除的确认在 DeletePeriodSheet（由经期页持有）。
import type { PeriodOut } from '../../api/types'
import { Button } from '../../components/Button'
import { addDays, formatFullDate as full } from '../../lib/dates'
import '../../styles/components/sec-head.css'

/** 最多列出的条数，更早的不列 */
export const MAX_LISTED_PERIODS = 12

function dayCount(start: string, end: string): number {
  let n = 1
  for (let date = start; date < end; date = addDays(date, 1)) n += 1
  return n
}

export function RecordedPeriods({ periods, onDelete }: { periods: PeriodOut[]; onDelete: (period: PeriodOut) => void }) {
  if (periods.length === 0) return null
  const sorted = [...periods].sort((a, b) => b.start_date.localeCompare(a.start_date))
  const shown = sorted.slice(0, MAX_LISTED_PERIODS)
  return (
    <section aria-labelledby="cyc-list-h">
      <div className="sec-h"><h2 className="sec-l" id="cyc-list-h">已记录的经期</h2></div>
      <div className="plate cyc-list">
        <ul>
          {shown.map((p) => (
            <li key={p.id}>
              <span>
                {full(p.start_date)} 至 {p.end_date ? `${full(p.end_date)}（共 ${dayCount(p.start_date, p.end_date)} 天）` : '今（还没结束）'}
              </span>
              <Button variant="text" aria-label={`删除 ${full(p.start_date)} 开始的经期`} onPress={() => onDelete(p)}>
                删除
              </Button>
            </li>
          ))}
        </ul>
        {sorted.length > shown.length && <p className="cyc-list-x">只列出最近 {MAX_LISTED_PERIODS} 次，更早的不在这里显示。</p>}
      </div>
    </section>
  )
}
