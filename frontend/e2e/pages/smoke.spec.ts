import { expect, test } from '@playwright/test'
import { blockExternal } from '../support/net'

test('serves the app shell at the root', async ({ page }) => {
  const response = await page.goto('/')
  expect(response?.status()).toBe(200)
  await expect(page.locator('#root')).toBeAttached()
  await expect(page.locator('#shell-root')).toBeAttached()
})

test('health endpoint is ok', async ({ request }) => {
  const response = await request.get('/api/health')
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok' })
})

test('unknown api path is a json 404', async ({ request }) => {
  const response = await request.get('/api/nope')
  expect(response.status()).toBe(404)
  expect(response.headers()['content-type']).toContain('application/json')
  const body = (await response.json()) as { error?: { code?: string } }
  expect(body.error?.code).toBe('http_error')
})

test('page only talks to the local server', async ({ page }) => {
  const hosts = new Set<string>()
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.protocol.startsWith('http')) hosts.add(url.hostname)
  })
  const blocked = await blockExternal(page)
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  expect(blocked).toEqual([])
  expect([...hosts]).toEqual(['127.0.0.1'])
})
