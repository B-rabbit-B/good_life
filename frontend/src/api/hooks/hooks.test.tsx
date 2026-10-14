import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { createMemoryRouter, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'
import { AppShell } from '../../app/AppShell'
import type { RouteHandle } from '../../app/routes'
import { completeProfile, TEST_TOKEN } from '../../test/fixtures/core'
import { consentHandlers } from '../../test/msw/handlers/consents'
import { server } from '../../test/msw/server'
import { createTestQueryClient, renderRouter } from '../../test/render'
import { qk } from '../keys'
import { getToken, setToken } from '../token'
import { useLogout } from '../../app/useLogout'
import { useLogin, useMe } from './auth'
import { useConsents, useModuleConsent, useModuleReady } from './consents'
import { useMedicalItems, useMedicalReviews } from './medical'
import { useCapabilities, useUpdateProfile } from './profile'

const handle: RouteHandle = { nav: 'none', sensitive: false }

function withClient(queryClient = createTestQueryClient()) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

describe('auth and profile hooks', () => {
  it('clears the cache of the previous account on login', async () => {
    server.use(http.post('/api/auth/login', () => HttpResponse.json({ access_token: 'new-token', token_type: 'bearer' })))
    const { queryClient, wrapper } = withClient()
    queryClient.setQueryData(qk.profile, completeProfile({ height_cm: 180 }))
    const { result } = renderHook(() => useLogin(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ username: 'tester', password: 'secret-123' })
    })
    expect(queryClient.getQueryData(qk.profile)).toBeUndefined()
    expect(getToken()).toBe('new-token')
  })

  it('refreshes the capabilities after a profile update', async () => {
    setToken(TEST_TOKEN)
    server.use(http.patch('/api/profile', () => HttpResponse.json(completeProfile({ gender: 'male' }))))
    const { queryClient, wrapper } = withClient()
    const { result } = renderHook(() => ({ caps: useCapabilities(), update: useUpdateProfile() }), { wrapper })
    await waitFor(() => expect(result.current.caps.data?.cycle).toBe(true))
    server.use(http.get('/api/me/capabilities', () =>
      HttpResponse.json({ cycle: false, medical: true, nutrition: true, fitness: true })))
    await act(async () => {
      await result.current.update.mutateAsync({ gender: 'male' })
    })
    // mutateAsync 返回时能力清单已经取回（缓存里已是新值，页面随后重绘）
    expect(queryClient.getQueryData(qk.capabilities)).toMatchObject({ cycle: false })
    await waitFor(() => expect(result.current.caps.data?.cycle).toBe(false))
    expect(queryClient.getQueryData(qk.profile)).toMatchObject({ gender: 'male' })
  })

  it('logs out to login without the expired notice even when the token was revoked', async () => {
    setToken(TEST_TOKEN)
    let unauthenticatedCalls = 0
    server.use(
      http.post('/api/auth/logout', () => HttpResponse.json(
        { error: { code: 'invalid_token', message: '登录已失效，请重新登录' } }, { status: 401 },
      )),
      http.get('/api/auth/me', ({ request }) => {
        if (!request.headers.get('Authorization')) {
          unauthenticatedCalls += 1
          return HttpResponse.json({ error: { code: 'not_authenticated', message: '请先登录' } }, { status: 401 })
        }
        return HttpResponse.json({ id: 'u1', username: 'tester', created_at: '2026-10-01T08:00:00Z' })
      }),
    )
    function MePage() {
      const me = useMe()
      const logout = useLogout()
      return (
        <>
          <p>{me.data?.username ?? '…'}</p>
          <button type="button" onClick={() => logout.mutate()}>退出登录</button>
        </>
      )
    }
    function LoginPage() {
      const location = useLocation()
      return <p>登录页 {JSON.stringify(location.state)}</p>
    }
    const router = createMemoryRouter([{
      element: <AppShell />,
      children: [{ path: '/me', element: <MePage />, handle }, { path: '/login', element: <LoginPage />, handle }],
    }], { initialEntries: ['/me'] })
    const { queryClient } = renderRouter(router)
    expect(await screen.findByText('tester')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '退出登录' }))
    expect(await screen.findByText('登录页 null')).toBeInTheDocument()
    expect(getToken()).toBeNull()
    await waitFor(() => expect(queryClient.getQueryCache().getAll()).toHaveLength(0))
    expect(unauthenticatedCalls).toBe(0)
  })
})

describe('module hooks', () => {
  it('does not request medical reviews without consent', async () => {
    setToken(TEST_TOKEN)
    const consents = consentHandlers({ granted: { medical: false } })
    let reviewRequests = 0
    server.use(...consents.handlers, http.get('/api/medical/reviews', () => {
      reviewRequests += 1
      return HttpResponse.json([])
    }))
    const { wrapper } = withClient()
    const { result } = renderHook(() => ({ consents: useConsents(), caps: useCapabilities(), reviews: useMedicalReviews() }), { wrapper })
    await waitFor(() => expect(result.current.consents.data).toHaveLength(2))
    expect(result.current.caps.data?.medical).toBe(true)
    expect(result.current.reviews.fetchStatus).toBe('idle')
    expect(reviewRequests).toBe(0)

    // 同意之后才请求
    server.use(...consentHandlers().handlers)
    await act(async () => {
      await result.current.consents.refetch()
    })
    await waitFor(() => expect(result.current.reviews.isSuccess).toBe(true))
    expect(reviewRequests).toBe(1)
  })

  it('keeps a module ready when a background refetch of consents fails', async () => {
    setToken(TEST_TOKEN)
    server.use(...consentHandlers().handlers)
    const { wrapper } = withClient()
    const { result } = renderHook(() => {
      const consents = useConsents()
      return { failed: consents.isError, refetch: consents.refetch, status: useModuleConsent('cycle') }
    }, { wrapper })
    await waitFor(() => expect(result.current.status).toBe('ready'))
    server.use(http.get('/api/consents', () =>
      HttpResponse.json({ error: { code: 'internal_error', message: '服务器出错' } }, { status: 500 })))
    await act(async () => {
      await result.current.refetch()
    })
    await waitFor(() => expect(result.current.failed).toBe(true))
    expect(result.current.status).toBe('ready')
  })

  it('refreshes consents when a module answers consent required', async () => {
    setToken(TEST_TOKEN)
    server.use(...consentHandlers().handlers)
    const { wrapper } = withClient()
    const { result } = renderHook(() => ({ ready: useModuleReady('medical'), items: useMedicalItems() }), { wrapper })
    await waitFor(() => expect(result.current.items.isSuccess).toBe(true))
    expect(result.current.ready).toBe(true)
    // 在另一台设备上撤回了：医嘱接口回 403 consent_required，同意状态随之重新读取，模块不再可用
    server.use(
      ...consentHandlers({ granted: { medical: false } }).handlers,
      http.get('/api/medical/items', () =>
        HttpResponse.json({ error: { code: 'consent_required', message: '使用医嘱前，需要你单独同意处理医嘱与健康信息' } }, { status: 403 })),
    )
    await act(async () => {
      await result.current.items.refetch()
    })
    await waitFor(() => expect(result.current.ready).toBe(false))
  })
})

