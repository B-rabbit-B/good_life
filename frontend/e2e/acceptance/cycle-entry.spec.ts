// 验收标准 2：女性用户能看到经期页，男性用户看不到入口；女性关掉“经期记录”后入口同样消失。
import type { Page } from '@playwright/test'
import { createUser, openAs } from '../support/api'
import { snap } from '../support/flows'
import { expect, test } from '../support/test'

const NAV = '主导航'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

async function openHealthFromNav(page: Page): Promise<void> {
  const nav = page.getByRole('navigation', { name: NAV })
  await expect(nav.getByRole('link', { name: '健康' })).toBeVisible()
  await nav.getByRole('link', { name: '健康' }).click()
  await expect(page.getByRole('heading', { name: '健康', level: 1 })).toBeVisible()
}

/** 页面与导航上都没有“经期”，直接打开 /health/cycle 被送回对话页 */
async function expectNoCycleEntry(page: Page): Promise<void> {
  await expect(page.getByRole('tablist', { name: '健康分段' })).toHaveCount(0)
  await expect(page.getByRole('tablist', { name: '医嘱分类' })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('经期')
  await page.goto('/health/cycle')
  await expect(page).toHaveURL(/\/chat$/)
  await expect(page.getByRole('navigation', { name: NAV })).not.toContainText('经期')
}

test('a female user sees the cycle page', async ({ page, request }) => {
  const { token } = await createUser(request, { gender: 'female' })
  await openAs(page, token, '/chat')
  await openHealthFromNav(page)
  const segments = page.getByRole('tablist', { name: '健康分段' })
  await expect(segments.getByRole('tab', { name: '经期' })).toBeVisible()
  await segments.getByRole('tab', { name: '经期' }).click()
  await expect(page).toHaveURL(/\/health\/cycle$/)
  await expect(page.getByRole('grid', { name: /经期月历/ })).toBeVisible()
  await snap(page, 'cycle')
})

test('a male user never sees a cycle entry', async ({ page, request }) => {
  const { token } = await createUser(request, { gender: 'male' })
  await openAs(page, token, '/chat')
  await openHealthFromNav(page)
  await expect(page).toHaveURL(/\/health\/medical$/)
  await expectNoCycleEntry(page)
})

test('turning off cycle tracking hides the entry', async ({ page, request }) => {
  const { token } = await createUser(request, { gender: 'female' })
  await openAs(page, token, '/me')
  const toggle = page.getByRole('switch', { name: /经期记录/ })
  await expect(toggle).toBeChecked()
  await page.locator('.tg-row', { hasText: '经期记录' }).click()
  await expect(toggle).not.toBeChecked()
  await openHealthFromNav(page)
  await expect(page).toHaveURL(/\/health\/medical$/)
  await expectNoCycleEntry(page)
})
