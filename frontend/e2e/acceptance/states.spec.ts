// 验收标准 7：加载、失败、无数据、数据不足、需要授权（定位、未配置模型）与登录过期都有清晰提示。
import { createUser, localDate, openAs, seedPeriod, TOKEN_KEY } from '../support/api'
import { expect, test } from '../support/test'

const SUMMARY = '**/api/nutrition/summary*'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('loading shows a skeleton', async ({ page, request }) => {
  const { token } = await createUser(request)
  await page.route(SUMMARY, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.continue()
  })
  await openAs(page, token, '/records')
  const status = page.getByRole('status').filter({ hasText: '正在读取' })
  await expect(status).toBeVisible()
  await expect(page.locator('.ld .sk').first()).toBeVisible()
  await expect(page.getByRole('region', { name: '这天没有饮食记录' })).toBeVisible()
  await expect(status).toHaveCount(0)
})

test('a failure shows the backend message and retries', async ({ page, request }) => {
  const { token } = await createUser(request)
  let failing = true
  await page.route(SUMMARY, async (route) => {
    if (!failing) {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 502,
      json: { error: { code: 'upstream_unavailable', message: '营养服务暂时不可用，请稍后再试。', details: [] } },
    })
  })
  await openAs(page, token, '/records')
  const alert = page.getByRole('alert').filter({ hasText: '营养服务暂时不可用，请稍后再试。' })
  await expect(alert).toBeVisible({ timeout: 15_000 })
  await expect(alert.getByRole('heading', { name: '没能读取' })).toBeVisible()
  await expect(alert.getByText('错误码 upstream_unavailable')).toBeVisible()
  failing = false
  await alert.getByRole('button', { name: '重试' }).click()
  await expect(page.getByRole('region', { name: '这天没有饮食记录' })).toBeVisible()
  await expect(alert).toHaveCount(0)
})

test('an empty day says so with next steps', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/records')
  const empty = page.getByRole('region', { name: '这天没有饮食记录' })
  await expect(empty).toBeVisible()
  await expect(empty).toContainText('拍一张饭菜，或者手动记一餐。')
  await expect(empty.getByRole('link', { name: '拍照记录' })).toHaveAttribute('href', '/photos/new')
  await expect(empty.getByRole('link', { name: '手动记一餐' })).toHaveAttribute('href', /^\/records\/meals\/new\?date=/)
})

test('insufficient cycle data says so', async ({ page, request }) => {
  const { token } = await createUser(request, { gender: 'female' })
  await seedPeriod(request, token, localDate(-6), localDate(-2))
  await openAs(page, token, '/health/cycle')
  const state = page.getByRole('region', { name: '还不能预测下次经期' })
  await expect(state).toBeVisible()
  // 说明是后端预测接口给的原文，逐条照写
  const prediction = (await (await request.get('/api/cycle/prediction', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as { status: string; notes: string[] }
  expect(prediction.status).not.toBe('ok')
  expect(prediction.notes.length).toBeGreaterThan(0)
  await expect(state.locator('.st-p')).toHaveText(prediction.notes)
})

test('location needs consent once', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/restaurants')
  const ask = page.getByRole('region', { name: '用一次你的位置？' })
  await expect(ask).toBeVisible()
  await expect(ask.getByRole('button', { name: '允许定位' })).toBeVisible()
  await ask.getByRole('button', { name: '输入地点' }).click()
  await expect(ask).toHaveCount(0)
  await expect(page.getByLabel('地名或地标')).toBeVisible()
  // 再进一次不再询问
  await page.reload()
  await expect(page.getByText('没有开启定位，输入地名或地标即可，不会再请求定位。')).toBeVisible()
  await expect(page.getByRole('region', { name: '用一次你的位置？' })).toHaveCount(0)
})

test('no model is explained with a way out', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/chat')
  const state = page.getByRole('region', { name: '还没有可用的对话模型' })
  await expect(state).toBeVisible()
  await expect(state).toContainText('填地址与密钥')
  await state.getByRole('link', { name: '去添加模型服务' }).click()
  await expect(page).toHaveURL(/\/settings\/models\/new$/)
})

test('an expired session returns to login', async ({ page }) => {
  await page.goto('/login')
  await page.evaluate((key) => window.localStorage.setItem(key, 'not-a-valid-token'), TOKEN_KEY)
  await page.goto('/chat')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('region', { name: '登录已过期' })).toBeVisible()
  expect(await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_KEY)).toBeNull()
})
