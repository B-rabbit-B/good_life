// 手动记一餐：搜索食物（后端的提示原文显示，例如名称相近时的说明），结果是账目行；选中后按克数，
// 或按这种食物的常用份量（单位加份数）填写；日期默认查询参数或今天、餐次默认查询参数或按时间的默认值；
// 操作坞“保存”，成功后回到那一天的饮食记录并轻提示“已记下”。
import { useEffect, useId, useRef, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { useNavigate } from 'react-router'
import { ApiError } from '../../api/errors'
import { useCreateMeal, useFood, useFoodSearch, type MealInput } from '../../api/hooks/nutrition'
import { Button } from '../../components/Button'
import { DateField } from '../../components/DateField'
import { Dock } from '../../components/Dock'
import { Icon } from '../../components/Icon'
import { PageHeader } from '../../components/PageHeader'
import { RadioSegment } from '../../components/RadioSegment'
import { SelectField } from '../../components/SelectField'
import { TextField } from '../../components/TextField'
import { Title } from '../../components/Title'
import { useToast } from '../../components/Toast'
import { defaultMealType, todayISO } from '../../lib/dates'
import { MEAL_LABELS, type MealType } from '../../lib/labels'
import '../../styles/components/meals.css'
import { useSingleFlight } from '../../lib/singleFlight'
import { errorsOf } from '../../lib/formErrors'
import { useQueryParams } from '../../lib/queryParams'

const DATE = /^\d{4}-\d{2}-\d{2}$/
const SEARCH_DELAY_MS = 250
const MEAL_TYPES = Object.keys(MEAL_LABELS) as MealType[]
const MEAL_OPTIONS = MEAL_TYPES.map((value) => ({ value, label: MEAL_LABELS[value] }))
const MODE_OPTIONS = [{ value: 'grams', label: '按克数' }, { value: 'portion', label: '按份量' }]

/** 填的数字：有限的数字发数字，否则原样发出，让后端给出说明 */
const numberOrText = (text: string) => {
  const trimmed = text.trim()
  const value = Number(trimmed)
  return trimmed !== '' && Number.isFinite(value) ? value : trimmed
}

/** 输入停下 250 毫秒后才搜索 */
function useDebounced(value: string): string {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [value])
  return settled
}

export default function MealNewPage() {
  const [params] = useQueryParams()
  const navigate = useNavigate()
  const toast = useToast()
  const amountId = useId()
  const [text, setText] = useState('')
  const q = useDebounced(text.trim())
  const search = useFoodSearch(q)
  const [picked, setPicked] = useState<{ id: string; name: string } | null>(null)
  const food = useFood(picked?.id ?? null)
  const [mode, setMode] = useState<'grams' | 'portion'>('grams')
  const [grams, setGrams] = useState('')
  const [unit, setUnit] = useState('')
  const [count, setCount] = useState('1')
  const dateParam = params.get('date') ?? ''
  const mealParam = params.get('meal') ?? ''
  const [date, setDate] = useState(DATE.test(dateParam) ? dateParam : todayISO())
  const [meal, setMeal] = useState<MealType>(
    (MEAL_TYPES as string[]).includes(mealParam) ? (mealParam as MealType) : defaultMealType(new Date()),
  )
  const create = useCreateMeal()
  // 双击“保存”时 isPending 还没渲染出来：用锁保证只记一次
  const flight = useSingleFlight()
  const saved = useRef(false) // 记下之后、离开这一页之前不再保存
  const errors = errorsOf(create.error)
  const portions = food.data?.portions ?? []
  const byPortion = mode === 'portion' && portions.length > 0
  const unitValue = unit || portions[0]?.unit || ''

  const choose = (id: string, name: string) => {
    setPicked({ id, name })
    setUnit('')
    create.reset()
  }

  const save = () => {
    if (!picked) return
    const body: MealInput = byPortion
      ? { eaten_on: date, meal_type: meal, food_id: picked.id, portion: { unit: unitValue, count: numberOrText(count) } }
      : { eaten_on: date, meal_type: meal, food_id: picked.id, grams: numberOrText(grams) }
    if (saved.current) return
    flight(() => create.mutateAsync(body))?.then(() => {
      saved.current = true
      toast.show('已记下')
      void navigate(`/records?tab=diet&date=${date}`)
    }, () => undefined) // 错误由 create.error 显示
  }

  const results = search.data?.results ?? []
  const shownErrors = new Set(['grams', 'count'])
  const formError = Object.entries(errors).find(([key]) => !shownErrors.has(key))?.[1]
  return (
    <>
      <PageHeader titleKey="mealNew" variant="sub" back />
      <div className="plate food-q">
        <TextField label="搜索食物" type="search" value={text} onChange={setText} maxLength={50} />
        {search.data?.message && <p className="food-msg">{search.data.message}</p>}
        {search.isError && <p className="food-msg">{search.error.message}</p>}
        {results.length > 0 && (
          <ul className="foods" aria-label="搜索结果">
            {results.map((result) => (
              <li key={result.id}>
                <AriaButton
                  className="food-row" aria-pressed={picked?.id === result.id}
                  onPress={() => choose(result.id, result.name)}
                >
                  <span>{result.name}</span>
                  <span className="t-cap">{result.category}</span>
                </AriaButton>
              </li>
            ))}
          </ul>
        )}
        {picked && <p className="food-picked">已选：{picked.name}</p>}
      </div>
      {picked && (
        <section className="plate meal-amount" aria-labelledby={amountId}>
          <h2 id={amountId} className="sr-only">吃了多少</h2>
          {portions.length > 0 && (
            <RadioSegment label="记录方式" options={MODE_OPTIONS} value={mode} onChange={(value) => setMode(value as 'grams' | 'portion')} />
          )}
          {byPortion
            ? (
              <div className="mn-pair">
                <SelectField
                  label="单位" value={unitValue} onChange={setUnit}
                  options={portions.map((portion) => ({ value: portion.unit, label: `${portion.unit}（约 ${portion.grams} 克）` }))}
                />
                <TextField label="份数" value={count} onChange={setCount} inputMode="decimal" error={errors.count} />
              </div>
            )
            : <TextField label="克数" value={grams} onChange={setGrams} inputMode="decimal" suffix="克" error={errors.grams} />}
        </section>
      )}
      <section className="plate mn-when" aria-labelledby={`${amountId}-when`}>
        <Title k="mealWhen" level="h" id={`${amountId}-when`} />
        <div className="mn-pair">
          <DateField label="日期" value={date} max={todayISO()} onChange={(value) => setDate(value ?? todayISO())} />
          <SelectField label="餐次" value={meal} options={MEAL_OPTIONS} onChange={(value) => setMeal(value as MealType)} />
        </div>
        {formError && (
          <div className="err" role="alert">
            <Icon name="alert" size={18} />
            <span>{formError}{create.error instanceof ApiError && <small>错误码 {create.error.code}</small>}</span>
          </div>
        )}
      </section>
      <Dock>
        <Button variant="primary" block isDisabled={!picked} isPending={create.isPending} onPress={save}>保存</Button>
      </Dock>
    </>
  )
}
