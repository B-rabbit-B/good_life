// 入口流程的接口：注册、登录、退出、免责正文与确认，以及建档与“我的”页测试用的可变档案。
// 规则照后端：注册 201（没有确认年满 14 周岁时 422 validation_error）；登录失败 401 invalid_credentials；
// 确认的版本不是当前版本时 409 disclaimer_outdated。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { Capabilities, ProfileOut, ProfileUpdate, RegisterRequest } from '../../../api/types'
import { DISCLAIMER_VERSION, TEST_TOKEN, testUser } from '../../fixtures/core'
import { disclaimerText } from '../../fixtures/profile'

const error = (status: number, code: string, message: string) =>
  HttpResponse.json({ error: { code, message } }, { status })

const authed = (request: Request) => {
  const header = request.headers.get('Authorization')
  if (!header) return error(401, 'not_authenticated', '请先登录')
  if (header !== `Bearer ${TEST_TOKEN}`) return error(401, 'invalid_token', '登录已失效，请重新登录')
  return null
}

export function authHandlers(): HttpHandler[] {
  return [
    http.post('/api/auth/register', async ({ request }) => {
      const body = (await request.json()) as RegisterRequest
      if (body.age_confirmed !== true) {
        return HttpResponse.json({
          error: {
            code: 'validation_error',
            message: '请求参数不合法',
            details: [{ field: 'age_confirmed', message: '请确认你已年满 14 周岁', type: 'value_error' }],
          },
        }, { status: 422 })
      }
      return HttpResponse.json(testUser({ username: body.username.toLowerCase() }), { status: 201 })
    }),
    http.post('/api/auth/login', () => HttpResponse.json({ access_token: TEST_TOKEN, token_type: 'bearer' })),
    http.post('/api/auth/logout', ({ request }) => authed(request) ?? new HttpResponse(null, { status: 204 })),
    http.get('/api/disclaimer', () => HttpResponse.json(disclaimerText())),
    http.post('/api/disclaimer/accept', async ({ request }) => {
      const denied = authed(request)
      if (denied) return denied
      const { version } = (await request.json()) as { version: string }
      if (version !== DISCLAIMER_VERSION) {
        return error(409, 'disclaimer_outdated', '免责声明已更新，请重新阅读最新版本后确认')
      }
      return HttpResponse.json({ current_version: DISCLAIMER_VERSION, accepted: true, accepted_at: '2026-10-12T08:00:00Z' })
    }),
  ]
}

/**
 * 一份会被 PATCH 改写的档案：GET 与 PATCH /api/profile、GET /api/me/capabilities（照后端的规则：经期只对女性且没有关闭经期记录时开放）。
 * fixed 固定其余模块的开放情况（例如医嘱不开放，用来看三项导航）。
 * patches 按顺序记下每次 PATCH 的请求体。要在 renderRoute 之后 server.use(...store.handlers)。
 */
export function profileStore(initial: ProfileOut, fixed: Partial<Omit<Capabilities, 'cycle'>> = {}) {
  let profile = initial
  const patches: ProfileUpdate[] = []
  const caps = (): Capabilities => ({
    medical: true, nutrition: true, fitness: true, ...fixed,
    cycle: profile.gender === 'female' && !profile.cycle_tracking_opt_out,
  })
  const handlers: HttpHandler[] = [
    http.get('/api/profile', ({ request }) => authed(request) ?? HttpResponse.json(profile)),
    http.patch('/api/profile', async ({ request }) => {
      const denied = authed(request)
      if (denied) return denied
      const body = (await request.json()) as ProfileUpdate
      patches.push(body)
      profile = { ...profile, ...body } as ProfileOut
      return HttpResponse.json(profile)
    }),
    http.get('/api/me/capabilities', ({ request }) => authed(request) ?? HttpResponse.json(caps())),
  ]
  return { handlers, patches, current: () => profile }
}
