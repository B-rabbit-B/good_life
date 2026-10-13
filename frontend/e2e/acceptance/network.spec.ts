// 两种设备上外网都被挡住：Chromium 由路由拦截 abort，WebKit 由死代理让请求失败（见 e2e/support/net.ts）；两边都记下被挡的地址。
import { expect, test } from '../support/test'

test('external requests fail and are recorded on this device', async ({ page, blockedRequests }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { level: 1, name: '登录' })).toBeVisible()
  expect(blockedRequests).toEqual([])
  const outcome = await page.evaluate(async () => {
    try {
      await fetch('https://example.com/blocked-by-e2e', { mode: 'no-cors' })
      return 'reached'
    } catch {
      return 'blocked'
    }
  })
  expect(outcome).toBe('blocked')
  expect(blockedRequests).toEqual(['https://example.com/blocked-by-e2e'])
})
