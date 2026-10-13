// 验收标准 4：待复核的医嘱在打开应用时得到提示，可以继续遵守，也可以到医嘱页确认解除；“稍后”把开场收进待处理条。
import type { APIRequestContext, Page } from '@playwright/test'
import type { components } from '../../src/api/schema'
import { createUser, e2eInfo, openAs, seedModelService, seedReviewDueItem } from '../support/api'
import { snap } from '../support/flows'
import { expect, test } from '../support/test'

type ManualItem = components['schemas']['ManualItemCreate']
type MedicalItem = components['schemas']['app__medical__schemas__ItemOut']

const SALT: ManualItem = { category: 'diet_require', content: '低盐饮食，每日钠不超过 2000 毫克', subjects: ['盐'] }
const ACK = '我知道解除后不能撤销，需要重新录入才能恢复这条约束'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

async function dueUser(request: APIRequestContext): Promise<{ token: string; item: MedicalItem }> {
  const { token } = await createUser(request)
  await seedModelService(request, token, await e2eInfo(request))
  const item = await seedReviewDueItem(request, token, SALT)
  return { token, item }
}

/** 打开应用（/）：落到对话页，开场卡片问的就是这一条 */
async function openApp(page: Page, token: string) {
  await openAs(page, token, '/')
  await expect(page).toHaveURL(/\/chat$/)
  const card = page.getByRole('group', { name: /你有一条医嘱/ })
  await expect(card).toBeVisible()
  await expect(card).toContainText(SALT.content)
  return card
}

async function itemOf(request: APIRequestContext, token: string, id: string): Promise<MedicalItem> {
  const response = await request.get(`/api/medical/items/${id}`, { headers: { Authorization: `Bearer ${token}` } })
  return (await response.json()) as MedicalItem
}

test('a due item is raised when the app opens and can be continued', async ({ page, request }) => {
  const { token, item } = await dueUser(request)
  const card = await openApp(page, token)
  await snap(page, 'opening-card')
  await card.getByRole('button', { name: '继续遵守' }).click()
  const sheet = page.getByRole('dialog', { name: '继续遵守这条医嘱' })
  await expect(sheet).toBeVisible()
  // 两个日期都在：复查日期预填 1 个月后，预计结束原来没有设
  await expect(sheet.getByLabel('复查日期', { exact: true })).not.toHaveValue('')
  await expect(sheet.getByLabel('预计结束', { exact: true })).toBeAttached()
  await expect(sheet.getByText('原来没有设，表示长期有效')).toBeVisible()
  await snap(page, 'continue-sheet')
  await sheet.getByRole('button', { name: '继续遵守' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已继续遵守')).toBeVisible()
  await expect(card).toHaveCount(0)
  await expect(page.getByRole('button', { name: /待复核/ })).toHaveCount(0)
  expect((await itemOf(request, token, item.id)).status).toBe('active')
})

test('a due item can be resolved from the medical page', async ({ page, request }) => {
  const { token, item } = await dueUser(request)
  const card = await openApp(page, token)
  await card.getByRole('button', { name: '去医嘱页处理' }).click()
  await expect(page).toHaveURL(/\/health\/medical\?tab=active$/)
  await expect(page.getByRole('tab', { name: /^生效中/ })).toHaveAttribute('aria-selected', 'true')
  const row = page.locator('.mo', { has: page.locator('.mo-c', { hasText: SALT.content }) })
  await row.getByRole('button', { name: '确认解除' }).click()
  const sheet = page.getByRole('dialog', { name: '确认解除这条医嘱' })
  const confirm = sheet.getByRole('button', { name: '确认解除' })
  await expect(confirm).toBeDisabled()
  await sheet.locator('.chk').click()
  await expect(sheet.getByRole('checkbox', { name: ACK })).toBeChecked()
  await confirm.click()
  await expect(sheet).toHaveCount(0)
  await expect(row).toHaveCount(0)
  expect((await itemOf(request, token, item.id)).status).toBe('resolved')
})

test('later collapses the opening into the strip', async ({ page, request }) => {
  const { token } = await dueUser(request)
  const card = await openApp(page, token)
  // 卡片显示时，这一条不再重复出现在待处理条里
  const strip = page.getByRole('button', { name: /待复核$/ })
  await expect(strip).toHaveCount(0)
  await card.getByRole('button', { name: '稍后' }).click()
  await expect(card).toHaveCount(0)
  await expect(strip).toBeVisible()
  await strip.click()
  await expect(page.locator('.rvx')).toContainText(SALT.content)
  await expect(page.locator('.rvx').getByRole('button', { name: '继续遵守' })).toBeVisible()
})
