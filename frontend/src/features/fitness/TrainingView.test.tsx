import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, describe, expect, it } from 'vitest'
import type { ConstraintsOut } from '../../api/types'
import { addDays, formatMonthDay, mondayOf, todayISO } from '../../lib/dates'
import {
  benchTrend, cardioWorkout, KNEE_CONFLICT_MESSAGE, KNEE_LIMIT, MISSING_WEIGHT_NOTE, missingWeightSummary,
  recentWorkouts, strengthWorkout, weekSummary,
} from '../../test/fixtures/fitness'
import { fitnessHandlers, type FitnessOptions } from '../../test/msw/handlers/fitness'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()

function renderTraining(opts: FitnessOptions = {}, route: Parameters<typeof renderRoute>[1] = {}) {
  const result = renderRoute('/records?tab=training', route)
  const fitness = fitnessHandlers({ summary: weekSummary(today), workouts: recentWorkouts(today), ...opts })
  server.use(...fitness.handlers)
  return { ...result, fitness }
}

function limits(end: string | null): ConstraintsOut {
  return {
    reminder: '',
    constraints: [{
      item_id: '20000000-0000-4000-8000-000000000009', category: 'exercise_limit', content: KNEE_LIMIT, subjects: ['跳'],
      start_date: addDays(today, -20), end_date: end, review_date: null, status: 'active', needs_review: false,
      resolution_proposed: false,
    }],
  }
}

const rowOf = async (name: string) => (await screen.findByText(name, { selector: '.trw-h b' })).closest('.trw') as HTMLElement

beforeAll(async () => {
  await import('../meals/RecordsPage')
}, 60_000)

describe('training view', { timeout: 15_000 }, () => {
  it('shows the exercise limit as sensitive medical content', async () => {
    const categories: (string | null)[] = []
    renderTraining()
    const end = addDays(today, 5)
    server.use(http.get('/api/medical/constraints', ({ request }) => {
      categories.push(new URL(request.url).searchParams.get('category'))
      return HttpResponse.json(limits(end))
    }))
    const line = await screen.findByText(`运动限制生效中：${KNEE_LIMIT}，到 ${formatMonthDay(end)}`)
    const region = line.closest('[data-sensitive]')
    expect(region).toHaveAttribute('data-sensitive-area', 'constraints')
    expect(categories).toContain('exercise_limit')
    expect(document.body.textContent).not.toContain('删除')
  })

  it('leaves out the end date when the limit has none', async () => {
    renderTraining()
    server.use(http.get('/api/medical/constraints', () => HttpResponse.json(limits(null))))
    expect(await screen.findByText(`运动限制生效中：${KNEE_LIMIT}`)).toBeInTheDocument()
  })

  it('shows week figures with a reference tag on the energy estimate', async () => {
    renderTraining({
      workouts: [cardioWorkout(today, 'ex:brisk_walking', '快走', 35), strengthWorkout(today)],
    })
    const panel = (await screen.findByRole('heading', { name: '本周训练' })).closest('.wk') as HTMLElement
    const monday = mondayOf(today)
    expect(panel).toHaveTextContent(`${formatMonthDay(monday)} 至 ${formatMonthDay(addDays(monday, 6))}`)
    const figures = Array.from(panel.querySelectorAll('.wk-figs > div'))
    await waitFor(() => expect(figures[1]).toHaveTextContent('85分钟总时长'))
    expect(figures[0]).toHaveTextContent('4次训练')
    expect(figures[2]).toHaveTextContent('820–1,020千卡估算消耗')
    expect(within(figures[2] as HTMLElement).getByText('仅供参考')).toBeInTheDocument()
    const bars = within(panel).getByRole('img')
    expect(bars.getAttribute('aria-label')).toMatch(/^每日训练分钟：/)
    expect(bars.getAttribute('aria-label')).toContain('今天 85')
    expect(bars.querySelectorAll('.wk-col')).toHaveLength(7)
  })

  it('shows the missing body weight note verbatim', async () => {
    renderTraining({ summary: missingWeightSummary(today) })
    const panel = (await screen.findByRole('heading', { name: '本周训练' })).closest('.wk') as HTMLElement
    expect(await within(panel).findByText(MISSING_WEIGHT_NOTE)).toBeInTheDocument()
    expect(panel).not.toHaveTextContent('千卡')
  })

  it('shows conflicts on workout rows', async () => {
    renderTraining()
    const row = await rowOf('开合跳')
    const conflict = within(row).getByText(KNEE_CONFLICT_MESSAGE)
    expect(conflict.closest('.trw-x')).not.toBeNull()
    expect(conflict.closest('[data-sensitive]')).toHaveAttribute('data-sensitive-area', 'constraints')
    expect(row).toHaveTextContent('15 分钟')
    const strength = await rowOf('力量训练')
    expect(strength).toHaveTextContent('50 分钟')
    expect(strength).toHaveTextContent('哑铃卧推 4×10，12 千克')
    expect(strength).toHaveTextContent('腿屈伸 3×12，25 千克')
    expect(within(await rowOf('快走')).queryByText(KNEE_CONFLICT_MESSAGE)).not.toBeInTheDocument()
  })

  it('draws the trend of the latest strength exercise', async () => {
    const { fitness } = renderTraining({ trends: { 'ex:dumbbell_bench_press': benchTrend(today) } })
    const trend = (await screen.findByText('最大重量，近 6 次')).closest('.trend') as HTMLElement
    expect(trend).toHaveTextContent('哑铃卧推')
    expect(trend).toHaveTextContent('8 到 12 千克')
    expect(trend.querySelectorAll('circle')).toHaveLength(6)
    expect(trend.querySelectorAll('circle.last')).toHaveLength(1)
    expect(fitness.record.trendRequests).toEqual(['ex:dumbbell_bench_press'])
  })

  it('goes to record a workout from the header and the search capsule', async () => {
    const user = userEvent.setup()
    const { router } = renderTraining()
    expect(await screen.findByRole('link', { name: '搜索动作，比如 深蹲、卧推' })).toHaveAttribute('href', '/records/workouts/new')
    await user.click(screen.getByRole('button', { name: '记一次训练' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/records/workouts/new'))
  })
})
