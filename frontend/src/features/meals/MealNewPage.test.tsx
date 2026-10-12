import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { addDays, todayISO } from '../../lib/dates'
import { PARTIAL_MATCH_MESSAGE, partialSearchResult, searchResult } from '../../test/fixtures/nutrition'
import { nutritionHandlers, type NutritionOptions } from '../../test/msw/handlers/nutrition'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()

function renderMealNew(path = '/records/meals/new', opts: NutritionOptions = {
  search: { 米饭: searchResult('米饭'), 饭: partialSearchResult('饭') },
}) {
  const result = renderRoute(path)
  const nutrition = nutritionHandlers(opts)
  server.use(...nutrition.handlers)
  return { ...result, nutrition }
}

async function chooseRice(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByRole('searchbox', { name: '搜索食物' }), '米饭')
  await user.click(await screen.findByRole('button', { name: /^米饭/ }))
  expect(await screen.findByText('已选：米饭')).toBeInTheDocument()
}

describe('meal new page', () => {
  it('searches and shows the backend message for partial matches', async () => {
    const user = userEvent.setup()
    renderMealNew()
    const search = await screen.findByRole('searchbox', { name: '搜索食物' })
    await user.type(search, '饭')
    expect(await screen.findByText(PARTIAL_MATCH_MESSAGE)).toBeInTheDocument()
    const results = screen.getByRole('list', { name: '搜索结果' })
    expect(within(results).getAllByRole('button').map((button) => button.textContent)).toEqual(['米饭谷类及制品', '蛋炒饭菜肴'])
    await user.clear(search)
    await user.type(search, '火星菜')
    expect(await screen.findByText('未找到与“火星菜”匹配的食物，请换个说法或检查错别字')).toBeInTheDocument()
  })

  it('saves by grams', async () => {
    const user = userEvent.setup()
    const { nutrition } = renderMealNew()
    await chooseRice(user)
    await user.selectOptions(screen.getByLabelText('餐次'), 'dinner')
    await user.type(screen.getByLabelText('克数'), '200')
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(nutrition.created).toHaveLength(1))
    expect(nutrition.created[0]).toEqual({ eaten_on: today, meal_type: 'dinner', food_id: 'cfcd:rice', grams: 200 })
  })

  it('saves by portion', async () => {
    const user = userEvent.setup()
    const { nutrition } = renderMealNew()
    await chooseRice(user)
    await user.selectOptions(screen.getByLabelText('餐次'), 'lunch')
    await user.click(await screen.findByRole('radio', { name: '按份量' }))
    expect(screen.getByLabelText('单位')).toHaveValue('碗')
    await user.selectOptions(screen.getByLabelText('单位'), '勺')
    await user.clear(screen.getByLabelText('份数'))
    await user.type(screen.getByLabelText('份数'), '1.5')
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(nutrition.created).toHaveLength(1))
    expect(nutrition.created[0]).toEqual({
      eaten_on: today, meal_type: 'lunch', food_id: 'cfcd:rice', portion: { unit: '勺', count: 1.5 },
    })
  })

  it('shows a backend error verbatim', async () => {
    const user = userEvent.setup()
    renderMealNew('/records/meals/new', {
      search: { 米饭: searchResult('米饭') },
      createError: { status: 422, code: 'invalid_portion', message: '克数需要大于 0 且不超过 5000' },
    })
    await chooseRice(user)
    await user.type(screen.getByLabelText('克数'), '9000')
    await user.click(screen.getByRole('button', { name: '保存' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('克数需要大于 0 且不超过 5000')
    expect(alert).toHaveTextContent('错误码 invalid_portion')
  })

  it('returns to the diary of that day', async () => {
    const user = userEvent.setup()
    const yesterday = addDays(today, -1)
    const { router, nutrition } = renderMealNew(`/records/meals/new?date=${yesterday}&meal=breakfast`)
    await chooseRice(user)
    expect(screen.getByLabelText('日期')).toHaveValue(yesterday)
    expect(screen.getByLabelText('餐次')).toHaveValue('breakfast')
    await user.type(screen.getByLabelText('克数'), '150')
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/records'))
    expect(router.state.location.search).toBe(`?tab=diet&date=${yesterday}`)
    expect(nutrition.created[0]).toMatchObject({ eaten_on: yesterday, meal_type: 'breakfast' })
    expect(await screen.findByText('已记下')).toBeInTheDocument()
  })
})
