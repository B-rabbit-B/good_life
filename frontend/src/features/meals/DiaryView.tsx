import { Button as AriaButton } from 'react-aria-components'
import { Link } from 'react-router'
import { networkError } from '../../api/client'
import { ApiError } from '../../api/errors'
import { useMeals, useSummary } from '../../api/hooks/nutrition'
import { PATHS } from '../../app/paths'
import { buttonClassName } from '../../components/Button'
import { ButtonLink } from '../../components/ButtonLink'
import { Icon } from '../../components/Icon'
import { EmptyState } from '../../components/states/EmptyState'
import { ErrorState } from '../../components/states/ErrorState'
import { InsufficientState } from '../../components/states/InsufficientState'
import { LoadingState } from '../../components/states/LoadingState'
import { addDays, formatMonthDay, formatWeekday, todayISO } from '../../lib/dates'
import '../../styles/components/meals.css'
import { Ledger } from './Ledger'
import { MealList } from './MealList'
import { NutrientTable } from './NutrientTable'
import { useQueryParams } from './queryParams'

function DateBar({ date, onChange }: { date: string; onChange: (date: string) => void }) {
  const today = todayISO()
  return (
    <div className="datebar">
      <AriaButton className="ibtn" aria-label="前一天" onPress={() => onChange(addDays(date, -1))}>
        <Icon name="back" />
      </AriaButton>
      <b>{formatMonthDay(date)}<small>{date === today ? '今天' : formatWeekday(date)}</small></b>
      <AriaButton className="ibtn" aria-label="后一天" isDisabled={date >= today} onPress={() => onChange(addDays(date, 1))}>
        <Icon name="right" />
      </AriaButton>
    </div>
  )
}

/**
 * 饮食记录的一天（设计稿 05）：日期条（今天之后不可用）；能量账本（档案不全时换成“数据不足”，正文是后端的说明）、
 * 营养表、三餐；当天完全没有记录时是“无数据”；最后是背景场上的“附近吃什么”。
 */
export function DiaryView({ date }: { date: string }) {
  const [, setParams] = useQueryParams()
  const summary = useSummary(date)
  const meals = useMeals(date)
  const go = (next: string) => setParams({ tab: 'diet', date: next })

  let body
  if (summary.data && meals.data) {
    const day = summary.data
    if (meals.data.length === 0) {
      body = (
        <div className="plate">
          <EmptyState
            titleKey="emptyDiary"
            body={`${formatMonthDay(date)} 还没有记录。拍一张饭菜，或者手动记一餐。补记的记录会算进那一天。`}
            actions={(
              <>
                <ButtonLink to={PATHS.photoNew} variant="primary"><Icon name="camera" size={18} />拍照记录</ButtonLink>
                <ButtonLink to={`${PATHS.mealNew}?date=${date}`} variant="quiet">手动记一餐</ButtonLink>
              </>
            )}
          />
        </div>
      )
    } else {
      body = (
        <>
          {day.needs.status === 'insufficient_profile'
            ? (
              <div className="plate">
                <InsufficientState
                  titleKey="needsProfile" notes={day.needs.notes}
                  actions={<ButtonLink to={PATHS.profileEdit} variant="quiet">去补充档案</ButtonLink>}
                />
              </div>
            )
            : <Ledger summary={day} meals={meals.data} date={date} />}
          <NutrientTable summary={day} />
          <MealList summary={day} meals={meals.data} date={date} />
        </>
      )
    }
  } else if ((summary.isError && !summary.data) || (meals.isError && !meals.data)) {
    const failed = summary.isError ? summary.error : meals.error
    body = (
      <div className="plate">
        <ErrorState
          error={failed instanceof ApiError ? failed : networkError()}
          onRetry={() => {
            void summary.refetch()
            void meals.refetch()
          }}
        />
      </div>
    )
  } else {
    body = <LoadingState variant="diary" text="正在读取这天的记录" />
  }

  return (
    <>
      <DateBar date={date} onChange={go} />
      {body}
      <div className="diary-near">
        <Link className={buttonClassName({ variant: 'text', onField: true })} to={PATHS.restaurants}>附近吃什么</Link>
      </div>
    </>
  )
}
