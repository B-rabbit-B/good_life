import { Link } from 'react-router'
import type { MealOut, SummaryOut } from '../../api/types'
import { PATHS } from '../../app/paths'
import { buttonClassName } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { Sensitive } from '../../components/Sensitive'
import { PHOTO_MEAL_NOTE } from '../../lib/contract'
import { formatTime } from '../../lib/dates'
import { fmtNum } from '../../lib/format'
import { MEAL_LABELS } from '../../lib/labels'
import { MEAL_ORDER, recordedMeals } from './Ledger'

/**
 * 三餐（设计稿 05）：按餐次分组，写餐名、这一餐第一条的时间、这一餐的千卡（汇总里的数），每项“食物名 克数 克”与千卡；
 * 来自拍照识别的一餐下面加胶囊。没记的餐每餐一行，右边是拍照与“手动记一餐”（这一块不在敏感区里）。
 */
export function MealList({ summary, meals, date }: { summary: SummaryOut; meals: MealOut[]; date: string }) {
  const recorded = recordedMeals(meals)
  const missing = MEAL_ORDER.filter((type) => !recorded.includes(type))
  return (
    <>
      <Sensitive area="meals" className="plate">
        <ul className="meals" aria-label="这天的饮食记录">
          {recorded.map((type) => {
            const entries = meals.filter((meal) => meal.meal_type === type)
            const first = entries[0]
            return (
              <li key={type} className="meal">
                <div className="meal-h">
                  <b>{MEAL_LABELS[type]}{first && <small>{formatTime(first.created_at)}</small>}</b>
                  <span className="ns">{fmtNum(summary.meals[type]?.energy_kcal ?? 0, 1)}</span>
                </div>
                <ul>
                  {entries.map((entry) => (
                    <li key={entry.id}>
                      <span>{entry.food_name} {fmtNum(entry.grams, 1)} 克</span>
                      <span className="n">{entry.nutrients.energy_kcal == null ? '—' : fmtNum(entry.nutrients.energy_kcal, 1)}</span>
                    </li>
                  ))}
                </ul>
                {entries.some((entry) => entry.note === PHOTO_MEAL_NOTE) && <span className="from">来自拍照识别</span>}
              </li>
            )
          })}
        </ul>
      </Sensitive>
      {missing.length > 0 && (
        <div className="plate">
          <ul className="meals" aria-label="没记的餐">
            {missing.map((type) => (
              <li key={type} className="meal empty">
                <b>{MEAL_LABELS[type]}</b>
                <span className="acts">
                  <Link className="ibtn" to={PATHS.photoNew} aria-label={`拍照记录${MEAL_LABELS[type]}`}>
                    <Icon name="camera" />
                  </Link>
                  <Link className={buttonClassName({ variant: 'text' })} to={`${PATHS.mealNew}?date=${date}&meal=${type}`}>
                    手动记一餐
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
