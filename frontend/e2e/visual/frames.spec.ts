// 每个画面、每个宽度各截一对图（应用与设计稿），存到 test-results/visual/，供评审并排比较。
// 外网拦截由 ../support/test 的自动夹具负责（设计稿里的 Google 字体请求同样被拦下）。
import { test } from '../support/test'
import { captureApp, captureDeckFrame } from '../support/visual'
import { FRAMES } from './frames'

for (const frame of FRAMES) {
  for (const width of frame.widths) {
    test(`frame ${frame.id} at ${width}`, async ({ page, request }) => {
      await page.setViewportSize({ width, height: 844 })
      const path = await frame.prepare({ request, page })
      await page.goto(path)
      await captureApp(page, frame.id, width)
      await captureDeckFrame(page, frame.id, width)
    })
  }
}
