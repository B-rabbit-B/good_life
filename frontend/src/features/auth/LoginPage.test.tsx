import { onlineManager } from '@tanstack/react-query'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, onTestFinished } from 'vitest'
import { api } from '../../api/client'
import { getToken } from '../../api/token'
import { MIN_AGE } from '../../lib/contract'
import { TEST_TOKEN } from '../../test/fixtures/core'
import { TEST_PASSWORD } from '../../test/fixtures/profile'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

type Router = ReturnType<typeof renderRoute>['router']

const AGE_CONFIRMATION = `我已年满 ${MIN_AGE} 周岁`

const landsOn = (router: Router, pathname: string) =>
  waitFor(() => expect(router.state.location.pathname).toBe(pathname))

/** 填写用户名与密码后提交；注册时先勾选年龄确认 */
async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, button: string, username = 'zhou_ning') {
  await user.type(screen.getByLabelText('用户名'), username)
  await user.type(screen.getByLabelText('密码'), TEST_PASSWORD)
  if (button === '注册并继续') await user.click(screen.getByRole('checkbox', { name: AGE_CONFIRMATION }))
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
    const login = JSON.stringify({ username: 'zhou_ning', password: TEST_PASSWORD })
    const registered = JSON.stringify({ username: 'zhou_ning', password: TEST_PASSWORD, age_confirmed: true })
    expect(calls).toEqual([`register ${registered}`, `login ${login}`])
    expect(getToken()).toBe(TEST_TOKEN)
    expect(await screen.findByRole('heading', { name: '免责声明' })).toBeInTheDocument()
  })

  it('keeps register disabled until the age confirmation is checked', async () => {
    const user = userEvent.setup()
    renderRoute('/login', { token: null })
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await user.type(screen.getByLabelText('用户名'), 'zhou_ning')
    await user.type(screen.getByLabelText('密码'), TEST_PASSWORD)
    const submit = screen.getByRole('button', { name: '注册并继续' })
    const confirm = screen.getByRole('checkbox', { name: AGE_CONFIRMATION })
    expect(confirm).not.toBeChecked()
    expect(submit).toBeDisabled()
    await user.click(confirm)
    expect(submit).toBeEnabled()
    await user.click(confirm)
    expect(submit).toBeDisabled()
  })

  it('sends age_confirmed with the registration', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/login', { token: null, accepted: false })
    const bodies: unknown[] = []
    server.use(http.post('/api/auth/register', async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json({ id: '1', username: 'zhou_ning', created_at: '2026-10-12T08:00:00Z' }, { status: 201 })
    }))
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await fillAndSubmit(user, '注册并继续')
    await landsOn(router, '/disclaimer')
    expect(bodies).toEqual([{ username: 'zhou_ning', password: TEST_PASSWORD, age_confirmed: true }])
  })

  it('hides the age confirmation when logging in', async () => {
    const user = userEvent.setup()
    renderRoute('/login', { token: null })
    expect(await screen.findByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '注册' }))
    expect(screen.getByRole('checkbox', { name: AGE_CONFIRMATION })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '登录' }))
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登录' })).toBeEnabled()
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
    const notice = await screen.findByRole('heading', { name: '登录已过期' })
    expect(screen.getByText('请重新登录，记录不会丢失。')).toBeInTheDocument()
    expect(notice.closest('[role="status"]')).not.toBeNull()
    // 页题在前，过期说明在后
    const title = screen.getByRole('heading', { level: 1, name: '登录' })
    expect(title.compareDocumentPosition(notice) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('maps validation details to fields', async () => {
    const user = userEvent.setup()
    renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/register', () => HttpResponse.json({
      error: {
        code: 'validation_error',
        message: '请求参数不合法',
        details: [
          { field: 'username', message: '格式不符合要求，请按提示修改', type: 'string_pattern_mismatch' },
          { field: 'password', message: '至少 8 个字符，请补全', type: 'string_too_short' },
        ],
      },
    }, { status: 422 })))
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await fillAndSubmit(user, '注册并继续', 'zhou-ning')

    await waitFor(() => expect(screen.getByLabelText('用户名')).toHaveAccessibleDescription(/格式不符合要求，请按提示修改/))
    expect(screen.getByLabelText('密码')).toHaveAccessibleDescription(/至少 8 个字符，请补全/)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // 焦点移到第一个出错的字段
    await waitFor(() => expect(screen.getByLabelText('用户名')).toHaveFocus())
  })

  it('switches to login and keeps the fields when login fails after registering', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/login', { token: null })
    let registers = 0
    server.use(
      http.post('/api/auth/register', () => {
        registers += 1
        return HttpResponse.json({ id: '1', username: 'zhou_ning', created_at: '2026-10-12T08:00:00Z' }, { status: 201 })
      }),
      http.post('/api/auth/login', () => HttpResponse.json(
        { error: { code: 'internal_error', message: '服务器内部错误' } }, { status: 500 },
      )),
    )
    await user.click(await screen.findByRole('tab', { name: '注册' }))
    await fillAndSubmit(user, '注册并继续')

    expect(await screen.findByRole('alert')).toHaveTextContent('服务器内部错误')
    expect(screen.getByRole('tab', { name: '登录' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('用户名')).toHaveValue('zhou_ning')
    expect(screen.getByLabelText('密码')).toHaveValue(TEST_PASSWORD)
    // 重试只登录，不再注册
    server.use(http.post('/api/auth/login', () => HttpResponse.json({ access_token: TEST_TOKEN, token_type: 'bearer' })))
    await user.click(screen.getByRole('button', { name: '登录' }))
    await landsOn(router, '/chat')
    expect(registers).toBe(1)
  })

  it('shows the network error while the browser is offline', async () => {
    const user = userEvent.setup()
    onlineManager.setOnline(false)
    onTestFinished(() => onlineManager.setOnline(true))
    renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/login', () => HttpResponse.error()))
    expect(await screen.findByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
    await fillAndSubmit(user, '登录')

    expect(await screen.findByRole('alert')).toHaveTextContent('网络连接失败，请检查网络后重试')
    expect(screen.getByRole('button', { name: '登录' })).toBeEnabled()
  })

  it('keeps no password in the mutation cache after an error', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderRoute('/login', { token: null })
    server.use(http.post('/api/auth/login', () => HttpResponse.json(
      { error: { code: 'invalid_credentials', message: '用户名或密码错误' } }, { status: 401 },
    )))
    expect(await screen.findByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
    await fillAndSubmit(user, '登录')
    expect(await screen.findByRole('alert')).toHaveTextContent('用户名或密码错误')

    const cached = () => JSON.stringify(queryClient.getMutationCache().getAll().map((mutation) => mutation.state))
    await waitFor(() => expect(cached()).not.toContain(TEST_PASSWORD))
  })
})
