import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { addDays, todayISO } from '../../lib/dates'
import {
  BENCH, kneeConflict, KNEE_CONFLICT_MESSAGE, PARTIAL_MATCH_MESSAGE, searchOut, SQUAT, WALK,
} from '../../test/fixtures/fitness'
import { fitnessHandlers, type FitnessOptions } from '../../test/msw/handlers/fitness'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const today = todayISO()
const SEARCH: FitnessOptions['search'] = {
  卧推: searchOut('卧推', [BENCH], PARTIAL_MATCH_MESSAGE),
  哑铃卧推: searchOut('哑铃卧推', [BENCH]),
  快走: searchOut('快走', [WALK]),
  深蹲: searchOut('深蹲', [SQUAT]),
}

function renderWorkoutNew(opts: FitnessOptions = {}) {
  const result = renderRoute('/records/workouts/new')
  const fitness = fitnessHandlers({ search: SEARCH, ...opts })
  server.use(...fitness.handlers)
  return { ...result, fitness }
}

async function add(user: ReturnType<typeof userEvent.setup>, q: string, name: string) {
  const search = await screen.findByRole('searchbox', { name: '搜索动作' })
  await user.clear(search)
  await user.type(search, q)
  const results = await screen.findByRole('list', { name: '搜索结果' })
  await user.click(within(results).getByRole('button', { name: new RegExp(`^${name}`) }))
  return screen.findByRole('group', { name })
}

beforeAll(async () => {
  await import('./WorkoutNewPage')
}, 60_000)

describe('workout new page', { timeout: 15_000 }, () => {
  it('searches exercises and shows the backend message', async () => {
    const user = userEvent.setup()
    renderWorkoutNew()
    const search = await screen.findByRole('searchbox', { name: '搜索动作' })
    await user.type(search, '卧推')
    expect(await screen.findByText(PARTIAL_MATCH_MESSAGE)).toBeInTheDocument()
    const results = screen.getByRole('list', { name: '搜索结果' })
    expect(within(results).getAllByRole('button').map((button) => button.textContent)).toEqual(['哑铃卧推胸、肱三头肌、肩 · 哑铃'])
    await user.clear(search)
    await user.type(search, '倒立')
    expect(await screen.findByText('未找到与“倒立”匹配的动作，可以新增自定义动作')).toBeInTheDocument()
  })

  it('adds sets and saves the workout body', async () => {
    const user = userEvent.setup()
    const { fitness, router } = renderWorkoutNew()
    const bench = await add(user, '哑铃卧推', '哑铃卧推')
    await user.type(within(bench).getByLabelText('第 1 组重量'), '12')
    await user.type(within(bench).getByLabelText('第 1 组次数'), '10')
    await user.click(within(bench).getByRole('button', { name: '加一组' }))
    expect(within(bench).getByLabelText('第 2 组重量')).toHaveValue('12')
    await user.clear(within(bench).getByLabelText('第 2 组次数'))
    await user.type(within(bench).getByLabelText('第 2 组次数'), '8')
    const walk = await add(user, '快走', '快走')
    await user.type(within(walk).getByLabelText('时长'), '30')
    await user.type(within(walk).getByLabelText('距离（可不填）'), '2.5')
    fireEvent.change(screen.getByLabelText('训练日期'), { target: { value: addDays(today, -1) } })
    await user.type(screen.getByLabelText('整次时长（可不填）'), '45')
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(fitness.record.created).toEqual([{
      performed_on: addDays(today, -1),
      duration_minutes: 45,
      strength: [{ exercise_id: 'ex:dumbbell_bench_press', sets: [{ weight_kg: 12, reps: 10 }, { weight_kg: 12, reps: 8 }] }],
      cardio: [{ exercise_id: 'ex:brisk_walking', duration_minutes: 30, distance_km: 2.5 }],
    }]))
    await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe('/records?tab=training'))
    expect(await screen.findByText('已记下')).toBeInTheDocument()
  })

  it('removes a set and an exercise before saving', async () => {
    const user = userEvent.setup()
    const { fitness } = renderWorkoutNew()
    const squat = await add(user, '深蹲', '深蹲')
    await user.type(within(squat).getByLabelText('第 1 组重量'), '40')
    await user.type(within(squat).getByLabelText('第 1 组次数'), '8')
    await user.click(within(squat).getByRole('button', { name: '加一组' }))
    await user.click(within(squat).getByRole('button', { name: '删去第 2 组' }))
    expect(within(squat).queryByLabelText('第 2 组重量')).not.toBeInTheDocument()
    const walk = await add(user, '快走', '快走')
    await user.click(within(walk).getByRole('button', { name: '移除这个动作' }))
    expect(screen.queryByRole('group', { name: '快走' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(fitness.record.created).toEqual([{
      performed_on: today, duration_minutes: null,
      strength: [{ exercise_id: 'ex:squat', sets: [{ weight_kg: 40, reps: 8 }] }], cardio: [],
    }]))
  })

  it('shows backend field errors verbatim and saves once', async () => {
    const user = userEvent.setup({ delay: null })
    const { fitness } = renderWorkoutNew({
      createError: {
        status: 422, code: 'validation_error', message: '请求参数不正确',
        details: [{ field: 'strength.0.sets.0.reps', message: '应为 1 至 100 之间的整数' }],
      },
    })
    const bench = await add(user, '哑铃卧推', '哑铃卧推')
    await user.type(within(bench).getByLabelText('第 1 组重量'), '12')
    await user.type(within(bench).getByLabelText('第 1 组次数'), '0')
    await user.dblClick(screen.getByRole('button', { name: '保存' }))
    expect(await within(bench).findByText('应为 1 至 100 之间的整数')).toBeInTheDocument()
    expect(within(bench).getByLabelText('第 1 组次数')).toHaveAttribute('aria-invalid', 'true')
    expect(fitness.record.created).toHaveLength(1)
  })

  it('shows a search error verbatim with its code', async () => {
    const user = userEvent.setup()
    renderWorkoutNew({ searchError: { status: 500, code: 'internal_error', message: '服务出了点问题，请稍后再试' } })
    await user.type(await screen.findByRole('searchbox', { name: '搜索动作' }), '深蹲')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务出了点问题，请稍后再试')
    expect(alert).toHaveTextContent('错误码 internal_error')
  })

  it('shows a form error with its code', async () => {
    const user = userEvent.setup()
    renderWorkoutNew({ createError: { status: 422, code: 'workout_in_future', message: '不能记录未来日期的训练' } })
    await add(user, '快走', '快走')
    await user.type(screen.getByLabelText('时长'), '20')
    await user.click(screen.getByRole('button', { name: '保存' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('不能记录未来日期的训练')
    expect(alert).toHaveTextContent('错误码 workout_in_future')
  })

  it('tells the returned conflicts after saving', async () => {
    const user = userEvent.setup()
    renderWorkoutNew({ createConflicts: [kneeConflict([])] })
    await add(user, '快走', '快走')
    await user.type(screen.getByLabelText('时长'), '20')
    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(await screen.findByText(`已记下。${KNEE_CONFLICT_MESSAGE}`)).toBeInTheDocument()
  })
})
