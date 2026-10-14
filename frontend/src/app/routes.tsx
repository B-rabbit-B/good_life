// 路由表：页面全部按路由拆包（React Router 的 lazy）；守卫嵌套顺序 RequireAuth → RequireDisclaimer → RequireProfile → AppShell。
// 每个页面的 handle 写明底部怎么画（tabs 底部导航、chat 对话底座、none 都没有）；是否有敏感内容不在这里写，
// 由“本页有敏感区”登记表（sensitiveAreas.ts）推出，两处不会不一致。
import { useIsMutating, useQueryClient } from '@tanstack/react-query'
import type { ComponentType } from 'react'
import { Navigate, type RouteObject } from 'react-router'
import { ApiError } from '../api/errors'
import { PROFILE_UPDATE_KEY, useCapabilities } from '../api/hooks/profile'
import { qk } from '../api/keys'
import type { NavItem } from '../components/BottomNav'
import { Field } from '../components/Field'
import { ErrorState } from '../components/states/ErrorState'
import { AppShell } from './AppShell'
import { BootSplash, useRemoveBootShell } from './BootSplash'
import { GuestOnly, RequireAuth, RequireCapability, RequireDisclaimer, RequireProfile } from './guards'
import { healthSegments } from './nav'
import { PATHS, type PathKey } from './paths'
import { isSensitivePage } from './sensitiveAreas'

export interface RouteHandle {
  nav: 'tabs' | 'chat' | 'none'
  navKey?: NavItem['key']
  /** 这一页在敏感区登记表里（SENSITIVE_AREAS 有它的键）；没有底部导航的这类页面在页头右上角放遮盖按钮 */
  sensitive: boolean
}

type PageModule = Promise<{ default: ComponentType }>
const page = (load: () => PageModule): RouteObject['lazy'] => async () => ({ Component: (await load()).default })

const handle = (key: PathKey, nav: RouteHandle['nav'], navKey?: NavItem['key']): RouteHandle => {
  const sensitive = isSensitivePage(key)
  return navKey ? { nav, navKey, sensitive } : { nav, sensitive }
}

/**
 * /health 打开第一个开放的分段；经期与医嘱都不开放时回对话页。
 * 档案正在保存，或能力清单被作废后正在重取（例如刚关掉“经期记录”就点“健康”）时等新的结果：
 * 按旧清单跳到经期，新清单一到又会被送回对话页。平时数据过期引起的后台重取不等，直接按手上的清单跳转。
 */
function HealthRedirect() {
  const caps = useCapabilities()
  const queryClient = useQueryClient()
  const savingProfile = useIsMutating({ mutationKey: PROFILE_UPDATE_KEY }) > 0
  const refreshing = caps.isFetching && queryClient.getQueryState(qk.capabilities)?.isInvalidated === true
  if (!caps.data || refreshing || savingProfile) return <BootSplash />
  const [first] = healthSegments(caps.data)
  return <Navigate to={first === 'cycle' ? PATHS.cycle : first === 'medical' ? PATHS.medical : PATHS.chat} replace />
}

/** 路由出错（例如页面分包没能加载）时的整页说明；对话页的启动外壳要一起去掉，不能盖在说明上面 */
export function RouteError() {
  useRemoveBootShell()
  return (
    <>
      <Field />
      <main className="guard-error">
        <ErrorState
          error={new ApiError(0, 'page_load_failed', '页面没能加载，请检查网络后重试')}
          onRetry={() => window.location.reload()}
        />
      </main>
    </>
  )
}

// 组件样张页只在开发模式或 VITE_GALLERY=1（端到端构建）时注册；正式构建里这段连同它的分包一起去掉
const galleryRoutes: RouteObject[] = import.meta.env.DEV || import.meta.env.VITE_GALLERY === '1'
  ? [{
    path: PATHS.gallery,
    lazy: async () => ({ Component: (await import('../dev/GalleryPage')).GalleryPage }),
  }]
  : []

export const routes: RouteObject[] = [{
  ErrorBoundary: RouteError,
  HydrateFallback: BootSplash,
  children: [
    {
      element: <GuestOnly />,
      children: [{
        element: <AppShell />,
        children: [{ path: PATHS.login, lazy: page(() => import('../features/auth/LoginPage')), handle: handle('login', 'none') }],
      }],
    },
    {
      element: <RequireAuth />,
      children: [
        { path: PATHS.root, element: <Navigate to={PATHS.chat} replace /> },
        {
          element: <AppShell />,
          children: [{
            path: PATHS.disclaimer,
            lazy: page(() => import('../features/onboarding/DisclaimerPage')),
            handle: handle('disclaimer', 'none'),
          }],
        },
        {
          element: <RequireDisclaimer />,
          children: [
            {
              element: <AppShell />,
              children: [{
                path: PATHS.onboarding,
                lazy: page(() => import('../features/onboarding/OnboardingPage')),
                handle: handle('onboarding', 'none'),
              }],
            },
            {
              element: <RequireProfile />,
              children: [{
                element: <AppShell />,
                children: [
                  { path: PATHS.chat, lazy: page(() => import('../features/chat/ChatPage')), handle: handle('chat', 'chat', 'chat') },
                  {
                    path: PATHS.health,
                    element: <HealthRedirect />,
                    handle: handle('health', 'tabs', 'health'),
                  },
                  {
                    element: <RequireCapability anyOf={['cycle']} />,
                    children: [{
                      path: PATHS.cycle,
                      lazy: page(() => import('../features/health/HealthPage')),
                      handle: handle('cycle', 'tabs', 'health'),
                    }],
                  },
                  {
                    element: <RequireCapability anyOf={['medical']} />,
                    children: [
                      {
                        path: PATHS.medical,
                        lazy: page(() => import('../features/health/HealthPage')),
                        handle: handle('medical', 'tabs', 'health'),
                      },
                      {
                        path: PATHS.medicalNew,
                        lazy: page(() => import('../features/medical/MedicalNewPage')),
                        handle: handle('medicalNew', 'none'),
                      },
                    ],
                  },
                  {
                    element: <RequireCapability anyOf={['nutrition', 'fitness']} />,
                    children: [{
                      path: PATHS.records,
                      lazy: page(() => import('../features/meals/RecordsPage')),
                      handle: handle('records', 'tabs', 'records'),
                    }],
                  },
                  {
                    element: <RequireCapability anyOf={['nutrition']} />,
                    children: [
                      {
                        path: PATHS.restaurants,
                        lazy: page(() => import('../features/restaurants/RestaurantsPage')),
                        handle: handle('restaurants', 'none'),
                      },
                      {
                        path: PATHS.photoNew,
                        lazy: page(() => import('../features/photos/PhotoNewPage')),
                        handle: handle('photoNew', 'none'),
                      },
                      {
                        path: PATHS.photoResult,
                        lazy: page(() => import('../features/photos/PhotoResultPage')),
                        handle: handle('photoResult', 'none'),
                      },
                      {
                        path: PATHS.mealNew,
                        lazy: page(() => import('../features/meals/MealNewPage')),
                        handle: handle('mealNew', 'none'),
                      },
                    ],
                  },
                  {
                    element: <RequireCapability anyOf={['fitness']} />,
                    children: [{
                      path: PATHS.workoutNew,
                      lazy: page(() => import('../features/fitness/WorkoutNewPage')),
                      handle: handle('workoutNew', 'none'),
                    }],
                  },
                  { path: PATHS.me, lazy: page(() => import('../features/me/MePage')), handle: handle('me', 'tabs', 'me') },
                  {
                    path: PATHS.profileEdit,
                    lazy: page(() => import('../features/me/ProfileEditPage')),
                    handle: handle('profileEdit', 'none'),
                  },
                  {
                    path: PATHS.models,
                    lazy: page(() => import('../features/settings/ModelsPage')),
                    handle: handle('models', 'none'),
                  },
                  {
                    path: PATHS.modelNew,
                    lazy: page(() => import('../features/settings/ModelNewPage')),
                    handle: handle('modelNew', 'none'),
                  },
                  {
                    path: PATHS.privacy,
                    lazy: page(() => import('../features/settings/PrivacyPage')),
                    handle: handle('privacy', 'none'),
                  },
                  {
                    path: PATHS.disclaimerView,
                    lazy: page(() => import('../features/settings/DisclaimerViewPage')),
                    handle: handle('disclaimerView', 'none'),
                  },
                ],
              }],
            },
          ],
        },
      ],
    },
    ...galleryRoutes,
    { path: '*', element: <Navigate to={PATHS.root} replace /> },
  ],
}]
