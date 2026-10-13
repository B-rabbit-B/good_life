// 入口流程与“我的”：登录、免责、建档三步、我的、修改档案各页在 390 与 360 两个宽度下的触控目标、最小字号与横向滚动；
// 设计稿的几个尺寸（刻度尺容器宽、165 厘米时 160 的标签位置、分段每段 44、输入框 52 与聚焦描边）；我的与修改档案的遮盖。
import type { APIRequestContext, Page } from '@playwright/test'
import type { components } from '../../src/api/schema'
import {
  expectCoverWorks, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas, expectTouchTargets,
} from '../support/a11y'
import { createUser, openAs } from '../support/api'
import { expect, test } from '../support/test'

const PASSWORD = 'e2e-pass-123'
const ACCENT_RING = /rgb\(31, 88, 168\) 0px 0px 0px 2px inset/
/** 设计稿：刻度尺放在瓷胎面板里，容器宽 = 视口 − 面板外边 12 × 2 − 内边 16 × 2 */
const RULER_WIDTH = { 360: 304, 390: 334 } as const

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

const viewportWidth = (page: Page) => {
  const width = page.viewportSize()?.width
  if (width !== 360 && width !== 390) throw new Error(`没有为宽度 ${String(width)} 定义尺寸`)
  return width
}

const heights = (page: Page, selector: string) =>
  page.locator(selector).evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height))

async function patchProfile(request: APIRequestContext, token: string, data: components['schemas']['ProfileUpdate']) {
  const response = await request.patch('/api/profile', { headers: { Authorization: `Bearer ${token}` }, data })
  expect(response.ok(), await response.text()).toBe(true)
}

test('a new user registers, accepts the disclaimer and fills the profile', async ({ page }) => {
  const width = viewportWidth(page)
  const username = `n${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`

  // 01 登录与注册
  await page.goto('/login')
  await expect(page.getByRole('heading', { level: 1, name: '登录' })).toBeVisible()
  await expectPageRules(page)
  expect(await heights(page, '.ttab'), '分段控件每段 44').toEqual([44, 44])
  const usernameBox = page.locator('.fld-i').first()
  expect((await usernameBox.boundingBox())?.height, '输入框 52').toBe(52)
  await page.getByLabel('用户名').focus()
  await expect(usernameBox, '聚焦时 2 像素钴蓝内描边').toHaveCSS('box-shadow', ACCENT_RING)

  await page.getByRole('tab', { name: '注册' }).click()
  await expect(page.getByRole('heading', { level: 1, name: '注册' })).toBeVisible()
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(PASSWORD)
  await expectPageRules(page)
  await page.getByRole('button', { name: '注册并继续' }).click()

  // 01b 免责声明：没有返回键，勾选后才能确认
  await expect(page).toHaveURL(/\/disclaimer$/)
  await expect(page.getByRole('heading', { level: 1, name: '免责声明' })).toBeVisible()
  await expect(page.getByRole('listitem').first()).toBeVisible()
  await expect(page.getByRole('button', { name: '返回' })).toHaveCount(0)
  await expectPageRules(page)
  const confirm = page.getByRole('button', { name: '确认并继续' })
  await expect(confirm).toBeDisabled()
  await page.getByText('我已阅读并理解以上内容').click()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  // 02 建档第 1 步
  await expect(page).toHaveURL(/\/onboarding\/1$/)
  await expect(page.getByRole('heading', { level: 1, name: '基本信息' })).toBeVisible()
  await expectPageRules(page)
  const height = page.getByRole('slider', { name: '身高' })
  await expect(height).toHaveAttribute('aria-valuetext', '165 厘米')
  const ruler = await height.boundingBox()
  expect(ruler?.width, '刻度尺容器宽').toBe(RULER_WIDTH[width])
  expect((await page.getByRole('slider', { name: '体重' }).boundingBox())?.width).toBe(RULER_WIDTH[width])
  const offset = await height.evaluate((el) => {
    const needle = el.querySelector('.needle')?.getBoundingClientRect()
    const label = Array.from(el.querySelectorAll('span')).find((span) => span.textContent === '160')?.getBoundingClientRect()
    if (!needle || !label) return null
    return (needle.left + needle.width / 2) - (label.left + label.width / 2)
  })
  expect(offset, '165 厘米时 160 的标签中心在指针左边 40 像素').not.toBeNull()
  expect(offset ?? 0).toBeCloseTo(40, 0)
  expect(await heights(page, '.opt'), '性别分段每段 44').toEqual([44, 44, 44])

  await page.getByLabel('出生年份').selectOption('1993')
  await page.locator('.opt', { hasText: '女' }).click()
  await page.getByRole('button', { name: '下一步' }).click()

  // 第 2 步：活动与目标
  await expect(page).toHaveURL(/\/onboarding\/2$/)
  await expect(page.getByRole('heading', { level: 1, name: '活动与目标' })).toBeVisible()
  await expectPageRules(page)
  expect(await heights(page, '.opt'), '目标分段每段 44').toEqual([44, 44, 44, 44])
  await page.locator('.act', { hasText: '轻度' }).click()
  await page.locator('.opt', { hasText: '维持' }).click()
  await page.getByRole('button', { name: '下一步' }).click()

  // 第 3 步：饮食偏好与忌口
  await expect(page).toHaveURL(/\/onboarding\/3$/)
  await expect(page.getByRole('heading', { level: 1, name: '饮食偏好与忌口' })).toBeVisible()
  const avoid = page.locator('.fld', { has: page.locator('.fld-l', { hasText: '忌口' }) })
  await avoid.getByRole('button', { name: '添加' }).click()
  await page.getByLabel('添加忌口').fill('酒精')
  await page.getByLabel('添加忌口').press('Enter')
  await expect(avoid.getByRole('button', { name: '移除酒精' })).toBeVisible()
  await expectPageRules(page)
  await page.getByRole('button', { name: '完成' }).click()
  await expect(page).toHaveURL(/\/chat$/)
})

test('the me page meets the layout rules and covers the profile', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await patchProfile(request, user.token, { food_avoidances: ['动物内脏', '酒精'], health_conditions: '膝关节半月板术后' })
  await openAs(page, user.token, '/me')
  await expect(page.getByRole('heading', { level: 1, name: '我的' })).toBeVisible()
  await expect(page.getByRole('switch', { name: /经期记录/ })).toBeVisible()
  await expect(page.getByText('未设置')).toBeVisible()
  // 两个开关各自等自己的接口（档案与助手设置），量之前等两行都出来
  await expect(page.locator('.tg-row')).toHaveCount(2)
  await expectPageRules(page)
  expect(await heights(page, '.tg-row'), '开关整行 56').toEqual([56, 56])
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)
})

test('the profile edit page meets the layout rules, covers and saves', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await openAs(page, user.token, '/me/profile')
  await expect(page.getByRole('heading', { level: 1, name: '个人档案' })).toBeVisible()
  await expect(page.getByLabel('体重')).toHaveValue('54')
  await expectPageRules(page)
  expect(await heights(page, '.fld-i'), '输入框 52').toEqual([52, 52])
  expect(await heights(page, '.opt'), '目标分段每段 44').toEqual([44, 44, 44, 44])
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)

  await page.getByLabel('体重').fill('55.5')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page).toHaveURL(/\/me$/)
  await expect(page.getByText('已保存')).toBeVisible()
  await expect(page.locator('[data-sensitive-area="profile"]')).toContainText('55.5')
})
