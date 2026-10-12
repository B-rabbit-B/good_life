import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { api } from '../api/client'
import { getToken } from '../api/token'
import { server } from '../test/msw/server'
import { renderRoute } from '../test/render'

type Router = ReturnType<typeof renderRoute>['router']

async function landsOn(router: Router, pathname: string) {
  await waitFor(() => expect(router.state.location.pathname).toBe(pathname))
}

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
})
