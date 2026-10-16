// 医嘱页：390 与 360 两个宽度下，三个子标签（每个点按区不小于 44、选中项下一枚 18 × 3 的钴蓝胶囊）、
// 待核对（头孢的原文提取出的条目）、生效中（待复核、带解除建议、没有建议三种）与历史与审计；
// 面板打开时只有面板一层模糊（导航与遮罩都不模糊）、Tab 焦点不离开面板、关闭后回到触发按钮；
// 确认生效与确认解除只能经面板里的按钮完成（解除要先勾选，勾选框 22 × 22、整行 44）；录入医嘱与证据上传。
// 每页都查触控目标、最小字号、横向滚动、敏感区与遮盖。
import type { APIRequestContext, Locator, Page } from '@playwright/test'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { components } from '../../src/api/schema'
import {
  expectCoverWorks, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas, expectTouchTargets, waitForSheet,
} from '../support/a11y'
import {
  CEFUROXIME_ORDER as CEFUROXIME, createUser, openAs, seedActiveItem, seedPendingOrder, seedProposal, seedReviewDueItem,
} from '../support/api'
import { expect, test } from '../support/test'

type ManualItem = components['schemas']['ManualItemCreate']

const FIXTURES = join(fileURLToPath(new URL('.', import.meta.url)), '..', '.fixtures')
const SALT: ManualItem = { category: 'diet_require', content: '低盐饮食，每日钠不超过 2000 毫克', subjects: ['盐'] }
const KNEE: ManualItem = { category: 'exercise_limit', content: '膝关节术后六周内避免跑跳', subjects: ['跑跳'] }
const PURINE: ManualItem = { category: 'diet_avoid', content: '避免动物内脏与浓肉汤（高嘌呤）', subjects: ['动物内脏', '浓肉汤'] }
const EXTRACTED = '服药期间及停药后 7 天内禁止饮酒'
const COBALT = 'rgb(31, 88, 168)'

async function medicalUser(request: APIRequestContext): Promise<string> {
  const user = await createUser(request, { profile: 'complete' })
  await seedPendingOrder(request, user.token, CEFUROXIME)
  await seedReviewDueItem(request, user.token, SALT)
  const knee = await seedActiveItem(request, user.token, KNEE)
  await seedProposal(request, user.token, knee.id, '用户转述医生说膝盖恢复得不错，可以开始慢跑了')
  await seedActiveItem(request, user.token, PURINE)
  return user.token
}

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

/** 子标签：每个点按区不小于 44；选中项下一枚 18 × 3 的钴蓝胶囊 */
async function expectTextTabs(page: Page): Promise<void> {
  const tabs = page.getByRole('tablist', { name: '医嘱分类' }).getByRole('tab')
  expect(await tabs.count()).toBe(3)
  for (const tab of await tabs.all()) {
    const box = await tab.boundingBox()
    expect(box?.height, '子标签高').toBeGreaterThanOrEqual(44)
    expect(box?.width, '子标签宽').toBeGreaterThanOrEqual(44)
  }
  const capsule = await page.locator('.ttabs.sm [aria-selected="true"]').evaluate((el) => {
    const after = getComputedStyle(el, '::after')
    return { width: after.width, height: after.height, color: after.backgroundColor, content: after.content }
  })
  expect(capsule).toEqual({ width: '18px', height: '3px', color: COBALT, content: '""' })
}

/** 面板打开时：只有面板一层可能模糊（高过视口 40% 时连它也是实色），导航与遮罩都不模糊 */
async function expectOnlySheetBlurs(page: Page): Promise<void> {
  const blurred = await page.evaluate(() => {
    const filterOf = (style: CSSStyleDeclaration) =>
      style.backdropFilter || (style as CSSStyleDeclaration & { webkitBackdropFilter?: string }).webkitBackdropFilter || 'none'
    const out: string[] = []
    for (const el of Array.from(document.querySelectorAll('*'))) {
      for (const pseudo of [null, '::before', '::after'] as const) {
        const filter = filterOf(getComputedStyle(el, pseudo))
        if (filter !== 'none' && !(el.classList.contains('sheet') && pseudo === null)) {
          out.push(`${el.tagName.toLowerCase()}.${el.className}${pseudo ?? ''}：${filter}`)
        }
      }
    }
    return out
  })
  expect(blurred, '面板以外的模糊层').toEqual([])
  for (const selector of ['.rnav', '.scrim']) {
    const filter = await page.locator(selector).first().evaluate((el) => getComputedStyle(el).backdropFilter || 'none')
    expect(filter, `${selector} 的模糊`).toBe('none')
  }
}

/** 连按 Tab 焦点一直在面板里 */
async function expectFocusTrapped(page: Page, dialog: Locator): Promise<void> {
  for (let i = 0; i < 16; i += 1) {
    await page.keyboard.press('Tab')
    expect(await dialog.evaluate((el) => el.contains(document.activeElement)), '焦点离开了面板').toBe(true)
  }
}

test('lays out the three medical tabs with the deck sizes and covers their content', async ({ page, request }) => {
  const token = await medicalUser(request)
  await openAs(page, token, '/health/medical?tab=active')
  await expect(page.locator('.mo-c', { hasText: SALT.content })).toBeVisible()
  await expect(page.getByText(/^待复核，已到复查日期/)).toBeVisible()
  // seedProposal 走的是本人的接口（来源 user），所以写“你提出了”
  await expect(page.getByText('你提出了一条解除建议')).toBeVisible()
  await expect(page.getByRole('tab', { name: '生效中 3' })).toBeVisible()
  // 同意守门放行、内容渲染完才核对敏感区
  await expect(page.locator('[data-sensitive]').first()).toBeVisible()
  await expectTextTabs(page)
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)

  await page.getByRole('tab', { name: /^待核对/ }).click()
  await expect(page).toHaveURL(/tab=pending/)
  await expect(page.locator('.fields dd', { hasText: EXTRACTED })).toBeVisible()
  await expect(page.getByText(/之后仍未确认，会自动作废$/)).toBeVisible()
  await expect(page.getByText('没有写明。确认后不设复查日期，可先补上')).toBeVisible()
  // 同意守门放行、内容渲染完才核对敏感区
  await expect(page.locator('[data-sensitive]').first()).toBeVisible()
  await expectTextTabs(page)
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)

  await page.getByRole('tab', { name: '历史与审计' }).click()
  await expect(page.getByRole('heading', { name: '审计记录' })).toBeVisible()
  await expect(page.locator('.audit li').first()).toBeVisible()
  // 系统事件（进入待复核）的时间是检查的时间，不是零点
  const due = page.locator('.audit li', { hasText: '进入待复核' })
  await expect(due).toContainText('来源：系统（打开应用时检查，已到复查日期，请确认是否还需要继续遵守）')
  await expect(due.locator('time')).not.toContainText('00:00')
  // 同意守门放行、内容渲染完才核对敏感区
  await expect(page.locator('[data-sensitive]').first()).toBeVisible()
  await expectTextTabs(page)
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)
})

test('confirms an extracted item only through the confirm sheet', async ({ page, request }) => {
  const token = await medicalUser(request)
  await openAs(page, token, '/health/medical?tab=pending')
  const item = page.locator('.mo', { has: page.locator('.fields dd', { hasText: EXTRACTED }) })
  const trigger = item.getByRole('button', { name: '确认生效' })
  await trigger.click()
  const sheet = page.getByRole('dialog', { name: '确认这条医嘱生效' })
  await expect(sheet).toBeVisible()
  await waitForSheet(page)
  await expect(sheet.getByText('医嘱只能在这里确认或解除，对话里无法完成。')).toBeVisible()
  await expectOnlySheetBlurs(page)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectFocusTrapped(page, sheet)
  // 不确认就关上：焦点回到触发按钮，条目仍待核对
  await sheet.getByRole('button', { name: '返回修改' }).click()
  const edit = page.getByRole('dialog', { name: '修改这条医嘱' })
  await expect(edit).toBeVisible()
  await edit.getByRole('button', { name: '取消' }).click()
  await expect(edit).toHaveCount(0)
  await expect(trigger).toBeFocused()

  await trigger.click()
  await expect(sheet).toBeVisible()
  await sheet.getByRole('button', { name: '确认生效' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.locator('.fields dd', { hasText: EXTRACTED })).toHaveCount(0)
  await page.getByRole('tab', { name: /^生效中/ }).click()
  await expect(page.locator('.mo-c', { hasText: EXTRACTED })).toBeVisible()
})

test('resolves only after the acknowledgement and moves the item to history', async ({ page, request }) => {
  const token = await medicalUser(request)
  await openAs(page, token, '/health/medical?tab=active')
  const row = page.locator('.mo', { has: page.locator('.mo-c', { hasText: PURINE.content }) })
  const trigger = row.getByRole('button', { name: '确认解除' })
  await trigger.click()
  const sheet = page.getByRole('dialog', { name: '确认解除这条医嘱' })
  await expect(sheet).toBeVisible()
  await waitForSheet(page)
  await expectOnlySheetBlurs(page)
  await expectTouchTargets(page)
  const box = await sheet.locator('.chk .box').boundingBox()
  expect([box?.width, box?.height], '勾选框 22 × 22').toEqual([22, 22])
  expect((await sheet.locator('.chk').boundingBox())?.height, '勾选整行').toBeGreaterThanOrEqual(44)
  const confirm = sheet.getByRole('button', { name: '确认解除' })
  await expect(confirm).toBeDisabled()
  await expectFocusTrapped(page, sheet)
  // 次按钮“取消”只关闭：焦点回到触发按钮
  await sheet.getByRole('button', { name: '取消' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(trigger).toBeFocused()

  await trigger.click()
  // 点整行（原生勾选框只给读屏）
  await sheet.locator('.chk').click()
  await expect(sheet.getByRole('checkbox', { name: '我知道解除后不能撤销，需要重新录入才能恢复这条约束' })).toBeChecked()
  await expect(confirm).toBeEnabled()
  await confirm.click()
  await expect(sheet.locator('[aria-live="assertive"]')).toHaveText(`已解除：${PURINE.content}。审计已记录。`)
  await expect(sheet).toHaveCount(0)
  await expect(row).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '生效中 2' })).toBeVisible()
  await page.getByRole('tab', { name: '历史与审计' }).click()
  const closed = page.locator('.closed', { hasText: PURINE.content })
  await expect(closed).toContainText('已解除')
  await expect(closed).toContainText('由你本人确认解除')
  await expect(page.locator('.audit li').first()).toContainText(`确认解除 ${PURINE.content}`)
})

test('enters an order with evidence and lands on the pending tab', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await openAs(page, user.token, '/health/medical/new')
  await expect(page.getByRole('heading', { name: '录入医嘱' })).toBeVisible()
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)

  await page.getByLabel('医嘱原文').fill(CEFUROXIME)
  await expect(page.getByText(`${CEFUROXIME.length} / 5000`)).toBeVisible()
  await page.locator('input[type="file"]:not([capture])').setInputFiles(join(FIXTURES, 'meal.jpg'))
  await expect(page.getByRole('list', { name: '证据' })).toContainText('meal.jpg')
  await expect(page.getByRole('list', { name: '证据' })).toContainText('，加密保存')
  await expectPageRules(page)
  await page.getByRole('button', { name: '提取条目' }).click()
  await expect(page).toHaveURL(/\/health\/medical\?tab=pending$/)
  const group = page.getByRole('region', { name: 'meal.jpg' })
  await expect(group.locator('.fields dd', { hasText: EXTRACTED })).toBeVisible()
  await group.getByRole('button', { name: '查看' }).click()
  const viewer = page.getByRole('dialog', { name: '原文与证据' })
  await expect(viewer.getByText(CEFUROXIME)).toBeVisible()
  await expect(viewer.getByRole('img', { name: 'meal.jpg' })).toBeVisible()
})
