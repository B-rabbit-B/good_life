import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { createMemoryRouter, matchRoutes, type RouteObject } from 'react-router'
import { describe, expect, it } from 'vitest'
import { qk } from '../api/keys'
import { capabilities, completeProfile } from '../test/fixtures/core'
import { server } from '../test/msw/server'
import { gate } from '../test/chat'
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

  it('waits for refreshed capabilities before opening health', async () => {
    const { router, queryClient } = renderRoute('/me')
    await screen.findByRole('heading', { name: '我的', level: 1 })
    // 刚关掉经期记录：能力清单正在重新取（新结果晚一点到），这时点“健康”
    server.use(http.get('/api/me/capabilities', async () => {
      await delay(200)
      return HttpResponse.json(capabilities({ cycle: false }))
    }))
    void queryClient.invalidateQueries({ queryKey: qk.capabilities })
    void router.navigate('/health')
    await expect.poll(() => router.state.location.pathname).toBe('/health/medical')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(router.state.location.pathname).toBe('/health/medical')
  })

  it('waits for a profile save before opening health', async () => {
    const { router } = renderRoute('/me')
    let saved = false
    server.use(
      http.patch('/api/profile', async () => {
        await delay(200)
        saved = true
        return HttpResponse.json(completeProfile({ cycle_tracking_opt_out: true }))
      }),
      http.get('/api/me/capabilities', () => HttpResponse.json(capabilities({ cycle: !saved }))),
    )
    // 关掉经期记录，保存还没回来就点“健康”
    await userEvent.click(await screen.findByRole('switch', { name: /经期记录/ }))
    void router.navigate('/health')
    await expect.poll(() => router.state.location.pathname).toBe('/health/medical')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(router.state.location.pathname).toBe('/health/medical')
  })

  it('opens health right away when the capabilities are only stale', async () => {
    const { router, queryClient } = renderRoute('/me')
    await screen.findByRole('heading', { name: '我的', level: 1 })
    // 清单只是过期（不是被作废）：打开 /health 会在后台重取，但不等它
    const current = queryClient.getQueryData(qk.capabilities)
    queryClient.setQueryData(qk.capabilities, current, { updatedAt: Date.now() - 60_000 })
    const held = gate()
    let requests = 0
    server.use(http.get('/api/me/capabilities', async () => {
      requests += 1
      await held.promise
      return HttpResponse.json(capabilities())
    }))
    void router.navigate('/health')
    await expect.poll(() => router.state.location.pathname).toBe('/health/cycle')
    // 跳转时重取还没回来，期间没有显示启动画面
    expect(requests).toBe(1)
    expect(screen.queryByText('正在加载')).not.toBeInTheDocument()
    held.open()
  })

  it('sends unknown paths to chat', async () => {
    const { router } = renderRoute('/nowhere')
    await expect.poll(() => router.state.location.pathname).toBe('/chat')
  })
})
