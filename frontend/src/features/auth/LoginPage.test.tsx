import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { api } from '../../api/client'
import { getToken } from '../../api/token'
import { TEST_TOKEN } from '../../test/fixtures/core'
import { TEST_PASSWORD } from '../../test/fixtures/profile'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

type Router = ReturnType<typeof renderRoute>['router']

const landsOn = (router: Router, pathname: string) =>
  waitFor(() => expect(router.state.location.pathname).toBe(pathname))

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, button: string, username = 'zhou_ning') {
  await user.type(screen.getByLabelText('用户名'), username)
  await user.type(screen.getByLabelText('密码'), TEST_PASSWORD)
  await user.click(screen.getByRole('button', { name: button }))
}

describe('login page', () => {
  it('registers then logs in and goes to the disclaimer', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/login', { token: null, accepted: false })
    const calls: string[] = []
    server.use(
      http.post('/api/auth/register', async ({ request }) => {
        calls.push(`register ${JSON.stringify(await request.json())}`)
        return HttpResponse.json({ id: '1', username: 'zhou_ning', created_at: '2026-10-12T08:00:00Z' }, { status: 201 })
      }),
      http.post('/api/auth/login', async ({ request }) => {
        calls.push(`login ${JSON.stringify(await request.json())}`)
        return HttpResponse.json({ access_token: TEST_TOKEN, token_type: 'bearer' })
      }),
    )
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    expect(screen.getByRole('heading', { level: 1, name: '注册' })).toBeInTheDocument()
    expect(screen.getByLabelText('用户名')).toHaveAccessibleDescription('3 到 32 位，字母、数字或下划线')
    expect(screen.getByLabelText('密码')).toHaveAccessibleDescription('至少 8 位')
    await fillAndSubmit(user, '注册并继续')

    await landsOn(router, '/disclaimer')
    const body = JSON.stringify({ username: 'zhou_ning', password: TEST_PASSWORD })
    expect(calls).toEqual([`register ${body}`, `login ${body}`])
    expect(getToken()).toBe(TEST_TOKEN)
    expect(await screen.findByRole('heading', { name: '免责声明' })).toBeInTheDocument()
  })

  it('shows username_taken under the username field', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/register', () => HttpResponse.json(
      { error: { code: 'username_taken', message: '该用户名已被注册，请换一个' } }, { status: 409 },
    )))
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await fillAndSubmit(user, '注册并继续')

    await waitFor(() => expect(screen.getByLabelText('用户名')).toHaveAccessibleDescription(/该用户名已被注册，请换一个/))
    expect(screen.getByLabelText('用户名')).toHaveAttribute('aria-invalid', 'true')
    expect(router.state.location.pathname).toBe('/login')
    expect(getToken()).toBeNull()
  })

  it('shows invalid credentials as a form error and keeps the token empty', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/login', () => HttpResponse.json(
      { error: { code: 'invalid_credentials', message: '用户名或密码错误' } }, { status: 401 },
    )))
    expect(await screen.findByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
    await fillAndSubmit(user, '登录')

    expect(await screen.findByRole('alert')).toHaveTextContent('用户名或密码错误')
    expect(getToken()).toBeNull()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByRole('heading', { name: '登录已过期' })).not.toBeInTheDocument()
  })

  it('shows the expired notice after a 401', async () => {
    const { router } = renderRoute('/records')
    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    server.use(http.get('/api/auth/me', () => HttpResponse.json(
      { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
    )))
    await act(async () => {
      await api('/api/auth/me').catch(() => undefined)
    })
    await landsOn(router, '/login')
    expect(await screen.findByRole('heading', { name: '登录已过期' })).toBeInTheDocument()
    expect(screen.getByText('请重新登录，记录不会丢失。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
  })

  it('maps validation details to fields', async () => {
    const user = userEvent.setup()
    renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/register', () => HttpResponse.json({
      error: {
        code: 'validation_error',
        message: '请求参数不合法',
        details: [
          { field: 'username', message: "String should match pattern '^[A-Za-z0-9_]+$'" },
          { field: 'password', message: 'String should have at least 8 characters' },
        ],
      },
    }, { status: 422 })))
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await fillAndSubmit(user, '注册并继续', 'zhou-ning')

    await waitFor(() => expect(screen.getByLabelText('用户名'))
      .toHaveAccessibleDescription(/String should match pattern '\^\[A-Za-z0-9_\]\+\$'/))
    expect(screen.getByLabelText('密码')).toHaveAccessibleDescription(/String should have at least 8 characters/)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
