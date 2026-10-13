// 应用外壳：浮起的底部导航（左右 8、下沿 18、高 60、最右 60 宽的遮盖格）、触控目标与横向滚动、
// 对话页首屏的累计布局偏移、按能力清单显隐的“健康”入口。
import type { Page } from '@playwright/test'
import { expectGlass, expectNoHorizontalScroll, expectTouchTargets } from '../support/a11y'
import { createUser, openAs } from '../support/api'
import { expect, test } from '../support/test'

const NAV = '主导航'
const COVER = '遮盖敏感内容'

async function expectFloatingNav(page: Page): Promise<void> {
  const nav = page.getByRole('navigation', { name: NAV })
  await expect(nav).toBeVisible()
  const box = await nav.boundingBox()
  const viewport = page.viewportSize()
  if (!box || !viewport) throw new Error('量不到导航或视口')
  expect(box.x, '导航左边距').toBeCloseTo(8, 0)
  expect(viewport.width - (box.x + box.width), '导航右边距').toBeCloseTo(8, 0)
  expect(viewport.height - (box.y + box.height), '导航下边距').toBeCloseTo(18, 0)
  expect(box.height, '导航高度').toBeCloseTo(60, 0)
  const cover = await nav.getByRole('button', { name: COVER }).boundingBox()
  expect(cover?.width, '遮盖格宽度').toBeCloseTo(60, 0)
  // 导航在 #shell-root 里，不在滚动容器里
  expect(await nav.evaluate((el) => el.closest('#shell-root') !== null && el.closest('[data-scroller]') === null)).toBe(true)
}

const navLabels = (page: Page) => page.getByRole('navigation', { name: NAV }).getByRole('link').allTextContents()

for (const [name, path, heading] of [['records', '/records', '记录'], ['me', '/me', '我的']] as const) {
  test(`floats the nav over the ${name} page`, async ({ page, request }) => {
    const user = await createUser(request, { profile: 'complete' })
    await openAs(page, user.token, path)
    await expect(page.getByRole('heading', { name: heading, level: 1 })).toBeVisible()
    await expectFloatingNav(page)
    await expect(page.getByRole('navigation', { name: NAV }).getByRole('link', { name: heading }))
      .toHaveAttribute('aria-current', 'page')
    await expectGlass(page, true)
    await expectTouchTargets(page)
    await expectNoHorizontalScroll(page)
  })
}

test('keeps the chat first paint stable', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await page.addInitScript(() => {
    const w = window as Window & { __cls?: number }
    w.__cls = 0
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) {
        if (!entry.hadRecentInput) w.__cls = (w.__cls ?? 0) + entry.value
      }
    }).observe({ type: 'layout-shift', buffered: true })
  })
  await openAs(page, user.token, '/chat')
  await expect(page.getByRole('heading', { name: '对话', level: 1 })).toBeVisible()
  await expect(page.locator('#boot-shell')).toHaveCount(0)
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  const cls = await page.evaluate(() => (window as Window & { __cls?: number }).__cls ?? 0)
  expect(cls, '累计布局偏移').toBeLessThanOrEqual(0.05)
})

test('shows health to a male user without the cycle segment', async ({ page, request }) => {
  const user = await createUser(request, { gender: 'male', profile: 'complete' })
  await openAs(page, user.token, '/records')
  await expect(page.getByRole('navigation', { name: NAV })).toBeVisible()
  expect(await navLabels(page)).toEqual(['对话', '记录', '健康', '我的'])
  await page.getByRole('navigation', { name: NAV }).getByRole('link', { name: '健康' }).click()
  await expect(page).toHaveURL(/\/health\/medical$/)
  await expect(page.getByRole('heading', { name: '健康', level: 1 })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('经期')
})

test('shows three nav items when health is closed', async ({ page, request }) => {
  const user = await createUser(request, { gender: 'male', profile: 'complete' })
  // 真实后端总是开放医嘱；这里只把能力清单的答复换掉，看三项导航的版式
  await page.route('**/api/me/capabilities', (route) =>
    route.fulfill({ json: { cycle: false, medical: false, nutrition: true, fitness: true } }))
  await openAs(page, user.token, '/me')
  await expect(page.getByRole('navigation', { name: NAV })).toBeVisible()
  expect(await navLabels(page)).toEqual(['对话', '记录', '我的'])
  await expectFloatingNav(page)
  await expectTouchTargets(page)
  await expectNoHorizontalScroll(page)
})
