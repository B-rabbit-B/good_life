import type { QueryClient, QueryKey } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { createTestQueryClient } from '../test/render'
import { discardConversations, DOMAINS, invalidateDomain, type Domain } from './invalidation'
import { qk } from './keys'

const DAY = '2026-10-13'
const ALL: Record<string, QueryKey> = {
  summary: qk.summary(DAY),
  meals: qk.meals(DAY),
  foodSearch: qk.foodSearch('鸡'),
  recognitions: qk.recognitions,
  recognition: qk.recognition('r1'),
  recognitionImage: qk.recognitionImage('r1'),
  weekSummary: qk.weekSummary,
  workouts: qk.workouts(DAY, DAY),
  exerciseTrend: qk.exerciseTrend('e1'),
  periods: qk.periods,
  prediction: qk.prediction,
  reviews: qk.reviews,
  medicalItems: qk.medicalItems,
  orders: qk.orders,
  constraints: qk.constraints(),
  profile: qk.profile,
  capabilities: qk.capabilities,
  conversations: qk.conversations,
  providers: qk.providers,
}

function seeded(): QueryClient {
  const queryClient = createTestQueryClient()
  for (const key of Object.values(ALL)) queryClient.setQueryData(key, { seeded: true })
  return queryClient
}

function invalidated(queryClient: QueryClient): string[] {
  return Object.entries(ALL)
    .filter(([, key]) => queryClient.getQueryState(key)?.isInvalidated)
    .map(([name]) => name)
    .sort()
}

const EXPECTED: Record<Domain, string[]> = {
  nutrition: ['meals', 'recognition', 'recognitions', 'summary'],
  fitness: ['exerciseTrend', 'recognition', 'recognitions', 'summary', 'weekSummary', 'workouts'],
  cycle: ['meals', 'periods', 'prediction', 'recognition', 'recognitions', 'summary'],
  medical: ['constraints', 'meals', 'medicalItems', 'orders', 'recognition', 'recognitions', 'reviews', 'summary', 'workouts'],
  profile: [
    'capabilities', 'meals', 'periods', 'prediction', 'profile', 'recognition', 'recognitions', 'summary', 'weekSummary',
  ],
}

describe('domain invalidation', () => {
  it('lists every domain', () => {
    expect([...DOMAINS].sort()).toEqual(Object.keys(EXPECTED).sort())
  })

  it('marks only the derived queries of each domain as invalidated', async () => {
    for (const domain of Object.keys(EXPECTED) as Domain[]) {
      const queryClient = seeded()
      await invalidateDomain(queryClient, domain)
      expect(invalidated(queryClient), domain).toEqual(EXPECTED[domain])
    }
  })

  it('never refetches a kept photo', async () => {
    const queryClient = seeded()
    for (const domain of DOMAINS) await invalidateDomain(queryClient, domain)
    expect(queryClient.getQueryState(qk.recognitionImage('r1'))?.isInvalidated).toBe(false)
  })

  it('drops every conversation and keeps today without an opening after clearing the chat', () => {
    const queryClient = seeded()
    queryClient.setQueryData(qk.conversation('c1'), { seeded: true })
    queryClient.setQueryData(qk.opening, { opening: { id: 'o1', kind: 'review_due', question: '要不要现在看看？' } })
    queryClient.setQueryData(qk.agentSettings, { seeded: true })
    discardConversations(queryClient)
    expect(queryClient.getQueryData(qk.conversations)).toBeUndefined()
    expect(queryClient.getQueryData(qk.conversation('c1'))).toBeUndefined()
    expect(queryClient.getQueryData(qk.opening)).toEqual({ opening: null })
    expect(queryClient.getQueryState(qk.opening)?.isInvalidated).toBe(false)
    expect(queryClient.getQueryData(qk.agentSettings)).toEqual({ seeded: true })
    expect(queryClient.getQueryData(qk.providers)).toEqual({ seeded: true })
  })

  it('does not invent an opening that was never fetched', () => {
    const queryClient = seeded()
    discardConversations(queryClient)
    expect(queryClient.getQueryState(qk.opening)).toBeUndefined()
  })
})
