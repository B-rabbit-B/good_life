// 组件样张页的版式与无障碍检查（layout-390 与 layout-360 两个宽度各跑一遍）。样张页不需要登录。
import type { Page } from '@playwright/test'
import {
  expectCoverWorks,
  expectForcedColorsSmoke,
  expectGlass,
  expectMinFontSize,
  expectNoHorizontalScroll,
  expectTouchTargets,
} from '../support/a11y'
import { expect, test } from '../support/test'

const GALLERY = '/dev/gallery'

async function openGallery(page: Page): Promise<void> {
  await page.goto(GALLERY)
  await expect(page.locator('#ds')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

const box = (page: Page, selector: string) => page.locator(selector).first().evaluate((el) => {
  const rect = el.getBoundingClientRect()
  const style = getComputedStyle(el)
  return {
    width: rect.width, height: rect.height, left: rect.left, right: window.innerWidth - rect.right,
    bottom: window.innerHeight - rect.bottom, radius: style.borderTopLeftRadius,
  }
})

test('gallery meets the touch, font size and overflow rules', async ({ page }) => {
  await openGallery(page)
  await expectTouchTargets(page)
  await expectMinFontSize(page, 12)
  await expectNoHorizontalScroll(page)
})

test('buttons, nav and switches have the deck sizes', async ({ page }) => {
  await openGallery(page)
  const primary = await box(page, '.btn.btn-pri:not(.btn-sm):not(.btn-blk)')
  expect(primary.height).toBe(48)
  expect(primary.radius).toBe('16px')
  const small = page.locator('.btn.btn-sm').first()
  expect((await box(page, '.btn.btn-sm')).height).toBe(36)
  await expect(small).toHaveAttribute('data-hit44', '')
  const nav = await box(page, '#shell-root .rnav')
  expect(nav.height).toBe(60)
  expect(nav.left).toBe(8)
  expect(nav.right).toBe(8)
  expect(nav.bottom).toBe(18)
  expect(nav.radius).toBe('28px')
  const toggle = await box(page, '.tg')
  expect([toggle.width, toggle.height]).toEqual([50, 30])
})

test('glass turns off with the reduce transparency setting', async ({ page }) => {
  await openGallery(page)
  await expectGlass(page, true)
  await page.getByRole('radiogroup', { name: /减少透明/ }).getByText('开', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'off')
  await expectGlass(page, false)
  await page.getByRole('radiogroup', { name: /减少透明/ }).getByText('跟随系统', { exact: true }).click()
  await expectGlass(page, true)
})

test('forced colors keep real borders and outlines', async ({ page }) => {
  await openGallery(page)
  await expectForcedColorsSmoke(page)
})

test('tab reaches the sensitive ruler while it is uncovered', async ({ page }) => {
  await openGallery(page)
  // 证明下一条的 Tab 检查有意义：不遮盖时，连按 Tab 能进入样张页上方的敏感区（刻度尺）
  let reached = false
  for (let i = 0; i < 40 && !reached; i += 1) {
    await page.keyboard.press('Tab')
    reached = await page.evaluate(() => document.activeElement?.closest('[data-sensitive]') != null)
  }
  expect(reached).toBe(true)
})

test('cover hides every sensitive region', async ({ page }) => {
  await openGallery(page)
  await expectCoverWorks(page)
})

test('reduced motion stops the sweep and shows final counts', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openGallery(page)
  const sweep = await page.locator('.sk').first().evaluate((el) => getComputedStyle(el, '::after').display)
  expect(sweep).toBe('none')
  const count = page.locator('[data-demo="count"]')
  await expect(count).toHaveText('1,085')
  await page.locator('[data-demo-button="count"]').click()
  // 不等动画：减弱动效时直接是终值
  expect(await count.textContent()).toBe('1,640')
})
