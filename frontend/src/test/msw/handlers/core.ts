// 守卫与外壳用到的四个接口（登录用户、免责状态、档案、能力清单），按后端的规则模拟：
// 没有令牌或令牌不对是 401；未确认免责时档案与能力清单是 403 disclaimer_not_accepted。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { Capabilities, ProfileOut } from '../../../api/types'
import { capabilities, completeProfile, disclaimerStatus, TEST_TOKEN, testUser } from '../../fixtures/core'

export interface CoreOptions {
  token?: string
  accepted?: boolean
  profile?: Partial<ProfileOut>
  capabilities?: Partial<Capabilities>
}

const error = (status: number, code: string, message: string) =>
  HttpResponse.json({ error: { code, message } }, { status })

export function coreHandlers(opts: CoreOptions = {}): HttpHandler[] {
  const { token = TEST_TOKEN, accepted = true } = opts
  const authed = (request: Request) => {
    const header = request.headers.get('Authorization')
    if (!header) return error(401, 'not_authenticated', '请先登录')
    if (header !== `Bearer ${token}`) return error(401, 'invalid_token', '登录已失效，请重新登录')
    return null
  }
  const business = (request: Request) =>
    authed(request) ?? (accepted ? null : error(403, 'disclaimer_not_accepted', '请先阅读并确认免责声明'))

  return [
    http.get('/api/auth/me', ({ request }) => authed(request) ?? HttpResponse.json(testUser())),
    http.get('/api/disclaimer/status', ({ request }) => authed(request) ?? HttpResponse.json(disclaimerStatus(accepted))),
    http.get('/api/profile', ({ request }) => business(request) ?? HttpResponse.json(completeProfile(opts.profile))),
    http.get('/api/me/capabilities', ({ request }) =>
      business(request) ?? HttpResponse.json(capabilities(opts.capabilities))),
  ]
}
