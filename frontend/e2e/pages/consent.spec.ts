// 单独同意：390 与 360 两个宽度下，没有同意过的用户第一次打开经期页、医嘱页与录入医嘱页时先看到同意面板
// （黑体标题、后端正文全文不截断、勾选行 44 高、勾选框 22 × 22，勾选“我已阅读并同意”之前同意按钮停用）；
// 同意之后直接进入模块，刷新后不再询问；“暂不使用”不进入模块。“我的”页撤回：勾选“我知道清除后不能恢复”之前确认按钮停用，
// 面板打开时 Tab 焦点不离开面板，“继续使用”关闭后焦点回到“撤回”按钮；撤回后再打开经期页又要同意。
// 每个面板都查触控目标、最小字号与横向滚动。
import type { Locator, Page } from '@playwright/test'
import { expectMinFontSize, expectNoHorizontalScroll, expectTouchTargets, waitForSheet } from '../support/a11y'
import { createUser, openAs } from '../support/api'
import { expect, test } from '../support/test'

const AGREE = '同意并开始使用'
const READ = '我已阅读并同意'

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

/** 勾选行整行不小于 44 高，勾选框 22 × 22 */
async function expectCheckRow(scope: Locator): Promise<void> {
  const box = await scope.locator('.chk .box').boundingBox()
  expect([box?.width, box?.height], '勾选框 22 × 22').toEqual([22, 22])
  expect((await scope.locator('.chk').boundingBox())?.height, '勾选整行').toBeGreaterThanOrEqual(44)
}

/** 同意面板：版式规则、勾选行尺寸、正文每段都完整显示（不省略、不裁切），勾选之前同意按钮停用 */
async function expectConsentPanel(page: Page, title: string): Promise<Locator> {
  const panel = page.locator('section.consent')
  await expect(panel.getByRole('heading', { name: title })).toBeVisible()
  await expect(panel.getByRole('button', { name: AGREE })).toBeDisabled()
  await expectPageRules(page)
  await expectCheckRow(panel)
  const clipped = await panel.locator('.cs-text p').evaluateAll((paragraphs) => paragraphs
    .filter((p) => {
      const style = getComputedStyle(p)
      return p.scrollWidth > p.clientWidth + 1 || p.scrollHeight > p.clientHeight + 1
        || style.textOverflow === 'ellipsis' || style.webkitLineClamp !== 'none'
    })
    .map((p) => p.textContent?.slice(0, 20) ?? ''))
  expect(clipped, '被截断的正文段落').toEqual([])
  expect(await panel.locator('.cs-text p').count(), '正文段落数').toBeGreaterThan(1)
  return panel
}

async function agree(panel: Locator): Promise<void> {
  // 点整行（原生勾选框只给读屏）
  await panel.locator('.chk').click()
  await expect(panel.getByRole('checkbox', { name: READ })).toBeChecked()
  await panel.getByRole('button', { name: AGREE }).click()
}

/** 连按 Tab 焦点一直在面板里 */
async function expectFocusTrapped(page: Page, dialog: Locator): Promise<void> {
  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press('Tab')
    expect(await dialog.evaluate((el) => el.contains(document.activeElement)), '焦点离开了面板').toBe(true)
  }
}

test('asks for consent once before the cycle page and remembers it', async ({ page, request }) => {
  const { token } = await createUser(request, { consents: false })
  await openAs(page, token, '/health/cycle')
  const panel = await expectConsentPanel(page, '单独同意：经期记录')
  await expect(page.locator('[data-sensitive-area="content"]')).toHaveCount(0)
  await agree(panel)
  await expect(page.locator('[data-sensitive-area="content"]')).toBeVisible()
  await expect(panel).toHaveCount(0)

  // 刷新后不再询问；“我的”页写着同意的日期，医嘱仍未同意
  await page.reload()
  await expect(page.locator('[data-sensitive-area="content"]')).toBeVisible()
  await expect(page.locator('section.consent')).toHaveCount(0)
  await page.goto('/me')
  const rows = page.getByRole('list', { name: '单独同意' }).getByRole('listitem')
  await expect(rows.nth(0)).toContainText(/^经期记录已同意（\d{4}-\d{2}-\d{2}）/)
  await expect(rows.nth(1)).toContainText('未同意')
  await expectPageRules(page)
})

test('asks for consent before the medical page and the new order page', async ({ page, request }) => {
  const { token } = await createUser(request, { consents: false })
  await openAs(page, token, '/health/medical')
  await expectConsentPanel(page, '单独同意：医嘱')
  await expect(page.getByRole('tablist', { name: '医嘱分类' })).toHaveCount(0)

  // 直接打开录入医嘱：同样先要同意；“暂不使用”不进入，直接打开时没有上一页，回到对话页
  await page.goto('/health/medical/new')
  const panel = await expectConsentPanel(page, '单独同意：医嘱')
  await expect(page.getByRole('heading', { name: '录入医嘱' })).toHaveCount(0)
  await panel.getByRole('button', { name: '暂不使用' }).click()
  await expect(page).toHaveURL(/\/chat$/)

  await page.goto('/health/medical/new')
  await agree(page.locator('section.consent'))
  await expect(page.getByRole('heading', { name: '录入医嘱' })).toBeVisible()
  await page.goto('/health/medical')
  await expect(page.getByRole('tablist', { name: '医嘱分类' })).toBeVisible()
  await expect(page.locator('section.consent')).toHaveCount(0)
})

test('withdraws a consent from the me page only after the acknowledgement', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/me')
  const row = page.getByRole('list', { name: '单独同意' }).getByRole('listitem').filter({ hasText: '经期记录' })
  const trigger = row.getByRole('button', { name: '撤回' })
  await trigger.click()
  const sheet = page.getByRole('dialog', { name: '撤回经期记录的单独同意' })
  await expect(sheet).toBeVisible()
  await waitForSheet(page)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectCheckRow(sheet)
  const confirm = sheet.getByRole('button', { name: '撤回并清除经期数据' })
  await expect(confirm).toBeDisabled()
  await expectFocusTrapped(page, sheet)
  // “继续使用”只关闭面板：焦点回到“撤回”，仍是已同意
  await sheet.getByRole('button', { name: '继续使用' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await expect(row).toContainText('已同意')

  await trigger.click()
  await sheet.locator('.chk').click()
  await expect(sheet.getByRole('checkbox', { name: '我知道清除后不能恢复' })).toBeChecked()
  await expect(confirm).toBeEnabled()
  await confirm.click()
  await expect(sheet).toHaveCount(0)
  await expect(row).toContainText('未同意')
  await expect(row.getByRole('button', { name: '撤回' })).toHaveCount(0)

  await page.goto('/health/cycle')
  await expectConsentPanel(page, '单独同意：经期记录')
})
