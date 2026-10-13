import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, describe, expect, it } from 'vitest'
import { api } from '../api/client'
import { qk } from '../api/keys'
import { getToken } from '../api/token'
import { server } from '../test/msw/server'
import { renderRoute } from '../test/render'

type Router = ReturnType<typeof renderRoute>['router']

async function landsOn(router: Router, pathname: string) {
  await waitFor(() => expect(router.state.location.pathname).toBe(pathname))
}

// 健康页（经期与医嘱）是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好
beforeAll(async () => {
  await import('../features/health/HealthPage')
}, 60_000)

describe('route guards', () => {
  it('sends a visitor without a token to login', async () => {
    const { router } = renderRoute('/records', { token: null })
    await landsOn(router, '/login')
    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument()
  })

  it('sends a signed in user away from login', async () => {
    const { router } = renderRoute('/login')
    await landsOn(router, '/chat')
  })

  it('sends an unaccepted user to the disclaimer before anything else', async () => {
    const { router } = renderRoute('/records', { accepted: false, profile: { height_cm: null } })
    await landsOn(router, '/disclaimer')
    expect(await screen.findByRole('heading', { name: '免责声明' })).toBeInTheDocument()
  })

  it('sends an incomplete profile to the first missing onboarding step', async () => {
    const first = renderRoute('/chat', { profile: { height_cm: null } })
    await landsOn(first.router, '/onboarding/1')
    first.unmount()

    const second = renderRoute('/chat', { profile: { goal: null } })
    await landsOn(second.router, '/onboarding/2')
  })

  it('lets a complete user reach chat', async () => {
    const { router } = renderRoute('/')
    await landsOn(router, '/chat')
    expect(await screen.findByRole('heading', { name: '对话' })).toBeInTheDocument()
  })

  it('redirects a user without the cycle module away from the cycle page', async () => {
    const { router } = renderRoute('/health/cycle', { capabilities: { cycle: false } })
    await landsOn(router, '/chat')
  })

  it('lets a user with the cycle module reach the cycle page', async () => {
    const { router } = renderRoute('/health/cycle')
    expect(await screen.findByRole('heading', { name: '健康' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/health/cycle')
  })

  it('returns to login with the expired notice after a 401', async () => {
    const { router } = renderRoute('/chat')
    expect(await screen.findByRole('heading', { name: '对话' })).toBeInTheDocument()

    server.use(http.get('/api/auth/me', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    await act(async () => {
      await api('/api/auth/me').catch(() => undefined)
    })
    await landsOn(router, '/login')
    expect(router.state.location.state).toEqual({ expired: true })
    expect(getToken()).toBeNull()
  })

  it('returns to login with the expired notice when a guard check gets a 401', async () => {
    const { router } = renderRoute('/chat', { token: 'stale-token' })
    server.use(http.get('/api/disclaimer/status', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    await landsOn(router, '/login')
    expect(router.state.location.state).toEqual({ expired: true })
    expect(getToken()).toBeNull()
  })

  it('shows the backend message and retries when a guard check fails', async () => {
    let calls = 0
    // 在 renderRoute 之后装上：renderRoute 装的默认处理器会覆盖更早装的
    const { router } = renderRoute('/chat')
    server.use(http.get('/api/me/capabilities', () => {
      calls += 1
      return calls === 1
        ? HttpResponse.json({ error: { code: 'internal_error', message: '服务器内部错误' } }, { status: 500 })
        : HttpResponse.json({ cycle: true, medical: true, nutrition: true, fitness: true })
    }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务器内部错误')
    expect(alert).toHaveTextContent('internal_error')
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('heading', { name: '对话' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/chat')
  })

  it('keeps the page and nav when a background refetch fails', async () => {
    const { router, queryClient } = renderRoute('/me')
    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    server.use(http.get('/api/me/capabilities', () => new HttpResponse('bad gateway', { status: 502 })))
    // 能力清单过期并在后台重新请求失败：缓存里的数据还在
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: qk.capabilities })
    })
    expect(queryClient.getQueryState(qk.capabilities)?.status).toBe('error')
    await userEvent.click(screen.getByRole('link', { name: '记录' }))
    expect(await screen.findByRole('heading', { name: '记录' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/records')
    expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the error with a retry when there is no data and the request fails', async () => {
    const { router } = renderRoute('/me')
    let calls = 0
    server.use(http.get('/api/me/capabilities', () => {
      calls += 1
      return calls === 1
        ? new HttpResponse('bad gateway', { status: 502 })
        : HttpResponse.json({ cycle: true, medical: true, nutrition: true, fitness: true })
    }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服务暂时不可用，请稍后再试（HTTP 502）')
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/me')
  })

  it('sends the user to the disclaimer when its version changed mid session', async () => {
    const { router } = renderRoute('/chat')
    // 免责状态先答“已确认”（随后进入缓存），新版本让档案与能力清单返回 403，再取免责状态就是“未确认”
    let statusCalls = 0
    server.use(
      http.get('/api/disclaimer/status', () => {
        statusCalls += 1
        return HttpResponse.json({ current_version: 'v2', accepted: statusCalls === 1, accepted_at: null })
      }),
      http.get('/api/profile', () => HttpResponse.json(
        { error: { code: 'disclaimer_not_accepted', message: '请先阅读并确认免责声明' } }, { status: 403 },
      )),
      http.get('/api/me/capabilities', () => HttpResponse.json(
        { error: { code: 'disclaimer_not_accepted', message: '请先阅读并确认免责声明' } }, { status: 403 },
      )),
    )
    await landsOn(router, '/disclaimer')
    expect(router.state.location.state).toEqual({ from: '/chat' })
    expect(await screen.findByRole('heading', { name: '免责声明' })).toBeInTheDocument()
    // 缓存里过时的“已确认”被作废并重新取过
    await waitFor(() => expect(statusCalls).toBe(2))
  })
})

