// 路由守卫：未登录 → 登录页；未确认免责 → 免责页；档案未填完 → 建档页；模块未开放 → 对话页。
// 判断全部来自后端（免责状态、档案、能力清单）；请求中显示 BootSplash，失败显示后端的说明并可重试，
// 登录失效（401）时回登录页并带上“登录已过期”。
import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { ApiError } from '../api/errors'
import { useDisclaimerStatus } from '../api/hooks/disclaimer'
import { useCapabilities, useProfile } from '../api/hooks/profile'
import { getToken } from '../api/token'
import type { CapabilityKey } from '../api/types'
import { Field } from '../components/Field'
import { ErrorState } from '../components/states/ErrorState'
import { BootSplash, useRemoveBootShell } from './BootSplash'
import { PATHS, onboardingPath } from './paths'
import { firstIncompleteStep, isProfileComplete } from './profile'

/** 跳到登录页时随 location.state 带上的内容：from 是被拦下的路径，expired 表示登录已过期 */
export interface LoginState {
  from?: string
  expired?: boolean
}

const SESSION_ENDED = new Set(['not_authenticated', 'invalid_token'])

const isSessionEnded = (error: unknown) =>
  error instanceof ApiError && error.status === 401 && SESSION_ENDED.has(error.code)

const asApiError = (error: unknown) =>
  error instanceof ApiError ? error : new ApiError(0, 'unknown_error', '出了点问题，请稍后再试')

function GuardError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  useRemoveBootShell()
  if (isSessionEnded(error)) {
    return <Navigate to={PATHS.login} replace state={{ expired: true } satisfies LoginState} />
  }
  return (
    <>
      <Field />
      <main className="guard-error">
        <ErrorState error={asApiError(error)} onRetry={onRetry} />
      </main>
    </>
  )
}

function useFrom(): string {
  const location = useLocation()
  return `${location.pathname}${location.search}`
}

/** 没有令牌就去登录页。令牌是否仍有效由后面守卫的请求发现（401 时回登录页）。 */
export function RequireAuth({ children }: { children?: ReactNode }) {
  const from = useFrom()
  if (!getToken()) return <Navigate to={PATHS.login} replace state={{ from } satisfies LoginState} />
  return children ?? <Outlet />
}

/** 登录页：已经有令牌就回首页。 */
export function GuestOnly({ children }: { children?: ReactNode }) {
  if (getToken()) return <Navigate to={PATHS.root} replace />
  return children ?? <Outlet />
}

export function RequireDisclaimer({ children }: { children?: ReactNode }) {
  const status = useDisclaimerStatus()
  const from = useFrom()
  if (status.isPending) return <BootSplash />
  if (status.isError) return <GuardError error={status.error} onRetry={() => void status.refetch()} />
  if (!status.data.accepted) return <Navigate to={PATHS.disclaimer} replace state={{ from }} />
  return children ?? <Outlet />
}

/** 档案六项都填了才放行（第三步可跳过），否则去第一个没填完的建档步骤。外壳要用的能力清单也在这里一起取好。 */
export function RequireProfile({ children }: { children?: ReactNode }) {
  const profile = useProfile()
  const caps = useCapabilities()
  const failed = profile.isError ? profile : caps.isError ? caps : null
  if (failed) {
    const retry = () => {
      if (profile.isError) void profile.refetch()
      if (caps.isError) void caps.refetch()
    }
    return <GuardError error={failed.error} onRetry={retry} />
  }
  if (!profile.data || !caps.data) return <BootSplash />
  if (!isProfileComplete(profile.data)) {
    return <Navigate to={onboardingPath(firstIncompleteStep(profile.data))} replace />
  }
  return children ?? <Outlet />
}

/** 列出的模块全都没开放时回对话页（经期入口只对开放经期模块的用户显示）。 */
export function RequireCapability({ anyOf, children }: { anyOf: CapabilityKey[]; children?: ReactNode }) {
  const caps = useCapabilities()
  if (caps.isPending) return <BootSplash />
  if (caps.isError) return <GuardError error={caps.error} onRetry={() => void caps.refetch()} />
  if (!anyOf.some((key) => caps.data[key])) return <Navigate to={PATHS.chat} replace />
  return children ?? <Outlet />
}
