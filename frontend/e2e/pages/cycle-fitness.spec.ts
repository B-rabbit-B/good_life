// 经期与训练：390 与 360 两个宽度下，经期页（女性用户经接口写四次经期与两天的记录）的月历格高 44、格内方块 36（圆角 12）、
// 面板内边距 12（360 下每格约 44.6 宽），遮盖后内容区只剩两个记录按钮可点；强制颜色下已记录格是 CanvasText 实块、
// 今天是 Highlight 描边；两个面板在模糊预算内。训练页（经接口写一周的训练、一条运动限制）的柱顶角 2、运动限制与冲突说明在敏感区里；
// 记一次训练从搜索到保存。每页都查触控目标、最小字号、横向滚动、敏感区与遮盖。
import type { APIRequestContext, Page } from '@playwright/test'
import {
  expectBlurBudget, expectCoverWorks, expectForcedColorsSmoke, expectMinFontSize, expectNoHorizontalScroll, expectSensitiveAreas,
  expectTouchTargets, waitForSheet,
} from '../support/a11y'
import { createUser, KNEE_LIMIT, localDate, openAs, seedDeckCycle, seedDeckTraining } from '../support/api'
import { expect, test } from '../support/test'

async function cycleUser(request: APIRequestContext): Promise<string> {
  const { token } = await createUser(request)
  await seedDeckCycle(request, token)
  return token
}

async function trainingUser(request: APIRequestContext): Promise<string> {
  const { token } = await createUser(request)
  await seedDeckTraining(request, token)
  return token
}

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

/** 内容区（页头与底部导航以外）里还能点的东西的名字 */
function clickableInContent(page: Page): Promise<string[]> {
  return page.evaluate(() => Array.from(document.querySelectorAll('main a, main button, main [role="button"], main input'))
    .filter((el) => !el.closest('.top') && !el.closest('[inert]') && el.getBoundingClientRect().width > 0)
    .map((el) => el.getAttribute('aria-label') ?? el.textContent?.trim() ?? ''))
}

test('lays out the cycle page at the deck sizes and covers all but the two buttons', async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  await expect(page.getByRole('img', { name: /^周期刻度：/ })).toBeVisible()
  await expect(page.locator('.cal-g .d.today')).toBeVisible()
  await expect(page.locator('.cal-g .d.log').first()).toBeVisible()

  const viewport = page.viewportSize()?.width ?? 0
  const panel = await page.locator('.cal').evaluate((el) => {
    const style = getComputedStyle(el)
    return { left: style.paddingLeft, right: style.paddingRight }
  })
  expect(panel).toEqual({ left: '12px', right: '12px' })
  const cells = await page.locator('.cal-g .d').evaluateAll((els) => els.map((el) => {
    const box = el.getBoundingClientRect()
    const span = el.querySelector('span') as HTMLElement
    const square = span.getBoundingClientRect()
    return { width: box.width, height: box.height, square: [square.width, square.height], radius: getComputedStyle(span).borderTopLeftRadius }
  }))
  expect(cells.length % 7).toBe(0)
  const expectedWidth = (viewport - 2 * 12 - 2 * 12) / 7 // 面板外边 12、内边距 12
  for (const cell of cells) {
    expect(cell.height).toBe(44)
    expect(cell.square).toEqual([36, 36])
    expect(cell.radius).toBe('12px')
    expect(Math.abs(cell.width - expectedWidth)).toBeLessThan(0.5)
  }
  if (viewport === 360) expect(cells[0]?.width).toBeGreaterThan(44.4)

  await expectPageRules(page)
  await expectSensitiveAreas(page)
  await expectCoverWorks(page)
  await page.getByRole('button', { name: '遮盖敏感内容', exact: true }).first().click()
  await expect.poll(() => clickableInContent(page)).toEqual(['记录经期', '记录今天'])
  await page.getByRole('button', { name: '已遮盖，点按恢复显示', exact: true }).first().click()
})

test('leaves the calendar cells of the neighbouring months empty', async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  await expect(page.locator('.cal-g .d.today')).toBeVisible()
  const month = localDate().slice(0, 7)
  const cells = await page.locator('.cal-g .d').evaluateAll((els) => els.map((el) => {
    const box = el.querySelector('span')?.getBoundingClientRect()
    return {
      date: el.getAttribute('data-date') ?? '', text: el.textContent ?? '', tabindex: el.getAttribute('tabindex'),
      visibility: getComputedStyle(el).visibility, square: [box?.width, box?.height],
    }
  }))
  const before = cells.filter((cell) => cell.date < `${month}-01`)
  const inMonth = cells.filter((cell) => cell.date.startsWith(month))
  for (const cell of cells.filter((c) => !c.date.startsWith(month))) {
    expect(cell).toMatchObject({ text: '', tabindex: null, visibility: 'hidden', square: [36, 36] })
  }
  expect(before.map((cell) => cell.text).join('')).toBe('')
  expect(inMonth.length).toBeGreaterThanOrEqual(28)
  expect(inMonth[0]?.text).toBe('1')
  expect(inMonth.every((cell) => cell.text !== '' && cell.visibility === 'visible')).toBe(true)
})

test('records a past period and deletes it from the recorded periods list', async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  await expect(page.locator('.cal-g .d.today')).toBeVisible()
  await expect(page.locator('.cal-g .d.today.rec')).toHaveCount(0)
  const list = page.locator('.cyc-list')
  await expect(list.getByRole('listitem')).toHaveCount(4)

  await page.getByRole('button', { name: '记录经期开始' }).click()
  const record = page.getByRole('dialog', { name: '记录经期开始' })
  await record.getByLabel('结束日期（还没结束可以留空）').fill(localDate())
  await record.getByRole('button', { name: '保存' }).click()
  await expect(record).toHaveCount(0)
  await expect(page.locator('.cal-g .d.today.rec')).toBeVisible()
  await expect(list.getByRole('listitem')).toHaveCount(5)

  const [year = '', month = '', day = ''] = localDate().split('-')
  const label = `删除 ${year}年${Number(month)}月${Number(day)}日 开始的经期`
  await expectPageRules(page)
  await list.getByRole('button', { name: label }).click()
  const sheet = page.getByRole('dialog', { name: '删除这次经期记录' })
  await expect(sheet).toContainText('这次经期当天的每日记录不会被删除。')
  await waitForSheet(page)
  await sheet.getByRole('button', { name: '删除这次经期' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已删除')).toBeVisible()
  await expect(list.getByRole('listitem')).toHaveCount(4)
  await expect(page.locator('.cal-g .d.today.rec')).toHaveCount(0)
  await expect(page.locator('.cal-g .d.today')).toBeVisible()
})

test('draws the calendar marks with system colours in forced colours',async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  await expect(page.locator('.cal-g .d.today')).toBeVisible()
  await expectForcedColorsSmoke(page)
  await page.emulateMedia({ forcedColors: 'active' })
  const colours = await page.evaluate(() => {
    const probe = document.createElement('div')
    document.body.appendChild(probe)
    const system = (value: string) => {
      probe.style.color = value
      return getComputedStyle(probe).color
    }
    const result = { canvasText: system('CanvasText'), highlight: system('Highlight') }
    probe.remove()
    const recorded = document.querySelector('.cal-g .d.rec span') as HTMLElement
    const today = document.querySelector('.cal-g .d.today span') as HTMLElement
    return {
      ...result,
      recorded: getComputedStyle(recorded).backgroundColor,
      todayShadow: getComputedStyle(today).boxShadow,
    }
  })
  await page.emulateMedia({ forcedColors: 'none' })
  expect(colours.recorded).toBe(colours.canvasText)
  expect(colours.todayShadow).toContain(colours.highlight)
  expect(colours.todayShadow).toContain('2px')
})

test('shows the focus ring on a predicted day reached by keyboard', async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  const today = page.locator('.cal-g .d.today')
  await expect(today).toBeVisible()
  await today.focus()
  // 用方向键一天一天往后移，直到焦点落在预计经期的格子上（可能翻到下个月）
  for (let i = 0; i < 45; i += 1) {
    if (await page.evaluate(() => document.activeElement?.classList.contains('prd') === true)) break
    await page.keyboard.press('ArrowRight')
  }
  const ring = await page.evaluate(() => {
    const cell = document.activeElement as HTMLElement
    const style = getComputedStyle(cell.querySelector('span') as HTMLElement)
    return { predicted: cell.classList.contains('prd'), visible: cell.hasAttribute('data-focus-visible'),
      width: style.outlineWidth, style: style.outlineStyle, color: style.outlineColor }
  })
  expect(ring).toEqual({ predicted: true, visible: true, width: '2px', style: 'solid', color: 'rgb(31, 88, 168)' })
  await page.emulateMedia({ forcedColors: 'active' })
  const forced = await page.evaluate(() => {
    const probe = document.createElement('div')
    probe.style.color = 'Highlight'
    document.body.appendChild(probe)
    const highlight = getComputedStyle(probe).color
    probe.remove()
    const style = getComputedStyle((document.activeElement as HTMLElement).querySelector('span') as HTMLElement)
    return { highlight, color: style.outlineColor, width: style.outlineWidth, style: style.outlineStyle }
  })
  await page.emulateMedia({ forcedColors: 'none' })
  expect(forced).toEqual({ highlight: forced.highlight, color: forced.highlight, width: '2px', style: 'solid' })
})

test('opens the period and day log sheets within the blur budget', async ({ page, request }) => {
  const token = await cycleUser(request)
  await openAs(page, token, '/health/cycle')
  await page.getByRole('button', { name: '记录今天' }).click()
  const sheet = page.getByRole('dialog', { name: '记录今天' })
  await expect(sheet.getByRole('radiogroup', { name: '流量' })).toBeVisible()
  await waitForSheet(page)
  await expectBlurBudget(page, { allowNone: true })
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await sheet.getByRole('radio', { name: '少' }).check({ force: true })
  await sheet.getByRole('button', { name: '保存' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已记下')).toBeVisible()

  await page.getByRole('button', { name: '记录经期开始' }).click()
  const period = page.getByRole('dialog', { name: '记录经期开始' })
  await expect(period.getByLabel('开始日期')).toHaveValue(localDate())
  await waitForSheet(page)
  await expectBlurBudget(page, { allowNone: true })
  await expectTouchTargets(page)
  await period.getByRole('button', { name: '取消' }).click()
  await expect(period).toHaveCount(0)
})

test('lays out training with square-topped bars and the limit in the sensitive area', async ({ page, request }) => {
  const token = await trainingUser(request)
  await openAs(page, token, '/records?tab=training')
  await expect(page.getByRole('heading', { name: '本周训练' })).toBeVisible()
  await expect(page.getByText(`运动限制生效中：${KNEE_LIMIT}`, { exact: false })).toBeVisible()
  const conflict = page.locator('.trw-x').first()
  await expect(conflict).toBeVisible()
  expect(await conflict.evaluate((el) => el.closest('[data-sensitive]')?.getAttribute('data-sensitive-area'))).toBe('constraints')
  await expect(page.locator('.wk-col')).toHaveCount(7)
  const bars = await page.locator('.wk-col:not(.zero) .bar').evaluateAll((els) => els.map((el) => {
    const style = getComputedStyle(el)
    return [style.borderTopLeftRadius, style.borderTopRightRadius, style.borderBottomLeftRadius]
  }))
  expect(bars.length).toBeGreaterThan(0)
  for (const radius of bars) expect(radius).toEqual(['2px', '2px', '0px'])
  await expect(page.locator('.trend circle.last')).toHaveCount(1)

  await expectPageRules(page)
  await expectSensitiveAreas(page, ['constraints'])
  await expectCoverWorks(page)
  await expectForcedColorsSmoke(page)
})

test('records a workout from search to save', async ({ page, request }) => {
  const token = await trainingUser(request)
  await openAs(page, token, '/records?tab=training')
  await page.getByRole('link', { name: '搜索动作，比如 深蹲、卧推' }).click()
  await expect(page).toHaveURL(/\/records\/workouts\/new$/)
  await page.getByRole('searchbox', { name: '搜索动作' }).fill('深蹲')
  await page.getByRole('list', { name: '搜索结果' }).getByRole('button', { name: /^深蹲/ }).click()
  const squat = page.getByRole('group', { name: '深蹲' })
  await squat.getByLabel('第 1 组重量').fill('40')
  await squat.getByLabel('第 1 组次数').fill('8')
  await squat.getByRole('button', { name: '加一组' }).click()
  await expect(squat.getByLabel('第 2 组重量')).toHaveValue('40')
  await page.evaluate(() => document.fonts.ready)
  await expectPageRules(page)
  await expectSensitiveAreas(page, ['constraints'])
  await expectCoverWorks(page)
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page).toHaveURL(/\/records\?tab=training$/)
  await expect(page.getByText('已记下')).toBeVisible()
  await expect(page.locator('.trw-h b', { hasText: '深蹲' }).first()).toBeVisible()
})

test('records a past period with its end date and shows it on the calendar', async ({ page, request }) => {
  const { token } = await createUser(request)
  const start = localDate(-20)
  const end = localDate(-15)
  await openAs(page, token, '/health/cycle')
  await page.getByRole('button', { name: '记录经期开始' }).last().click()
  const sheet = page.getByRole('dialog', { name: '记录经期开始' })
  await waitForSheet(page)
  await sheet.getByLabel('开始日期').fill(start)
  await expect(sheet.getByText('补记以前的经期，请同时填写结束日期')).toBeVisible()
  await sheet.getByLabel('结束日期（还没结束可以留空）').fill(end)
  await expect(sheet.getByText('补记以前的经期，请同时填写结束日期')).toHaveCount(0)
  await sheet.getByRole('button', { name: '保存' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已记下')).toBeVisible()
  const grid = page.getByRole('grid')
  for (const date of [end, start]) { // 由近到远，只往前翻
    // 日期不在当前显示的月份时翻到上个月
    const cell = page.locator(`.cal-g .d:not(.out)[data-date="${date}"]`)
    if (await cell.count() === 0) await page.getByRole('button', { name: '上个月' }).click()
    await expect(grid.locator(`.d:not(.out)[data-date="${date}"]`)).toHaveClass(/\brec\b/)
  }
})

test('picks a start and an end on the calendar, shows the band and deletes the period from the same panel', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/health/cycle')
  const cellOf = (date: string) => page.locator(`.cal-g .d:not(.out)[data-date="${date}"]`)
  const panel = page.getByRole('region', { name: '选中日期' })
  const today = localDate()
  await expect(cellOf(today)).toBeVisible()
  // 开始日与结束日取今天与往前一天；今天是 1 号时前一天在上个月，先翻页再点，点完翻回来
  const start = localDate(-1)
  if (await cellOf(start).count() === 0) await page.getByRole('button', { name: '上个月' }).click()
  await cellOf(start).click()
  await expect(panel).toContainText('再点一个日期作为结束日')
  await expect(cellOf(start)).toHaveClass(/\bss\b/)
  await expectPageRules(page)
  if (await cellOf(today).count() === 0) await page.getByRole('button', { name: '下个月' }).click()
  await cellOf(today).click()
  await expect(panel).toContainText('共 2 天')
  await expect(cellOf(today)).toHaveClass(/\bse\b/)
  await expect(page.locator('.cal-g .d.sb:not(.out)').first()).toBeVisible()
  await expectPageRules(page)
  await panel.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('已记下')).toBeVisible()
  await expect(panel).toHaveCount(0)
  await expect(page.locator('.cal-g .sb')).toHaveCount(0)
  await expect(cellOf(today)).toHaveClass(/\brec\b/)
  await expect(page.locator('.cyc-list').getByRole('listitem')).toHaveCount(1)

  await cellOf(today).click()
  await expect(panel).toContainText('的经期内')
  await panel.getByRole('button', { name: '删除这次经期' }).click()
  const sheet = page.getByRole('dialog', { name: '删除这次经期记录' })
  await waitForSheet(page)
  await sheet.getByRole('button', { name: '删除这次经期' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已删除')).toBeVisible()
  await expect(cellOf(today)).not.toHaveClass(/\brec\b/)
  await expect(panel).toHaveCount(0)
  await expect(page.locator('.cyc-list')).toHaveCount(0)
})
