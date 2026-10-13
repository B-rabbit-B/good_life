// 两种设备上外网都被挡住：Chromium 由路由拦截 abort，WebKit 由死代理让请求失败（见 e2e/support/net.ts）；
// fetch、图片与 wss 三种请求都失败，并且都记进 blockedRequests。
import { expect, test } from '../support/test'

const FETCH_URL = 'https://example.com/blocked-by-e2e'
const IMAGE_URL = 'http://example.com/blocked-by-e2e.png'
const SOCKET_URL = 'wss://example.com/blocked-by-e2e'

test('external requests fail and are recorded on this device', async ({ page, blockedRequests }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { level: 1, name: '登录' })).toBeVisible()
  expect(blockedRequests).toEqual([])

  const outcome = await page.evaluate(async ({ fetchUrl, imageUrl, socketUrl }) => {
    const fetched = await fetch(fetchUrl, { mode: 'no-cors' }).then(() => 'reached', () => 'blocked')
    const image = await new Promise<string>((resolve) => {
      const img = new Image()
      img.onload = () => resolve('reached')
      img.onerror = () => resolve('blocked')
      img.src = imageUrl
    })
    const socket = await new Promise<string>((resolve) => {
      const ws = new WebSocket(socketUrl)
      ws.onopen = () => {
        ws.close()
        resolve('reached')
      }
      ws.onerror = () => resolve('blocked')
      ws.onclose = () => resolve('blocked')
    })
    return { fetched, image, socket }
  }, { fetchUrl: FETCH_URL, imageUrl: IMAGE_URL, socketUrl: SOCKET_URL })

  expect(outcome).toEqual({ fetched: 'blocked', image: 'blocked', socket: 'blocked' })
  await expect.poll(() => [...blockedRequests].sort()).toEqual([FETCH_URL, IMAGE_URL, SOCKET_URL].sort())
})
