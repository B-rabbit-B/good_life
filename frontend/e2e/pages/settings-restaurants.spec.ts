// 附近餐厅与设置：390 与 360 两个宽度下，附近餐厅（拒绝定位后手动输入模拟高德认得的地点）导航瓷扣 56×56、需求胶囊 36 高带 data-hit44，
// 导航链接只断言 href（不真正打开）；允许定位时用浏览器给的坐标检索。添加模型服务（本地模拟模型）四步走到选择用途，步骤号圈 28；
// 密钥不对时密钥框是 2 像素朱色内描边。隐私与数据里切换“减少透明”后外壳的模糊随之关开。
// 每页都查触控目标、最小字号、横向滚动，有敏感区的页面查敏感区与遮盖。
import type { Page } from '@playwright/test'
import {
  expectCoverWorks, expectGlass, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas, expectTouchTargets,
} from '../support/a11y'
import { createUser, e2eInfo, MOCK_CITY, MOCK_PLACE, openAs, setLocationConsent } from '../support/api'
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

/** 第 1 步：自定义的 OpenAI 兼容格式、模拟模型的地址与给定的密钥，保存并获取模型 */
async function fillProvider(page: Page, baseUrl: string, key: string): Promise<void> {
  await page.getByLabel('类型').selectOption('kind:openai_compatible')
  await page.getByLabel('名称').fill('本地模拟模型')
  await page.getByLabel('服务地址').fill(baseUrl)
  await page.getByLabel('密钥', { exact: true }).fill(key)
  await page.getByRole('button', { name: '保存并获取模型' }).click()
}

test('walks the four model service steps and keeps the key out of the page', async ({ page, request }) => {
  const info = await e2eInfo(request)
  const { token } = await createUser(request)
  await openAs(page, token, '/settings/models/new')
  await expect(page.getByLabel('密钥', { exact: true })).toHaveAttribute('autocomplete', 'new-password')
  await expectPageRules(page)
  await fillProvider(page, info.model_base_url, info.model_key)
  const step3 = page.locator('[data-step="3"]')
  await step3.getByRole('button', { name: '测试连通' }).click()
  await expect(page.locator('[data-step="4"]').getByRole('button', { name: '保存用途' })).toBeVisible()
  for (const size of await box(page, '.fs-m')) expect(size).toEqual([28, 28])
  expect(await page.content()).not.toContain(info.model_key)
  const values = await page.locator('input, select, textarea').evaluateAll((els) => els.map((el) => (el as HTMLInputElement).value))
  expect(values).not.toContain(info.model_key)
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }))
  expect(stored).not.toContain(info.model_key)
  await expectPageRules(page)

  await page.getByRole('button', { name: '保存用途' }).click()
  await expect(page).toHaveURL(/\/settings\/models$/)
  await expect(page.getByRole('list', { name: '当前用途' })).toContainText(info.chat_model_id)
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)
})

test('outlines the key field in red when the key is refused', async ({ page, request }) => {
  const info = await e2eInfo(request)
  const { token } = await createUser(request)
  await openAs(page, token, '/settings/models/new')
  await fillProvider(page, info.model_base_url, info.bad_key)
  const key = page.getByLabel('密钥', { exact: true })
  await expect(key).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('错误码 llm_invalid_key')).toBeVisible()
  const shadow = await page.locator('.fld-i.bad').evaluate((el) => getComputedStyle(el).boxShadow)
  expect(shadow).toBe('rgb(179, 38, 30) 0px 0px 0px 2px inset')
  await expect(page.locator('[data-step="1"] .fs-m')).toHaveClass(/bad/)
  await expectPageRules(page)
})

test('switches reduce transparency from the privacy page', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/settings/privacy')
  const group = page.getByRole('radiogroup', { name: '减少透明' })
  await expect(group).toBeVisible()
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)

  await group.getByText('开', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'off')
  await page.goto('/me')
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expectGlass(page, false)

  await page.goto('/settings/privacy')
  await page.getByRole('radiogroup', { name: '减少透明' }).getByText('关', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'on')
  await page.goto('/me')
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expectGlass(page, true)
})
