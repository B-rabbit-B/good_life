// 每个画面、每个宽度各截一对图（应用与设计稿），存到 test-results/visual/，供评审并排比较。
import { test } from '@playwright/test'
import { blockExternal } from '../support/net'
import { captureApp, captureDeckFrame } from '../support/visual'
import { FRAMES } from './frames'

for (const frame of FRAMES) {
  for (const width of frame.widths) {
    test(`frame ${frame.id} at ${width}`, async ({ page, request }) => {
      await blockExternal(page)
      await page.setViewportSize({ width, height: 844 })
      const path = await frame.prepare({ request, page })
      await page.goto(path)
      await captureApp(page, frame.id, width)
      await captureDeckFrame(page, frame.id, width)
    })
  }
}
