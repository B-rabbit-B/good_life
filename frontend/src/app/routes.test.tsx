import { matchRoutes, type RouteObject } from 'react-router'
import { describe, expect, it } from 'vitest'
import { renderRoute } from '../test/render'
import { PATHS } from './paths'
import { routes, type RouteHandle } from './routes'

type PathKey = keyof typeof PATHS

const SAMPLE_PARAMS: Record<string, string> = { step: '1', recId: 'rec-1' }
const sample = (pattern: string) => pattern.replace(/:(\w+)/g, (_, name: string) => SAMPLE_PARAMS[name] ?? 'x')

function flatten(list: RouteObject[]): RouteObject[] {
  return list.flatMap((route) => [route, ...flatten(route.children ?? [])])
}

const byPath = (pattern: string) => flatten(routes).filter((route) => route.path === pattern)

describe('route table', () => {
  it('registers a route for every path', () => {
    for (const [key, pattern] of Object.entries(PATHS)) {
      const matches = matchRoutes(routes, sample(pattern))
      const leaf = matches?.[matches.length - 1]?.route
      expect(leaf?.path, `${key} ${pattern}`).toBe(pattern)
    }
    // 组件样张页只在开发模式与端到端构建里注册；测试按开发模式运行
    expect(import.meta.env.DEV).toBe(true)
    expect(byPath(PATHS.gallery)).toHaveLength(1)
  })

  it('splits every page into its own chunk', () => {
    const redirects = new Set<string>([PATHS.root, PATHS.health])
    for (const [key, pattern] of Object.entries(PATHS)) {
      if (redirects.has(pattern)) continue
      const [route] = byPath(pattern)
      expect(route?.lazy, key).toBeTypeOf('function')
      expect(route?.element, key).toBeUndefined()
    }
  })

  it('marks the sensitive pages from the design', () => {
    const sensitive = (Object.keys(PATHS) as PathKey[]).filter((key) => {
      const [route] = byPath(PATHS[key])
      return (route?.handle as RouteHandle | undefined)?.sensitive === true
    })
    expect(sensitive.sort()).toEqual([
      'chat', 'cycle', 'health', 'me', 'medical', 'medicalNew', 'photoResult', 'profileEdit', 'records', 'restaurants',
    ])
  })

  it('gives every app page a nav handle', () => {
    const expected: Partial<Record<PathKey, RouteHandle['nav']>> = {
      chat: 'chat', records: 'tabs', cycle: 'tabs', medical: 'tabs', me: 'tabs', login: 'none', disclaimer: 'none',
      onboarding: 'none', photoNew: 'none', photoResult: 'none', mealNew: 'none', workoutNew: 'none', medicalNew: 'none',
      restaurants: 'none', profileEdit: 'none', models: 'none', modelNew: 'none', privacy: 'none', disclaimerView: 'none',
    }
    for (const [key, nav] of Object.entries(expected)) {
      const [route] = byPath(PATHS[key as PathKey])
      expect((route?.handle as RouteHandle | undefined)?.nav, key).toBe(nav)
    }
  })

  it('opens health on the first open segment', async () => {
    const female = renderRoute('/health')
    await expect.poll(() => female.router.state.location.pathname).toBe('/health/cycle')
    female.unmount()

    const male = renderRoute('/health', { capabilities: { cycle: false } })
    await expect.poll(() => male.router.state.location.pathname).toBe('/health/medical')
    male.unmount()

    const neither = renderRoute('/health', { capabilities: { cycle: false, medical: false } })
    await expect.poll(() => neither.router.state.location.pathname).toBe('/chat')
  })

  it('sends unknown paths to chat', async () => {
    const { router } = renderRoute('/nowhere')
    await expect.poll(() => router.state.location.pathname).toBe('/chat')
  })
})
