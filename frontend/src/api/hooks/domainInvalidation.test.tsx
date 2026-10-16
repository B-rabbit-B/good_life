import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { completeProfile, TEST_TOKEN } from '../../test/fixtures/core'
import { server } from '../../test/msw/server'
import { createTestQueryClient } from '../../test/render'
import { qk } from '../keys'
import { setToken } from '../token'
import { useCreatePeriod, useDeletePeriod } from './cycle'
import { useCreateWorkout, type WorkoutInput } from './fitness'
import { useCancelProposal } from './medical'
import { useCreateMeal, type MealInput } from './nutrition'
import { useConfirmRecognition } from './photos'
import { useUpdateProfile } from './profile'

const OTHER_DAY = '2026-10-01'
const SEEDED = {
  summary: qk.summary(OTHER_DAY),
  meals: qk.meals(OTHER_DAY),
  recognitions: qk.recognitions,
  weekSummary: qk.weekSummary,
  workouts: qk.workouts(OTHER_DAY, OTHER_DAY),
  prediction: qk.prediction,
  reviews: qk.reviews,
  capabilities: qk.capabilities,
  conversations: qk.conversations,
}

/** 缓存里先放好 SEEDED 的查询，调用写操作的钩子；返回之后被标记失效的那些（按名字排序） */
async function invalidatedAfter<V>(useWrite: () => { mutateAsync: (variables: V) => Promise<unknown> }, variables: V) {
  setToken(TEST_TOKEN)
  const queryClient = createTestQueryClient()
  for (const key of Object.values(SEEDED)) queryClient.setQueryData(key, { seeded: true })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(useWrite, { wrapper })
  await act(async () => {
    await result.current.mutateAsync(variables)
  })
  const names = Object.entries(SEEDED).filter(([, key]) => queryClient.getQueryState(key)?.isInvalidated).map(([name]) => name)
  return { names: names.sort(), queryClient }
}

describe('write hooks invalidate their domain', () => {
  it('logging a meal invalidates nutrition on every date and the recognitions', async () => {
    server.use(http.post('/api/nutrition/meals', () => HttpResponse.json({ id: 'm1' })))
    const { names } = await invalidatedAfter(useCreateMeal, { eaten_on: '2026-10-13' } as MealInput)
    expect(names).toEqual(['meals', 'recognitions', 'summary'])
  })

  it('logging a workout invalidates fitness, the nutrition summary and the recognitions', async () => {
    server.use(http.post('/api/fitness/workouts', () => HttpResponse.json({ id: 'w1' })))
    const { names } = await invalidatedAfter(useCreateWorkout, {} as WorkoutInput)
    expect(names).toEqual(['recognitions', 'summary', 'weekSummary', 'workouts'])
  })

  it('recording a period invalidates cycle, nutrition and the recognitions', async () => {
    server.use(http.post('/api/cycle/periods', () => HttpResponse.json({ id: 'p1' })))
    const { names } = await invalidatedAfter(useCreatePeriod, { start_date: OTHER_DAY })
    expect(names).toEqual(['meals', 'prediction', 'recognitions', 'summary'])
  })

  it('deleting a period invalidates the same cycle domain', async () => {
    server.use(http.delete('/api/cycle/periods/p1', () => new HttpResponse(null, { status: 204 })))
    const { names } = await invalidatedAfter(useDeletePeriod, 'p1')
    expect(names).toEqual(['meals', 'prediction', 'recognitions', 'summary'])
  })

  it('a medical change invalidates medical, nutrition, workouts and the recognitions', async () => {
    server.use(http.post('/api/medical/items/i1/cancel-proposal', () => HttpResponse.json({ id: 'i1' })))
    const { names } = await invalidatedAfter(useCancelProposal, 'i1')
    expect(names).toEqual(['meals', 'recognitions', 'reviews', 'summary', 'workouts'])
  })

  it('confirming a recognition refreshes the nutrition domain', async () => {
    server.use(http.post('/api/photos/recognitions/r1/confirm', () => HttpResponse.json({ id: 'r1', status: 'confirmed' })))
    const { names, queryClient } = await invalidatedAfter(
      () => useConfirmRecognition('r1'),
      { eaten_on: '2026-10-13', meal_type: 'lunch' } as const,
    )
    // 摄入汇总与餐次是按日期的全部查询（不只确认的那一天）；返回的那条记录已经写进缓存，不再重取
    expect(names).toEqual(['meals', 'recognitions', 'summary'])
    expect(queryClient.getQueryData(qk.recognition('r1'))).toMatchObject({ status: 'confirmed' })
  })

  it('a profile update keeps the returned profile and invalidates what depends on it', async () => {
    server.use(http.patch('/api/profile', () => HttpResponse.json(completeProfile({ gender: 'male' }))))
    const { names, queryClient } = await invalidatedAfter(useUpdateProfile, { gender: 'male' })
    expect(names).toEqual(['capabilities', 'meals', 'prediction', 'recognitions', 'summary', 'weekSummary'])
    expect(queryClient.getQueryData(qk.profile)).toMatchObject({ gender: 'male' })
  })
})
