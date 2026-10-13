// 附近餐厅与设置：390 与 360 两个宽度下，附近餐厅（拒绝定位后手动输入模拟高德认得的地点）导航瓷扣 56×56、需求胶囊 36 高带 data-hit44，
// 导航链接只断言 href（不真正打开）；允许定位时用浏览器给的坐标检索。每页都查触控目标、最小字号、横向滚动、敏感区与遮盖。
import type { Page } from '@playwright/test'
import {
  expectCoverWorks, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas, expectTouchTargets,
} from '../support/a11y'
import { createUser, MOCK_CITY, MOCK_PLACE, openAs, setLocationConsent } from '../support/api'
import { expect, test } from '../support/test'

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

const box = (page: Page, selector: string) => page.locator(selector).evaluateAll((els) => els.map((el) => {
  const rect = el.getBoundingClientRect()
  return [Math.round(rect.width), Math.round(rect.height)]
}))

test('searches a typed place after denying location and lays out the results', async ({ page, request }) => {
  const { token } = await createUser(request)
  await setLocationConsent(request, token, 'denied')
  await openAs(page, token, '/restaurants')
  await expect(page.getByText('没有开启定位，输入地名或地标即可，不会再请求定位。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '用一次你的位置？' })).toHaveCount(0)

  const chips = page.getByRole('group', { name: '需求' })
  await chips.getByRole('button', { name: '清淡' }).click()
  for (const [width, height] of await box(page, '.need button')) {
    expect(height).toBe(36)
    expect(width).toBeGreaterThanOrEqual(44)
  }
  expect(await page.locator('.need button:not([data-hit44])').count()).toBe(0)

  await page.getByLabel('地名或地标').fill(MOCK_PLACE)
  await page.getByLabel('城市（可不填）').fill(MOCK_CITY)
  await page.getByRole('button', { name: '查找附近的店' }).click()
  const list = page.getByRole('list', { name: '附近的店' })
  await expect(list).toBeVisible()
  await expect(page.getByText('到店可点与应避开是基于餐厅类别的一般性建议', { exact: false })).toBeVisible()

  const navs = list.locator('a.navb')
  expect(await navs.count()).toBeGreaterThan(0)
  for (const size of await box(page, 'a.navb')) expect(size).toEqual([56, 56])
  const first = navs.first()
  await expect(first).toHaveAttribute('target', '_blank')
  await expect(first).toHaveAttribute('rel', 'noopener noreferrer')
  expect(await first.getAttribute('href')).toMatch(/^https:\/\//)
  await expect(first).toHaveAttribute('aria-label', /^导航到/)

  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)
})

test('asks once and searches with the browser location after consent', async ({ page, request, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:8765' })
  await context.setGeolocation({ latitude: 39.9087, longitude: 116.4627 })
  const { token } = await createUser(request)
  await openAs(page, token, '/restaurants')
  await expect(page.getByRole('heading', { name: '用一次你的位置？' })).toBeVisible()
  await expectPageRules(page)
  await page.getByRole('button', { name: '允许定位' }).click()
  await expect(page.getByRole('list', { name: '附近的店' })).toBeVisible()
  await expect(page.getByText('按你现在的位置查找附近的店。')).toBeVisible()
  await expectPageRules(page)
  await expectSensitiveAreas(page, ['rememberArea'])

  // 再进一次：不再询问，直接按定位检索
  await page.reload()
  await expect(page.getByRole('list', { name: '附近的店' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '用一次你的位置？' })).toHaveCount(0)
})
