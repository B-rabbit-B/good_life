// 背景场必须真的画在页面后面：页面上没有面板的空隙里应是天青渐变加颗粒，而不是 html 的平底 #F7FAFE
// （body 若有自己的底色，会盖住 z-index:-1 的背景场，玻璃下面就没有东西可模糊）。
import type { Page } from '@playwright/test'
import { hex, samplePixels, type Rgb } from '../support/pixels'
import { expect, test } from '../support/test'

const FLAT = { r: 0xf7, g: 0xfa, b: 0xfe }
// 在视口下部取样：背景场越往下越青（到 #D9E6F6），离平底色最远；但要在浮起的导航（下沿 18、高 60）之上
const SAMPLE_Y = 640

const distance = (a: Rgb, b: Rgb) => Math.max(Math.abs(a.r - b.r), Math.abs(a.g - b.g), Math.abs(a.b - b.b))

async function expectFieldAt(page: Page, x: number, y: number): Promise<void> {
  const pixels = await samplePixels(page, x, y)
  const seen = pixels.map(hex).join(' ')
  // 不是平底色：每个像素都明显比 #F7FAFE 青、暗
  for (const pixel of pixels) expect(distance(pixel, FLAT), `取样 ${seen}`).toBeGreaterThan(8)
  // 是背景场的天青：蓝通道最高
  for (const pixel of pixels) expect(pixel.b, `取样 ${seen}`).toBeGreaterThan(pixel.r)
}

test('the field shows behind a plain page', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.field')).toBeAttached()
  await expectFieldAt(page, 200, SAMPLE_Y)
})

test('the field shows in the gaps between gallery panels', async ({ page }) => {
  await page.goto('/dev/gallery')
  await expect(page.locator('#st4')).toBeVisible()
  // 把 st3 与 st4 之间 40 像素的空隙移到取样高度
  const gapTop = await page.locator('#st3').evaluate((el) => el.getBoundingClientRect().bottom + window.scrollY)
  await page.evaluate((top) => window.scrollTo(0, top), gapTop - (SAMPLE_Y - 18))
  const gap = await page.locator('#st3').evaluate((el) => el.getBoundingClientRect().bottom)
  expect(gap).toBeLessThan(SAMPLE_Y)
  await expectFieldAt(page, 180, SAMPLE_Y)
})
