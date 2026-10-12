import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { onTestFinished } from 'vitest'
import { clearToken, setToken } from '../api/token'
import type { Capabilities, ProfileOut } from '../api/types'
import { NETWORK_MODE } from '../app/queryClient'
import { routes } from '../app/routes'
import { CoverProvider } from '../components/cover'
import { GlassModeProvider } from '../components/glass/GlassModeProvider'
import { ToastProvider } from '../components/Toast'
import { TEST_TOKEN } from './fixtures/core'
import { coreHandlers } from './msw/handlers/core'
import { server } from './msw/server'

/** 与应用的查询客户端相同的网络模式（离线时照样发请求、报网络错误），只是不重试 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, networkMode: NETWORK_MODE },
      mutations: { retry: false, networkMode: NETWORK_MODE },
    },
  })
}

export function renderWithProviders(
  ui: ReactElement,
  { queryClient = createTestQueryClient(), ...options }: { queryClient?: QueryClient } & RenderOptions = {},
) {
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>, options),
  }
}

type AppRouter = ReturnType<typeof createMemoryRouter>

/** 测试期间在 body 里放一个 #shell-root（与 index.html 一样和 #root 同级），测试结束时移除。 */
function ensureShellRoot(): void {
  if (document.getElementById('shell-root')) return
  const shell = document.createElement('div')
  shell.id = 'shell-root'
  document.body.appendChild(shell)
  onTestFinished(() => shell.remove())
}

/** 用应用的全套 Provider（与 App.tsx 同序）渲染一个路由器。 */
export function renderRouter(router: AppRouter, queryClient: QueryClient = createTestQueryClient()) {
  ensureShellRoot()
  onTestFinished(() => router.dispose())
  const result = render(
    <QueryClientProvider client={queryClient}>
      <GlassModeProvider>
        <CoverProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </CoverProvider>
      </GlassModeProvider>
    </QueryClientProvider>,
  )
  return { ...result, router, queryClient }
}

/**
 * 按应用的真实路由表渲染 path，并装上守卫用的四个接口（登录用户、免责状态、档案、能力清单）。
 * token 默认是测试令牌，null 表示未登录；profile 与 capabilities 在完整的默认值上覆盖；accepted 默认 true。
 */
export function renderRoute(
  path: string,
  opts: { token?: string | null; capabilities?: Partial<Capabilities>; profile?: Partial<ProfileOut>; accepted?: boolean } = {},
): RenderResult & { router: AppRouter; queryClient: QueryClient } {
  const { token = TEST_TOKEN } = opts
  if (token === null) clearToken()
  else setToken(token)
  server.use(...coreHandlers({
    token: token ?? TEST_TOKEN, accepted: opts.accepted, profile: opts.profile, capabilities: opts.capabilities,
  }))
  return renderRouter(createMemoryRouter(routes, { initialEntries: [path] }))
}
