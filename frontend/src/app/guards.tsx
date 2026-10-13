// 路由守卫：未登录 → 登录页；未确认免责 → 免责页；档案未填完 → 建档页；模块未开放 → 对话页。
// 判断全部来自后端（免责状态、档案、能力清单）。只要缓存里有数据就按它放行（后台刷新失败不打断页面）；
// 还没有数据时：请求中显示 BootSplash，失败显示后端的说明并可重试；登录失效（401）回登录页并带上“登录已过期”；
// 免责声明换了版本（档案或能力清单返回 403 disclaimer_not_accepted）时作废免责状态并去免责页。
import { useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { useEffect, type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { isSessionEnded } from '../api/client'
import { ApiError, asApiError } from '../api/errors'
import { useDisclaimerStatus } from '../api/hooks/disclaimer'
import { useCapabilities, useProfile } from '../api/hooks/profile'
import { qk } from '../api/keys'
import { getToken } from '../api/token'
import type { CapabilityKey } from '../api/types'
import { Field } from '../components/Field'
import { ErrorState } from '../components/states/ErrorState'
import { DISCLAIMER_NOT_ACCEPTED } from '../lib/contract'
import { BootSplash, useRemoveBootShell } from './BootSplash'
import { PATHS, onboardingPath } from './paths'
import { firstIncompleteStep, isProfileComplete } from './profile'

/** 跳到登录页时随 location.state 带上的内容：from 是被拦下的路径，expired 表示登录已过期 */
export interface LoginState {
  from?: string
  expired?: boolean
}


const sessionEnded = (error: unknown) => error instanceof ApiError && error.status === 401 && isSessionEnded(error.code)
/** 免责声明换了版本（或还没确认）：后端对业务接口答 403 disclaimer_not_accepted。守卫与外壳（变更出错时）共用 */
export const disclaimerOutdated = (error: unknown) =>
  error instanceof ApiError && error.status === 403 && error.code === DISCLAIMER_NOT_ACCEPTED


function GuardError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  useRemoveBootShell()
  const queryClient = useQueryClient()
  const from = useFrom()
  const outdated = disclaimerOutdated(error)
  useEffect(() => {
    // 缓存里的“已确认”已经过时：作废它，免责页之后的守卫会重新取
    if (outdated) void queryClient.invalidateQueries({ queryKey: qk.disclaimerStatus })
  }, [outdated, queryClient])
  if (sessionEnded(error)) {
    return <Navigate to={PATHS.login} replace state={{ expired: true } satisfies LoginState} />
  }
  if (outdated) return <Navigate to={PATHS.disclaimer} replace state={{ from }} />
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

/**
 * 还没有数据的查询怎么显示：有一个失败且不在重新请求就显示它的错误（重试会重新请求全部失败的），否则显示 BootSplash。
 * 返回 null 表示数据都到了。
 */
function pending(queries: UseQueryResult<unknown>[]): ReactNode {
  const missing = queries.filter((query) => query.data === undefined)
  if (missing.length === 0) return null
  const failed = missing.find((query) => query.isError && !query.isFetching)
  if (!failed) return <BootSplash />
  const retry = () => {
    for (const query of missing) if (query.isError) void query.refetch()
  }
  return <GuardError error={failed.error} onRetry={retry} />
}

export function RequireDisclaimer({ children }: { children?: ReactNode }) {
  const status = useDisclaimerStatus()
  const from = useFrom()
  if (status.data === undefined) return pending([status])
  if (!status.data.accepted) return <Navigate to={PATHS.disclaimer} replace state={{ from }} />
  return children ?? <Outlet />
}

/** 档案六项都填了才放行（第三步可跳过），否则去第一个没填完的建档步骤。外壳要用的能力清单也在这里一起取好。 */
export function RequireProfile({ children }: { children?: ReactNode }) {
  const profile = useProfile()
  const caps = useCapabilities()
  if (profile.data === undefined || caps.data === undefined) return pending([profile, caps])
  if (!isProfileComplete(profile.data)) {
    return <Navigate to={onboardingPath(firstIncompleteStep(profile.data))} replace />
  }
  return children ?? <Outlet />
}

/** 列出的模块全都没开放时回对话页（经期入口只对开放经期模块的用户显示）。 */
export function RequireCapability({ anyOf, children }: { anyOf: CapabilityKey[]; children?: ReactNode }) {
  const caps = useCapabilities()
  if (caps.data === undefined) return pending([caps])
  if (!anyOf.some((key) => caps.data[key])) return <Navigate to={PATHS.chat} replace />
  return children ?? <Outlet />
}
