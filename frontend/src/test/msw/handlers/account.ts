// 数据可控的三个接口，按后端的规则模拟：导出与删除账号都要重新输入密码，密码不是 password 时 403 password_incorrect；
// 导出返回压缩包（以 PK 开头），文件名在 Content-Disposition 里；删除账号要带 confirm true，成功 204；清空全部对话 204。
// 记下每次请求的请求体与地址（地址里不能有密码）；hold 兑现前删除账号不返回。
import { http, HttpResponse, type HttpHandler } from 'msw'
import { TEST_PASSWORD } from '../../fixtures/profile'

export const EXPORT_FILENAME = 'good-life-export-20261014.zip'
export const PASSWORD_INCORRECT_MESSAGE = '密码不正确，请重新输入'

const wrongPassword = () => HttpResponse.json(
  { error: { code: 'password_incorrect', message: PASSWORD_INCORRECT_MESSAGE } }, { status: 403 },
)

export function accountHandlers(opts: { password?: string; hold?: { delete?: Promise<void> } } = {}) {
  const password = opts.password ?? TEST_PASSWORD
  const record = {
    exports: [] as { body: unknown; url: string }[],
    deletes: [] as { body: unknown; url: string }[],
    clears: 0,
  }
  const handlers: HttpHandler[] = [
    http.post('/api/account/export', async ({ request }) => {
      const body = (await request.json()) as { password?: string }
      record.exports.push({ body, url: request.url })
      if (body.password !== password) return wrongPassword()
      return new HttpResponse(new Uint8Array([0x50, 0x4b, 3, 4, 0, 0]), {
        headers: {
          'Content-Type': 'application/zip', 'Content-Disposition': `attachment; filename="${EXPORT_FILENAME}"`,
          'Cache-Control': 'no-store',
        },
      })
    }),
    http.post('/api/account/delete', async ({ request }) => {
      const body = (await request.json()) as { password?: string; confirm?: boolean }
      record.deletes.push({ body, url: request.url })
      await opts.hold?.delete
      if (body.password !== password) return wrongPassword()
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete('/api/agent/conversations', () => {
      record.clears += 1
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { handlers, record }
}
