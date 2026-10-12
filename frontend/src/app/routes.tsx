// 路由表：页面全部按路由拆包（React Router 的 lazy）；守卫嵌套顺序 RequireAuth → RequireDisclaimer → RequireProfile → AppShell。
// 每个页面的 handle 写明底部怎么画（tabs 底部导航、chat 对话底座、none 都没有）与是否有敏感内容（DESIGN.md 第四节的表）。
import type { ComponentType } from 'react'
import { Navigate, type RouteObject } from 'react-router'
import { ApiError } from '../api/errors'
import { useCapabilities } from '../api/hooks/profile'
import type { NavItem } from '../components/BottomNav'
import { Field } from '../components/Field'
import { ErrorState } from '../components/states/ErrorState'
import { AppShell } from './AppShell'
import { BootSplash } from './BootSplash'
import { GuestOnly, RequireAuth, RequireCapability, RequireDisclaimer, RequireProfile } from './guards'
import { healthSegments } from './nav'
import { PATHS } from './paths'

export interface RouteHandle {
  nav: 'tabs' | 'chat' | 'none'
  navKey?: NavItem['key']
  sensitive: boolean
}

type PageModule = Promise<{ default: ComponentType }>
const page = (load: () => PageModule): RouteObject['lazy'] => async () => ({ Component: (await load()).default })

const handle = (nav: RouteHandle['nav'], sensitive: boolean, navKey?: NavItem['key']): RouteHandle =>
  navKey ? { nav, navKey, sensitive } : { nav, sensitive }

/** /health 打开第一个开放的分段；经期与医嘱都不开放时回对话页 */
function HealthRedirect() {
  const caps = useCapabilities()
  if (!caps.data) return <BootSplash />
  const [first] = healthSegments(caps.data)
  return <Navigate to={first === 'cycle' ? PATHS.cycle : first === 'medical' ? PATHS.medical : PATHS.chat} replace />
}

/** 路由出错（例如页面分包没能加载）时的整页说明 */
function RouteError() {
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
        children: [{ path: PATHS.login, lazy: page(() => import('../features/auth/LoginPage')), handle: handle('none', false) }],
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
            handle: handle('none', false),
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
                handle: handle('none', false),
              }],
            },
            {
              element: <RequireProfile />,
              children: [{
                element: <AppShell />,
                children: [
                  { path: PATHS.chat, lazy: page(() => import('../features/chat/ChatPage')), handle: handle('chat', true, 'chat') },
                  {
                    path: PATHS.health,
                    element: <HealthRedirect />,
                    handle: handle('tabs', true, 'health'),
                  },
                  {
                    element: <RequireCapability anyOf={['cycle']} />,
                    children: [{
                      path: PATHS.cycle,
                      lazy: page(() => import('../features/health/HealthPage')),
                      handle: handle('tabs', true, 'health'),
                    }],
                  },
                  {
                    element: <RequireCapability anyOf={['medical']} />,
                    children: [
                      {
                        path: PATHS.medical,
                        lazy: page(() => import('../features/health/HealthPage')),
                        handle: handle('tabs', true, 'health'),
                      },
                      {
                        path: PATHS.medicalNew,
                        lazy: page(() => import('../features/medical/MedicalNewPage')),
                        handle: handle('none', true),
                      },
                    ],
                  },
                  {
                    element: <RequireCapability anyOf={['nutrition', 'fitness']} />,
                    children: [{
                      path: PATHS.records,
                      lazy: page(() => import('../features/meals/RecordsPage')),
                      handle: handle('tabs', true, 'records'),
                    }],
                  },
                  {
                    element: <RequireCapability anyOf={['nutrition']} />,
                    children: [
                      {
                        path: PATHS.restaurants,
                        lazy: page(() => import('../features/restaurants/RestaurantsPage')),
                        handle: handle('none', true),
                      },
                      {
                        path: PATHS.photoNew,
                        lazy: page(() => import('../features/photos/PhotoNewPage')),
                        handle: handle('none', false),
                      },
                      {
                        path: PATHS.photoResult,
                        lazy: page(() => import('../features/photos/PhotoResultPage')),
                        handle: handle('none', true),
                      },
                      {
                        path: PATHS.mealNew,
                        lazy: page(() => import('../features/meals/MealNewPage')),
                        handle: handle('none', false),
                      },
                    ],
                  },
                  {
                    element: <RequireCapability anyOf={['fitness']} />,
                    children: [{
                      path: PATHS.workoutNew,
                      lazy: page(() => import('../features/fitness/WorkoutNewPage')),
                      handle: handle('none', false),
                    }],
                  },
                  { path: PATHS.me, lazy: page(() => import('../features/me/MePage')), handle: handle('tabs', true, 'me') },
                  {
                    path: PATHS.profileEdit,
                    lazy: page(() => import('../features/me/ProfileEditPage')),
                    handle: handle('none', true),
                  },
                  {
                    path: PATHS.models,
                    lazy: page(() => import('../features/settings/ModelsPage')),
                    handle: handle('none', false),
                  },
                  {
                    path: PATHS.modelNew,
                    lazy: page(() => import('../features/settings/ModelNewPage')),
                    handle: handle('none', false),
                  },
                  {
                    path: PATHS.privacy,
                    lazy: page(() => import('../features/settings/PrivacyPage')),
                    handle: handle('none', false),
                  },
                  {
                    path: PATHS.disclaimerView,
                    lazy: page(() => import('../features/settings/DisclaimerViewPage')),
                    handle: handle('none', false),
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
