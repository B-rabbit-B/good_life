// 可视比对：同一画面各截一张设计稿与一张应用，存到 test-results/visual/，供评审并排比较（不做像素断言）。
import type { Page } from '@playwright/test'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = fileURLToPath(new URL('.', import.meta.url))
const frontend = join(here, '..', '..')
const DECK = pathToFileURL(join(frontend, '..', 'docs', 'superpowers', 'design', 'step11', 'index.html')).href
const OUT = join(frontend, 'test-results', 'visual')
const HEIGHT = 844
const STATE_PANEL = /^st(\d+)$/ // 状态面板 st1 至 st12：按设计稿里 .panel 的序号

/** 打开设计稿，视口宽设为 width，截下编号为 frameId 的手机画面（.app）或状态面板（.panel）。 */
export async function captureDeckFrame(page: Page, frameId: string, width: number): Promise<string> {
  await page.setViewportSize({ width, height: HEIGHT })
  await page.goto(DECK)
  const panel = STATE_PANEL.exec(frameId)
  const target = panel
    ? page.locator('.panel').nth(Number(panel[1]) - 1)
    : page.locator(`figure:has(figcaption b span:text-is("${frameId}")) .app`)
  const path = join(OUT, `${frameId}-${width}-deck.png`)
  await target.screenshot({ path })
  return path
}

/** 截下应用当前的整个视口。 */
export async function captureApp(page: Page, frameId: string, width: number): Promise<string> {
  await page.setViewportSize({ width, height: HEIGHT })
  const path = join(OUT, `${frameId}-${width}-app.png`)
  await page.screenshot({ path })
  return path
}
