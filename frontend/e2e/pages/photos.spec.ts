// 拍照识别与饮食记录：390 与 360 两个宽度下，从拍照页上传 meal.jpg（本地模拟看图模型认作麻婆豆腐加米饭），
// 识别结果页的操作坞（左右 8、下沿 18、主按钮 48）、把握五格（每格 6×8）、候选行（44 高），选候选后确认入库，
// 记录页的能量刻度（每格 25 千卡、需要线在面板内）与营养表进度条（4 像素圆头）；white.jpg 的“没有认出食物”；
// 减弱动效下刻度直接显示、计数直接是终值。每页都查触控目标、最小字号、横向滚动、敏感区与遮盖。
import type { Page } from '@playwright/test'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { components } from '../../src/api/schema'
import { fmtNum } from '../../src/lib/format'
import {
  expectBlurBudget, expectCoverWorks, expectGlass, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas,
  expectTouchTargets, waitForSheet,
} from '../support/a11y'
import {
  addPendingDish, confirmRecognition, createUser, e2eInfo, logMeal, openAs, recognizePhoto, seedModelService,
} from '../support/api'
import { expect, test } from '../support/test'

const FIXTURES = join(fileURLToPath(new URL('.', import.meta.url)), '..', '.fixtures')
const MEAL_JPG = join(FIXTURES, 'meal.jpg')
const WHITE_JPG = join(FIXTURES, 'white.jpg')
const RESULT_PATH = /\/photos\/[0-9a-f-]{36}$/

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

/** 操作坞：左右各 8、下沿 18；里面的主按钮 48 高；在 #shell-root 里 */
async function expectDock(page: Page): Promise<void> {
  const dock = page.locator('.stick')
  const box = await dock.boundingBox()
  const viewport = page.viewportSize()
  if (!box || !viewport) throw new Error('量不到操作坞')
  expect(box.x, '操作坞左边距').toBeCloseTo(8, 0)
  expect(viewport.width - (box.x + box.width), '操作坞右边距').toBeCloseTo(8, 0)
  expect(viewport.height - (box.y + box.height), '操作坞下边距').toBeCloseTo(18, 0)
  expect((await dock.locator('.btn-pri').boundingBox())?.height, '主按钮 48 高').toBeCloseTo(48, 0)
  expect(await dock.evaluate((el) => el.closest('#shell-root') !== null && el.closest('[data-scroller]') === null)).toBe(true)
}

async function photoUser(request: Parameters<typeof createUser>[0]): Promise<string> {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  return user.token
}

test('recognises a meal photo, picks a candidate and confirms it into the diary', async ({ page, request }) => {
  const token = await photoUser(request)
  await openAs(page, token, '/photos/new')
  await expect(page.getByRole('button', { name: '拍照' })).toBeVisible()
  await expectPageRules(page)

  // 从相册选 meal.jpg：识别完换成结果页
  await page.locator('input[type="file"]:not([capture])').setInputFiles(MEAL_JPG)
  await expect(page).toHaveURL(RESULT_PATH, { timeout: 30_000 })
  await expect(page.locator('.item-n>span', { hasText: '麻婆豆腐' })).toBeVisible()
  const id = new URL(page.url()).pathname.split('/').pop() ?? ''

  // 加一道营养库里只有相近名称的菜（卤猪肝），出现待确认项与候选
  const record = (await (await request.get(`/api/photos/recognitions/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as components['schemas']['RecognitionOut']
  await addPendingDish(request, token, record, { name: '卤猪肝', portion_text: '一小碟' })
  await page.reload()
  const confirm = page.getByRole('button', { name: '确认入库（还有 1 项待确认）' })
  await expect(confirm).toBeDisabled()

  await expectDock(page)
  for (const cell of await page.locator('.cells b').all()) {
    const box = await cell.boundingBox()
    expect([box?.width, box?.height], '把握格 6×8').toEqual([6, 8])
  }
  const candidates = page.locator('.cand')
  expect(await candidates.count()).toBeGreaterThan(0)
  for (const row of await candidates.all()) expect((await row.boundingBox())?.height, '候选行 44 高').toBeCloseTo(44, 0)
  await expect(page.locator('.item.flag').first()).toBeVisible()
  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectGlass(page, true)
  await expectBlurBudget(page)
  await expectCoverWorks(page)

  // 两个面板（修改一项、放弃这次识别）打开时，同屏模糊仍不超过视口的 40%
  for (const [open, title] of [['改个名字', '修改这一项'], ['放弃这次识别', '放弃这次识别']] as const) {
    await page.getByRole('button', { name: open }).click()
    const sheet = page.getByRole('dialog', { name: title })
    await expect(sheet).toBeVisible()
    await waitForSheet(page)
    await expectBlurBudget(page, { allowNone: true })
    await expectTouchTargets(page)
    await sheet.getByRole('button', { name: '取消' }).click()
    await expect(sheet).toHaveCount(0)
  }

  // 选候选：待确认项变成已匹配，确认入库可用
  await expect(page.getByRole('radiogroup', { name: '选择对应的食物' }).getByRole('radio').first()).toBeVisible()
  await candidates.first().click() // 点的是整行（单选框本身只给读屏）
  const ready = page.getByRole('button', { name: '确认入库' })
  await expect(ready).toBeEnabled()
  await page.getByLabel('餐次').selectOption('lunch')
  await ready.click()
  await expect(page).toHaveURL(/\/records\?tab=diet&date=\d{4}-\d{2}-\d{2}$/)
  await expect(page.getByText('来自拍照识别')).toBeVisible()
  await expect(page.getByText('麻婆豆腐', { exact: false }).first()).toBeVisible()
})

test('lays out the diary ledger, the nutrient bars and the meals', async ({ page, request }) => {
  const token = await photoUser(request)
  const record = await recognizePhoto(request, token, MEAL_JPG)
  await confirmRecognition(request, token, record.id, 'lunch')
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:111101x', grams: 50 })
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:101101x', grams: 250 })
  await openAs(page, token, '/records')

  const ledger = page.getByRole('img', { name: /今日能量/ })
  await expect(ledger).toBeVisible()
  const summary = (await (await request.get('/api/nutrition/summary', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as components['schemas']['SummaryOut']
  const total = summary.total.energy_kcal ?? 0
  const need = summary.needs.energy_kcal ?? 0
  // 每格 25 千卡
  await expect(ledger.locator('.lt-ticks i')).toHaveCount(Math.round(Math.max(total, need) / 25))
  // 需要线与“需要 N”都在面板内
  const panel = await page.locator('.ledger').boundingBox()
  const needLine = await ledger.locator('.lt-need').boundingBox()
  const needLabel = await ledger.locator('.lt-scale .need').boundingBox()
  if (!panel || !needLine || !needLabel) throw new Error('量不到能量账本')
  for (const box of [needLine, needLabel]) {
    expect(box.x, '需要线在面板内').toBeGreaterThanOrEqual(panel.x)
    expect(box.x + box.width, '需要线在面板内').toBeLessThanOrEqual(panel.x + panel.width)
  }
  // 营养表进度条：4 像素、圆头
  const bars = page.locator('.mt .bar')
  await expect(bars).toHaveCount(5)
  for (const bar of await bars.all()) {
    expect((await bar.boundingBox())?.height, '进度条 4 像素').toBeCloseTo(4, 0)
    expect(await bar.evaluate((el) => getComputedStyle(el).borderTopLeftRadius), '进度条圆头').toBe('999px')
  }
  await expect(page.getByText('来自拍照识别')).toBeVisible()
  await expect(page.getByRole('link', { name: '附近吃什么' })).toHaveAttribute('href', '/restaurants')

  await expectPageRules(page)
  await expectSensitiveAreas(page, ['ledger', 'nutrients', 'meals'])
  await page.locator('[data-scroller]').evaluate((el) => el.scrollTo({ top: el.scrollHeight }))
  await expectBlurBudget(page)
  await expectCoverWorks(page)
})

test('shows the ledger and the count at their final values under reduced motion', async ({ page, request }) => {
  const token = await photoUser(request)
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:061101x', grams: 400 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openAs(page, token, '/records')
  const ledger = page.getByRole('img', { name: /今日能量/ })
  await expect(ledger).toBeVisible()
  const summary = (await (await request.get('/api/nutrition/summary', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as components['schemas']['SummaryOut']
  const expected = fmtNum(summary.total.energy_kcal ?? 0, 1)
  // 数字一出现就是终值，不从 0 数上来
  await expect(page.locator('.ledger-big>.ns')).toHaveText(expected)
  const ticks = await ledger.locator('.lt-ticks i').evaluateAll((els) =>
    els.map((el) => ({ animation: getComputedStyle(el).animationName, transform: getComputedStyle(el).transform })))
  expect(ticks.length).toBeGreaterThan(0)
  for (const tick of ticks) expect(tick).toEqual({ animation: 'none', transform: 'none' })
})

test('shows the not food state for a white photo', async ({ page, request }) => {
  const token = await photoUser(request)
  await openAs(page, token, '/photos/new')
  await page.locator('input[type="file"]:not([capture])').setInputFiles(WHITE_JPG)
  await expect(page.getByRole('heading', { name: '没有认出食物' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('错误码 photo_not_food。这次没有产生识别记录。')).toBeVisible()
  await expect(page.getByRole('button', { name: '重拍' })).toBeVisible()
  await expect(page.getByRole('link', { name: '手动记一餐' })).toHaveAttribute('href', '/records/meals/new')
  await expectPageRules(page)
})
