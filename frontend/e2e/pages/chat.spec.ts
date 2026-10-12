// 对话页：390 与 360 两个宽度下的对话底座（左右 8、下沿 18、高 158）、快捷胶囊 36 高带 data-hit44、输入框 44、
// 两种气泡的圆角、就医提示出血到屏幕边且直角、页头吸顶后出现玻璃、模糊面积不超过视口 40%、触控目标与最小字号、
// 遮盖（就医提示四角不漏朱色）、玻璃开与关；开场卡片、待处理条与继续遵守面板。
import type { APIRequestContext, Page } from '@playwright/test'
import type { components } from '../../src/api/schema'
import {
  expectBlurBudget, expectCoverWorks, expectForcedColorsSmoke, expectGlass, expectMinFontSize, expectNoHorizontalScroll,
  expectSensitiveAreas, expectTouchTargets, waitForSheet,
} from '../support/a11y'
import {
  createUser, e2eInfo, openAs, seedActiveItem, seedModelService, seedProposal, seedReviewDueItem, sendMessage,
} from '../support/api'
import { samplePixels } from '../support/pixels'
import { expect, test } from '../support/test'

type ManualItem = components['schemas']['ManualItemCreate']

const SALT: ManualItem = { category: 'diet_require', content: '低盐饮食，每日钠不超过 2000 毫克', subjects: ['盐'] }
const KNEE: ManualItem = { category: 'exercise_limit', content: '膝关节术后六周内避免跑跳', subjects: ['跑跳'] }
const SPICY: ManualItem = { category: 'diet_avoid', content: '两周内忌食辛辣', subjects: ['辛辣'] }
const REDUCE_KEY = 'goodlife.reduceTransparency'

async function chatUser(request: APIRequestContext, history: string[] = []): Promise<string> {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  let conversation: string | undefined
  for (const text of history) conversation = (await sendMessage(request, user.token, text, conversation)).conversation_id
  return user.token
}

async function send(page: Page, text: string): Promise<void> {
  await page.getByRole('textbox', { name: '给助手发消息' }).fill(text)
  // 会话列表取到之前不能发送
  await expect(page.getByRole('button', { name: '发送' })).toBeEnabled()
  await page.keyboard.press('Enter')
}

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

/** 对话底座：左右各 8、下沿 18；快捷胶囊 36 高带 data-hit44；输入框 44 */
async function expectDock(page: Page, height: number): Promise<void> {
  const slab = page.locator('.slab')
  const box = await slab.boundingBox()
  const viewport = page.viewportSize()
  if (!box || !viewport) throw new Error('量不到对话底座')
  expect(box.x, '底座左边距').toBeCloseTo(8, 0)
  expect(viewport.width - (box.x + box.width), '底座右边距').toBeCloseTo(8, 0)
  expect(viewport.height - (box.y + box.height), '底座下边距').toBeCloseTo(18, 0)
  expect(box.height, '底座高度').toBeCloseTo(height, 0)
  for (const pill of await page.locator('.qa a').all()) {
    expect((await pill.boundingBox())?.height, '快捷胶囊 36 高').toBeCloseTo(36, 0)
    await expect(pill).toHaveAttribute('data-hit44', '')
  }
  expect((await page.locator('.cmp-in').boundingBox())?.height, '输入框 44 高').toBeCloseTo(44, 0)
  // 底座在 #shell-root 里，不在滚动容器里
  expect(await slab.evaluate((el) => el.closest('#shell-root') !== null && el.closest('[data-scroller]') === null)).toBe(true)
}

/** 把今天的开场都拒掉（拒掉一类，下一类才会出现） */
async function declineOpenings(request: APIRequestContext, token: string): Promise<void> {
  const headers = { Authorization: `Bearer ${token}` }
  for (let i = 0; i < 5; i += 1) {
    const body = (await (await request.get('/api/agent/opening', { headers })).json()) as { opening: { id: string } | null }
    if (!body.opening) return
    await request.post(`/api/agent/opening/${body.opening.id}/decline`, { headers })
  }
}

const radius = (page: Page, selector: string) =>
  page.locator(selector).first().evaluate((el) => getComputedStyle(el).borderRadius)

test('lays out the chat with history, a streamed answer and the dock', async ({ page, request }) => {
  const token = await chatUser(request, ['练完腿，晚饭吃什么好？', '鸡胸肉吃腻了，换成牛肉可以吗？', '午饭吃了番茄炒蛋和米饭，帮我记一下'])
  await openAs(page, token, '/chat')
  await expect(page.getByRole('heading', { name: '对话', level: 1 })).toBeVisible()
  await expect(page.getByText('鸡胸肉吃腻了，换成牛肉可以吗？')).toBeVisible()

  await send(page, '晚饭吃什么')
  const answer = page.locator('.msg-a').last()
  await expect(answer).toContainText('今晚可以吃清蒸鱼配米饭')
  await expect(answer.getByRole('button', { name: /依据/ })).toBeVisible()
  await expect(answer.getByText('仅供参考')).toBeVisible()
  await expect(page.locator('[data-sensitive-area="messages"]')).not.toHaveAttribute('aria-busy', 'true')

  await expectDock(page, 158)
  expect(await radius(page, '.msg-u>span'), '用户气泡圆角').toBe('22px 22px 8px')
  expect(await radius(page, '.msg-a'), '助手气泡圆角').toBe('8px 22px 22px')
  await expectPageRules(page)
  await expectSensitiveAreas(page, ['messages'])

  // 滚动后页头吸顶、玻璃层出现；回到顶部时没有
  const header = page.locator('header.top')
  await page.locator('[data-scroller]').evaluate((el) => el.scrollTo({ top: 0 }))
  await expect(header).not.toHaveClass(/stuck/)
  await page.locator('[data-scroller]').evaluate((el) => el.scrollTo({ top: el.scrollHeight }))
  await expect(header).toHaveClass(/stuck/)
  await expect.poll(() => header.evaluate((el) => getComputedStyle(el, '::before').opacity)).toBe('1')
  await expectGlass(page, true)
  await expectBlurBudget(page)

  // 多行草稿让底座变高：滚动容器的底部留白跟着底座的实际高度
  const input = page.getByRole('textbox', { name: '给助手发消息' })
  await input.fill('第一行\n第二行\n第三行\n第四行')
  await expect.poll(async () => (await page.locator('.slab').boundingBox())?.height ?? 0).toBeGreaterThan(158)
  const slabHeight = (await page.locator('.slab').boundingBox())?.height ?? 0
  const padding = await page.locator('[data-scroller]').evaluate((el) => Number.parseFloat(getComputedStyle(el).paddingBottom))
  expect(padding, '底部留白 = 底座高度 + 38').toBeCloseTo(slabHeight + 38, 0)
  await input.fill('')
  await expect.poll(async () => (await page.locator('.slab').boundingBox())?.height ?? 0).toBeCloseTo(158, 0)

  await expectCoverWorks(page)

  // 减少透明：外壳换成实色
  await page.evaluate((key) => window.localStorage.setItem(key, 'on'), REDUCE_KEY)
  await page.reload()
  await expect(page.locator('.slab')).toBeVisible()
  await expectGlass(page, false)
})

test('shows the care alert full bleed without quick actions', async ({ page, request }) => {
  const token = await chatUser(request)
  await openAs(page, token, '/chat')
  await expect(page.getByRole('group', { name: '快捷操作' })).toBeVisible()
  await send(page, '胸口很闷，一直出冷汗')
  const care = page.locator('.care')
  await expect(care).toBeVisible()
  await expect(care.getByRole('link', { name: '拨打 120' })).toHaveAttribute('href', 'tel:120')
  await expect(page.getByRole('group', { name: '快捷操作' })).toHaveCount(0)
  await expectDock(page, 118)

  const box = await care.boundingBox()
  const viewport = page.viewportSize()
  if (!box || !viewport) throw new Error('量不到就医提示')
  expect(box.x, '就医提示贴左边').toBe(0)
  expect(box.width, '就医提示贴右边').toBe(viewport.width)
  expect(await radius(page, '.care'), '就医提示直角').toBe('0px')
  await expectPageRules(page)
  await expectForcedColorsSmoke(page)

  // 遮盖后就医提示的四角没有朱色露出
  await care.scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: '遮盖敏感内容', exact: true }).click()
  await expect(page.locator('[data-sensitive-area="messages"]')).toHaveAttribute('aria-hidden', 'true')
  await page.waitForTimeout(300)
  const covered = await care.boundingBox()
  if (!covered) throw new Error('量不到就医提示')
  const corners = [
    [covered.x + 1, covered.y + 1], [covered.x + covered.width - 5, covered.y + 1],
    [covered.x + 1, covered.y + covered.height - 5], [covered.x + covered.width - 5, covered.y + covered.height - 5],
  ]
  for (const [x, y] of corners) {
    for (const pixel of await samplePixels(page, Math.round(x ?? 0), Math.round(y ?? 0))) {
      expect(pixel.r - pixel.b, `(${x}, ${y}) 漏出了朱色`).toBeLessThan(40)
    }
  }
  await page.getByRole('button', { name: '已遮盖，点按恢复显示', exact: true }).click()
})

test('shows the medical notice as a system slip', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  await seedActiveItem(request, user.token, SPICY)
  await openAs(page, user.token, '/chat')
  await send(page, '推荐川菜')
  const slip = page.getByRole('note', { name: '系统附上的医嘱提醒' })
  await expect(slip).toContainText('按你当前生效的医嘱，以下食物不建议：麻婆豆腐。')
  await expect(page.locator('.msg-a').last()).not.toContainText('麻婆豆腐')
  await expectSensitiveAreas(page, ['messages', 'notes'])
  await expectPageRules(page)
})

test('opens with the due review and keeps the proposal in the strip', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  await seedReviewDueItem(request, user.token, SALT)
  const knee = await seedActiveItem(request, user.token, KNEE)
  await seedProposal(request, user.token, knee.id, '用户转述医生说已经好了')
  await openAs(page, user.token, '/chat')

  const card = page.getByRole('group', { name: /你有一条医嘱/ })
  await expect(card).toBeVisible()
  await expect(card.getByText('今天想问你')).toBeVisible()
  await expect(card.getByRole('button')).toHaveText(['继续遵守', '去医嘱页处理', '稍后'])
  const strip = page.getByRole('button', { name: '运动限制 有解除建议' })
  await expect(strip).toBeVisible()
  await expectSensitiveAreas(page, ['messages', 'opening', 'reviewBar'])
  await expectPageRules(page)

  await strip.click()
  await expect(page.getByText('膝关节术后六周内避免跑跳')).toBeVisible()
  await expect(page.locator('.prop-by')).toContainText('提出，仍在生效')
  await expect(page.locator('.prop-by .ref')).toHaveText('仅供参考')
  await expect(page.locator('.rvx').getByRole('button', { name: '不解除' })).toBeVisible()
  await expectPageRules(page)
  await strip.click()

  await card.getByRole('button', { name: '继续遵守' }).click()
  const sheet = page.getByRole('dialog', { name: '继续遵守这条医嘱' })
  await expect(sheet).toBeVisible()
  await expect(sheet.getByText('已到复查日期，请确认是否还需要继续遵守')).toBeVisible()
  await waitForSheet(page)
  await expectPageRules(page)
  await sheet.getByRole('button', { name: '继续遵守' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已继续遵守')).toBeVisible()
  await expect(card).toHaveCount(0)
  await expect(strip).toBeVisible()
})

test('keeps the expanded strip within the blur budget and every action reachable', async ({ page, request }) => {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  let conversation: string | undefined
  for (const text of ['练完腿，晚饭吃什么好？', '晚饭吃什么', '那明天早饭呢', '好的']) {
    conversation = (await sendMessage(request, user.token, text, conversation)).conversation_id
  }
  for (const [i, content] of ['低盐饮食，每日钠不超过 2000 毫克', '每日饮水不少于 1500 毫升', '每周复查血压 2 次'].entries()) {
    await seedReviewDueItem(request, user.token, { ...SALT, content, subjects: [`盐${i}`] })
  }
  for (const item of [KNEE, { ...KNEE, content: '术后三个月内不做深蹲，负重不超过 10 千克', subjects: ['深蹲'] }]) {
    const active = await seedActiveItem(request, user.token, item)
    await seedProposal(request, user.token, active.id, '用户转述医生说已经好了')
  }
  await declineOpenings(request, user.token)
  await openAs(page, user.token, '/chat')

  const strip = page.getByRole('button', { name: '医嘱待处理 5 条' })
  await expect(strip).toBeVisible()
  await page.locator('[data-scroller]').evaluate((el) => el.scrollTo({ top: el.scrollHeight }))
  await expect(page.locator('header.top')).toHaveClass(/stuck/)
  await strip.click()
  await expect(page.locator('.rvx-i')).toHaveCount(5)
  await page.waitForTimeout(300)
  await expectBlurBudget(page)

  // 每一条的动作都能滚到、在视口里、不被对话底座挡住，并且真的点得到
  const slabTop = (await page.locator('.slab').boundingBox())?.y ?? 0
  const actions = page.locator('.rvx .acts-r').getByRole('button').or(page.locator('.rvx .acts-r').getByRole('link'))
  expect(await actions.count()).toBe(10)
  for (const action of await actions.all()) {
    await action.scrollIntoViewIfNeeded()
    const box = await action.boundingBox()
    if (!box) throw new Error('量不到条子里的动作')
    expect(box.y, '动作在视口里').toBeGreaterThanOrEqual(0)
    expect(box.y + box.height, '动作不在对话底座下面').toBeLessThanOrEqual(slabTop)
    await action.click({ trial: true })
  }
  await expectBlurBudget(page)
  await expectTouchTargets(page)
})

