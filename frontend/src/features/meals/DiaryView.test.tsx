import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { addDays, formatMonthDay, todayISO } from '../../lib/dates'
import {
  dayMeals, ESTIMATE_NOTE, INSUFFICIENT_NOTE, insufficientSummary, MINOR_NOTE, minorSummary, summary, SUMMARY_DISCLAIMER,
} from '../../test/fixtures/nutrition'
import { nutritionHandlers, type NutritionOptions } from '../../test/msw/handlers/nutrition'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()

function renderDiary(opts: NutritionOptions = { summaries: { [today]: summary() }, meals: { [today]: dayMeals() } }, path = '/records') {
  const result = renderRoute(path)
  const nutrition = nutritionHandlers(opts)
  server.use(...nutrition.handlers)
  return { ...result, nutrition }
}

describe('diary view', () => {
  it('offers the nearby restaurants entry', async () => {
    renderDiary()
    const link = await screen.findByRole('link', { name: '附近吃什么' })
    expect(link).toHaveAttribute('href', '/restaurants')
    expect(link).toHaveClass('on-field')
  })

  it('shows the ledger with need and remaining from the summary', async () => {
    renderDiary()
    const ledger = await screen.findByRole('img', { name: /今日能量/ })
    expect(ledger).toHaveAccessibleName('今日能量：早餐 412，午餐 515，加餐 158，共 1,085 千卡；需要 1,850 千卡')
    // 25 千卡一格：max(1085, 1850) / 25 = 74 格；三餐按出现顺序用 1、2、3 号颜色
    expect(ledger.querySelectorAll('.lt-ticks i')).toHaveLength(74)
    expect(ledger.querySelectorAll('.lt-ticks i.s1')).toHaveLength(Math.round(412 / 25))
    const figures = document.querySelector('.ledger-figs') as HTMLElement
    expect(figures).toHaveTextContent('1,085/ 1,850 千卡')
    expect(figures).toHaveTextContent('还可摄入765')
    const legend = document.querySelector('.legend') as HTMLElement
    expect(Array.from(legend.children).map((cell) => cell.textContent)).toEqual(['早餐412', '午餐515', '加餐158', '晚餐未记'])
    expect(screen.getByText(SUMMARY_DISCLAIMER)).toBeInTheDocument()
  })

  it('shows the nutrient table with needs, what is left and the sodium limit', async () => {
    renderDiary({
      summaries: { [today]: summary({ incomplete_fields: ['fiber_g', 'sodium_mg'], remaining: { energy_kcal: 765, protein_g: 17.6, sodium_mg: -40 } }) },
      meals: { [today]: dayMeals() },
    })
    const table = await screen.findByRole('table', { name: '营养素' })
    const rows = within(table).getAllByRole('row').slice(1).map((row) => row.textContent)
    expect(rows).toEqual([
      '蛋白质52.4克7017.6', '脂肪38.1克41–62—', '碳水化合物128.0克231–301—', '膳食纤维9.2克25–30—', '钠上限1,640毫克2,000-40',
    ])
    expect(within(table).getAllByRole('row').at(-1)).toHaveClass('warn')
    expect(screen.getByText('部分食物缺少 膳食纤维、钠 的数据，合计可能偏低')).toBeInTheDocument()
  })

  it('shows needs notes beside a reference tag', async () => {
    renderDiary()
    const note = await screen.findByText(ESTIMATE_NOTE)
    expect(within(note.closest('.ledger-note') as HTMLElement).getByText('仅供参考')).toBeInTheDocument()
  })

  it('shows the insufficient profile state with the backend notes', async () => {
    renderDiary({ summaries: { [today]: insufficientSummary() }, meals: { [today]: dayMeals() } })
    const state = await screen.findByRole('region', { name: '还不能估算每日需要' })
    expect(within(state).getByText(INSUFFICIENT_NOTE)).toBeInTheDocument()
    expect(within(state).getByRole('link', { name: '去补充档案' })).toHaveAttribute('href', '/me/profile')
    expect(screen.queryByRole('img', { name: /今日能量/ })).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '营养素' })).toBeInTheDocument()
  })

  it('shows the minor needs notes without energy numbers', async () => {
    renderDiary({ summaries: { [today]: minorSummary() }, meals: { [today]: dayMeals() } })
    const state = await screen.findByRole('region', { name: '还不能估算每日需要' })
    expect(within(state).getByText(MINOR_NOTE)).toBeInTheDocument()
    // 补充档案也不会估算，所以不给“去补充档案”
    expect(within(state).queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /今日能量/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/1,850/)).not.toBeInTheDocument()
    const table = screen.getByRole('table', { name: '营养素' })
    const rows = within(table).getAllByRole('row').slice(1).map((row) => row.textContent)
    expect(rows).toEqual(['蛋白质52.4克——', '脂肪38.1克——', '碳水化合物128.0克——', '膳食纤维9.2克——', '钠上限1,640毫克——'])
  })

  it('shows the empty day state with actions', async () => {
    renderDiary({})
    const state = await screen.findByRole('region', { name: '这天没有饮食记录' })
    expect(state).toHaveTextContent(`${formatMonthDay(today)} 还没有记录。拍一张饭菜，或者手动记一餐。补记的记录会算进那一天。`)
    expect(within(state).getByRole('link', { name: '拍照记录' })).toHaveAttribute('href', '/photos/new')
    expect(within(state).getByRole('link', { name: '手动记一餐' })).toHaveAttribute('href', `/records/meals/new?date=${today}`)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('marks meals that came from a photo', async () => {
    renderDiary()
    const meals = await screen.findByRole('list', { name: '这天的饮食记录' })
    const groups = within(meals).getAllByRole('listitem').filter((el) => el.classList.contains('meal'))
    expect(groups.map((group) => group.querySelector('.meal-h b')?.textContent)).toEqual(['早餐07:40', '午餐12:20', '加餐15:30'])
    expect(groups[1]).toHaveTextContent('来自拍照识别')
    expect(groups[0]).not.toHaveTextContent('来自拍照识别')
    expect(groups[0]).toHaveTextContent('燕麦牛奶粥 300 克186')
    expect(groups[0]?.querySelector('.meal-h .ns')).toHaveTextContent('412')
    // 没记的餐：拍照与手动记一餐
    const dinner = screen.getByText('晚餐', { selector: '.meal.empty b' }).closest('.meal') as HTMLElement
    expect(within(dinner).getByRole('link', { name: '拍照记录晚餐' })).toHaveAttribute('href', '/photos/new')
    expect(within(dinner).getByRole('link', { name: '手动记一餐' }))
      .toHaveAttribute('href', `/records/meals/new?date=${today}&meal=dinner`)
  })

  it('wraps the ledger, the table and the meals in sensitive regions', async () => {
    renderDiary()
    await screen.findByRole('img', { name: /今日能量/ })
    expect(sensitiveAreaMismatch(document, ['ledger', 'nutrients', 'meals']))
      .toEqual({ page: 'records', missing: [], unexpected: [] })
  })

  it('disables the next day after today', async () => {
    const user = userEvent.setup()
    const { router, nutrition } = renderDiary()
    const next = await screen.findByRole('button', { name: '后一天' })
    expect(next).toBeDisabled()
    expect(screen.getByText('今天')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '前一天' }))
    const yesterday = addDays(today, -1)
    await waitFor(() => expect(router.state.location.search).toBe(`?tab=diet&date=${yesterday}`))
    await waitFor(() => expect(nutrition.summaryDates).toContain(yesterday))
    expect(screen.getByRole('button', { name: '后一天' })).toBeEnabled()
  })

  it('shows a loading skeleton then a retryable error', async () => {
    const user = userEvent.setup()
    renderDiary({ summaryError: { status: 500, code: 'internal_error', message: '服务出了点问题，请稍后再试' } })
    expect(await screen.findByText('正在读取这天的记录')).toHaveAttribute('role', 'status')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务出了点问题，请稍后再试')
    expect(alert).toHaveTextContent('错误码 internal_error')
    server.use(...nutritionHandlers({ summaries: { [today]: summary() }, meals: { [today]: dayMeals() } }).handlers)
    await user.click(within(alert).getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('img', { name: /今日能量/ })).toBeInTheDocument()
  })

  it('shows the training view on the training tab', async () => {
    renderDiary(undefined, '/records?tab=training')
    expect(await screen.findByRole('tab', { name: '训练', selected: true })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '本周训练' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '附近吃什么' })).not.toBeInTheDocument()
  })

  it('hides the segments when only the diet module is open', async () => {
    renderRoute('/records', { capabilities: { fitness: false } })
    server.use(...nutritionHandlers().handlers)
    expect(await screen.findByRole('heading', { name: '记录', level: 1 })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: '附近吃什么' })).toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  })
})
