import { CountUp } from '../../components/CountUp'
import { LedgerTicks, type LedgerSegment } from '../../components/LedgerTicks'
import { RefTag } from '../../components/RefTag'
import { Sensitive } from '../../components/Sensitive'
import type { MealOut, SummaryOut } from '../../api/types'
import { formatMonthDay, todayISO } from '../../lib/dates'
import { fmtInt, fmtNum } from '../../lib/format'
import { MEAL_LABELS, type MealType } from '../../lib/labels'

export const MEAL_ORDER: MealType[] = ['breakfast', 'lunch', 'dinner', 'snack']

// 千卡与后端一样保留一位小数（整数不写 .0），计数过程中的每一帧也这样写
const kcalFormat = (n: number) => fmtNum(n, 1)

/** 这一天有记录的餐次（按早、午、晚、加餐的顺序） */
export function recordedMeals(meals: MealOut[]): MealType[] {
  return MEAL_ORDER.filter((type) => meals.some((meal) => meal.meal_type === type))
}

/**
 * 能量账本（设计稿 05）：大数是当天摄入 / 需要，右边“还可摄入”；刻度每格 25 千卡，
 * 段按早、午、晚、加餐的顺序只取有记录的餐，颜色按出现顺序 1 至 4；图例四格，没记的餐写“未记”；
 * 下面“仅供参考”与需求说明原文。数字全部来自后端的汇总。
 */
export function Ledger({ summary, meals, date }: { summary: SummaryOut; meals: MealOut[]; date: string }) {
  const kcal = (type: MealType) => summary.meals[type]?.energy_kcal ?? 0
  const recorded = recordedMeals(meals)
  const missing = MEAL_ORDER.filter((type) => !recorded.includes(type))
  const segments: LedgerSegment[] = recorded.map((type, i) => ({ kcal: kcal(type), tone: (i + 1) as LedgerSegment['tone'] }))
  const total = summary.total.energy_kcal ?? 0
  const need = summary.needs.energy_kcal
  const remaining = summary.remaining?.energy_kcal
  const day = date === todayISO() ? '今日' : formatMonthDay(date)
  const label = `${day}能量：${recorded.map((type) => `${MEAL_LABELS[type]} ${fmtNum(kcal(type), 1)}`).join('，')}，`
    + `共 ${fmtNum(total, 1)} 千卡${need === null ? '' : `；需要 ${fmtInt(need)} 千卡`}`
  return (
    <Sensitive area="ledger" className="plate ledger">
      <div className="ledger-figs">
        <div className="ledger-big">
          <span className="ns"><CountUp value={total} format={kcalFormat} /></span>
          {need !== null && <span>/ <span className="ns">{fmtInt(need)}</span> 千卡</span>}
        </div>
        {remaining !== undefined && (
          <div className="ledger-rem">还可摄入<span className="ns"><CountUp value={remaining} format={kcalFormat} /></span></div>
        )}
      </div>
      <LedgerTicks segments={segments} need={need} label={label} />
      <div className="legend">
        {recorded.map((type, i) => (
          <div key={type}><i className={`t${i + 1}`} />{MEAL_LABELS[type]}<span className="ns">{fmtNum(kcal(type), 1)}</span></div>
        ))}
        {missing.map((type) => <div key={type}><i />{MEAL_LABELS[type]}<span className="none">未记</span></div>)}
      </div>
      <p className="t-cap ledger-note">
        <RefTag />
        {summary.needs.notes.map((note) => <span key={note}>{note}</span>)}
      </p>
    </Sensitive>
  )
}
