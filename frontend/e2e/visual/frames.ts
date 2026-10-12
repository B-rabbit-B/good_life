import type { APIRequestContext, Page } from '@playwright/test'

export interface FrameSpec {
  /** 设计稿里的画面编号（例如 03a），状态面板用 st1 至 st12 */
  id: string
  widths: (360 | 390)[]
  /** 准备数据（只调用真实接口），返回要打开的路径 */
  prepare: (ctx: { request: APIRequestContext; page: Page }) => Promise<string>
}

/**
 * 样张页的某个区块：先打开样张页并等字体到齐，再返回带 #编号 的同一地址；
 * frames.spec 打开它时是同一文档内的跳转，页面直接滚到该区块（页头吸顶，区块留出页头的高度）。
 */
function galleryBlock(id: string, query = ''): FrameSpec['prepare'] {
  return async ({ page }) => {
    await page.goto(`/dev/gallery${query}`)
    await page.locator(`#${id}`).waitFor()
    await page.evaluate(() => document.fonts.ready)
    return `/dev/gallery${query}#${id}`
  }
}

// 每个界面任务往这里加自己的画面
export const FRAMES: FrameSpec[] = [
  // 设计系统一节对样张页
  { id: 'ds', widths: [360, 390], prepare: galleryBlock('ds') },
  // 状态面板 st1 至 st12 对样张页的对应区块；st10 是“一键遮盖”，打开时就遮盖
  ...Array.from({ length: 12 }, (_, i): FrameSpec => {
    const id = `st${i + 1}`
    return { id, widths: [360, 390], prepare: galleryBlock(id, id === 'st10' ? '?covered=1' : '') }
  }),
]
