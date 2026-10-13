// 玻璃降级、强制颜色、触控目标与字号、遮盖（切到后台再回来）与减弱动效，在 iPhone 13（WebKit）与 Pixel 7（Chromium）上各跑一遍。
import type { APIRequestContext, Page } from '@playwright/test'
import type { components } from '../../src/api/schema'
import { fmtNum } from '../../src/lib/format'
import {
  expectForcedColorsSmoke, expectGlass, expectMinFontSize, expectNoHorizontalScroll, expectTouchTargets,
} from '../support/a11y'
import {
  CEFUROXIME_ORDER, createUser, e2eInfo, logMeal, openAs, seedActiveItem, seedModelService, seedPendingOrder, sendMessage,
} from '../support/api'
import { hideAndShowPage } from '../support/flows'
import { expect, test } from '../support/test'

const REDUCE_TRANSPARENCY = '(prefers-reduced-transparency: reduce)'
const KNEE: components['schemas']['ManualItemCreate'] = { category: 'exercise_limit', content: '膝关节术后六周内避免跑跳', subjects: ['跑跳'] }

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

/** 主要页面都有内容的用户：模型服务、一段对话、一餐、一份待核对医嘱与一条生效条目 */
async function fullUser(request: APIRequestContext): Promise<string> {
  const { token } = await createUser(request)
  await seedModelService(request, token, await e2eInfo(request))
  await sendMessage(request, token, '晚饭吃什么')
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:111101x', grams: 50 })
  await seedPendingOrder(request, token, CEFUROXIME_ORDER)
  await seedActiveItem(request, token, KNEE)
  return token
}

async function expectPageRules(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
}

test('glass falls back to solid when reduced transparency is on', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/me')
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'on')
  await expectGlass(page, true)

  // 系统“减少透明”：外壳一律换成实色
  await page.addInitScript((query) => {
    const original = window.matchMedia.bind(window)
    window.matchMedia = (q: string) => {
      const list = original(q)
      if (q !== query) return list
      return Object.defineProperty(list, 'matches', { value: true })
    }
  }, REDUCE_TRANSPARENCY)
  await page.reload()
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'off')
  await expectGlass(page, false)
})

test('forced colours keep borders and shapes', async ({ page, request, browserName }) => {
  test.skip(browserName === 'webkit', 'WebKit 不支持模拟强制颜色')
  const token = await fullUser(request)
  for (const path of ['/me', '/health/medical?tab=pending']) {
    await openAs(page, token, path)
    await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
    await expect(page.locator('.btn').first()).toBeVisible()
    await expectForcedColorsSmoke(page)
  }
})

test('touch targets and font sizes hold on the main pages', async ({ page, request }) => {
  test.setTimeout(120_000)
  const token = await fullUser(request)
  const pages: [string, RegExp | string][] = [
    ['/chat', '对话'], ['/records', '记录'], ['/health/medical?tab=pending', '健康'], ['/me', '我的'],
    ['/restaurants', '附近吃什么'], ['/settings/models', '模型服务'],
  ]
  for (const [path, heading] of pages) {
    await openAs(page, token, path)
    await expect(page.getByRole('heading', { name: heading, level: 1 })).toBeVisible()
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
    await expectPageRules(page)
  }
})

test('cover hides sensitive content and comes back when the page was hidden', async ({ page, request }) => {
  const { token } = await createUser(request)
  await openAs(page, token, '/me')
  const areas = page.locator('[data-sensitive]')
  await expect(areas.first()).toBeVisible()
  await expect(areas.first()).not.toHaveAttribute('aria-hidden', 'true')
  await hideAndShowPage(page)
  // 回到前台后仍处于遮盖状态，等用户自己恢复
  await expect(page.getByRole('button', { name: '已遮盖，点按恢复显示', exact: true }).first()).toBeVisible()
  for (const area of await areas.all()) {
    await expect(area).toHaveAttribute('aria-hidden', 'true')
    await expect(area).toHaveAttribute('inert', '')
  }
  await page.getByRole('button', { name: '已遮盖，点按恢复显示', exact: true }).first().click()
  await expect(areas.first()).not.toHaveAttribute('aria-hidden', 'true')
})

test('reduced motion removes movement', async ({ page, request }) => {
  const { token } = await createUser(request)
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:061101x', grams: 400 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openAs(page, token, '/records')
  await expect(page.getByRole('img', { name: /今日能量/ })).toBeVisible()
  const summary = (await (await request.get('/api/nutrition/summary', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as { total: { energy_kcal: number | null } }
  // 计数一出现就是终值
  await expect(page.locator('.ledger-big>.ns')).toHaveText(fmtNum(summary.total.energy_kcal ?? 0, 1))
  // 全部元素（含伪元素）的动画与过渡时长都不超过 1 毫秒
  const moving = await page.evaluate(() => {
    const seconds = (value: string) => value.split(',').map((part) => {
      const v = part.trim()
      return v.endsWith('ms') ? Number.parseFloat(v) / 1000 : Number.parseFloat(v)
    })
    const out: string[] = []
    for (const el of Array.from(document.querySelectorAll('*'))) {
      for (const pseudo of [null, '::before', '::after'] as const) {
        const style = getComputedStyle(el, pseudo)
        const animated = style.animationName !== 'none' && seconds(style.animationDuration).some((s) => s > 0.001)
        const transitioned = seconds(style.transitionDuration).some((s) => s > 0.001)
        if (animated || transitioned) {
          out.push(`${el.tagName.toLowerCase()}.${String(el.className)}${pseudo ?? ''}：`
            + `${style.animationName} ${style.animationDuration} / ${style.transitionDuration}`)
        }
      }
    }
    return out
  })
  expect(moving, '减弱动效下仍有动画或过渡').toEqual([])
})
