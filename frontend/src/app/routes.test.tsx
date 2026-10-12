import { screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, matchRoutes, type RouteObject } from 'react-router'
import { describe, expect, it } from 'vitest'
import { renderRoute, renderRouter } from '../test/render'
import { PATHS, type PathKey } from './paths'
import { RouteError, routes, type RouteHandle } from './routes'
import { isSensitivePage, SENSITIVE_AREAS } from './sensitiveAreas'

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

  it('derives the sensitive flag from the sensitive area registry', () => {
    // 每个登记了敏感区的页面都有路由；每个带 handle 的路由的 sensitive 恰好等于它在不在登记表里
    for (const key of Object.keys(SENSITIVE_AREAS)) {
      expect(byPath(PATHS[key as PathKey]), key).toHaveLength(1)
    }
    for (const key of Object.keys(PATHS) as PathKey[]) {
      const handle = byPath(PATHS[key])[0]?.handle as RouteHandle | undefined
      if (handle) expect(handle.sensitive, key).toBe(isSensitivePage(key))
    }
    const sensitive = (Object.keys(PATHS) as PathKey[])
      .filter((key) => (byPath(PATHS[key])[0]?.handle as RouteHandle | undefined)?.sensitive === true)
    expect(sensitive.sort()).toEqual(Object.keys(SENSITIVE_AREAS).sort())
  })

  it('removes the boot shell under a route error', async () => {
    const boot = document.createElement('div')
    boot.id = 'boot-shell'
    document.body.prepend(boot)
    const router = createMemoryRouter([{
      ErrorBoundary: RouteError,
      children: [{ path: '/broken', lazy: () => Promise.reject(new Error('分包没能加载')) }],
    }], { initialEntries: ['/broken'] })
    renderRouter(router)
    expect(await screen.findByRole('alert')).toHaveTextContent('页面没能加载，请检查网络后重试')
    await waitFor(() => expect(document.getElementById('boot-shell')).toBeNull())
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
