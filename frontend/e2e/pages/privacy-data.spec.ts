// 隐私与数据页的数据可控三块（导出、清空对话、删除账号）：390 与 360 两个宽度下查触控目标、最小字号、横向滚动与敏感区；
// 删除账号面板里勾选行 44 高、勾选与密码之前“删除账号”停用，打开时焦点不离开面板，关闭后回到触发按钮；
// 请求进行中（路由先扣住删除请求，用错误密码，账号不会真被删）面板锁住，按 Esc 不关。
import type { Page } from '@playwright/test'
import {
  expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas, expectTouchTargets, waitForSheet,
} from '../support/a11y'
import { createUser, openAs } from '../support/api'
import { expect, test } from '../support/test'

const ACK = '我知道删除后所有数据立即清除、不能恢复'

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

const focusInSheet = (page: Page) => page.evaluate(() => document.activeElement?.closest('.sheet') != null)

test('privacy page offers export, clearing and deletion within the touch and font rules', async ({ page, request }) => {
  const { token, password } = await createUser(request)
  await openAs(page, token, '/settings/privacy')
  for (const title of ['导出我的数据', '清空对话历史', '删除账号与全部数据']) {
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
  }
  await expectPageRules(page)
  await expectSensitiveAreas(page)

  // 删除账号面板：勾选行 44 高，勾选与密码都有了才能删除；焦点在面板里打转，关闭后回到触发按钮
  const section = page.getByRole('region', { name: '删除账号与全部数据' })
  const trigger = section.getByRole('button', { name: '删除账号' })
  await trigger.click()
  const sheet = page.getByRole('dialog', { name: '删除账号与全部数据' })
  await expect(sheet).toBeVisible()
  await waitForSheet(page)
  expect(await focusInSheet(page)).toBe(true)
  const ackBox = await sheet.locator('.chk').boundingBox()
  expect(ackBox?.height ?? 0).toBeGreaterThanOrEqual(44)
  const confirm = sheet.getByRole('button', { name: '删除账号' })
  await expect(confirm).toBeDisabled()
  await sheet.locator('.chk').click()
  await expect(sheet.getByRole('checkbox', { name: ACK })).toBeChecked()
  await expect(confirm).toBeDisabled()
  await sheet.getByLabel('登录密码').fill(`${password}-wrong`)
  await expect(confirm).toBeEnabled()
  await sheet.locator('.chk').click()
  await expect(confirm).toBeDisabled()
  await expectPageRules(page)
  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press('Tab')
    expect(await focusInSheet(page), '焦点离开了面板').toBe(true)
  }
  await sheet.getByRole('button', { name: '取消' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(trigger).toBeFocused()

  // 请求进行中：确认与取消都停用，Esc 不关；放行后密码不对写在密码框下，面板解锁
  let release: () => void = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/account/delete', async (route) => {
    await held
    await route.continue()
  })
  await trigger.click()
  await expect(sheet).toBeVisible()
  await waitForSheet(page)
  await sheet.getByLabel('登录密码').fill(`${password}-wrong`)
  await sheet.locator('.chk').click()
  await sheet.getByRole('button', { name: '删除账号' }).click()
  await expect(sheet.getByRole('button', { name: '删除账号' })).toHaveAttribute('aria-disabled', 'true')
  await expect(sheet.getByRole('button', { name: '取消' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(sheet).toBeVisible()
  release()
  await expect(sheet.getByText('错误码 password_incorrect')).toBeVisible()
  await expect(sheet.getByLabel('登录密码')).toHaveAttribute('aria-invalid', 'true')
  await expect(sheet.getByRole('button', { name: '取消' })).toBeEnabled()
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  await expect(page).toHaveURL(/\/settings\/privacy$/)

  // 导出与清空对话的面板同样守版式
  await page.getByRole('region', { name: '导出我的数据' }).getByRole('button', { name: '导出我的数据' }).click()
  await waitForSheet(page)
  await expect(page.getByRole('dialog', { name: '导出我的数据' }).getByRole('button', { name: '导出并下载' })).toBeDisabled()
  await expectPageRules(page)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('region', { name: '清空对话历史' }).getByRole('button', { name: '清空对话历史' }).click()
  await waitForSheet(page)
  await expectPageRules(page)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
