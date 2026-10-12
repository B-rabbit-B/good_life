import type { Page } from '@playwright/test'

const LOCAL_HOST = '127.0.0.1'

/**
 * 只放行 127.0.0.1 与本地 file:// 文件（设计稿），其余请求一律 abort（设计稿里的 Google 字体同样被拦下）。
 * 返回被拦下的地址列表（随页面继续请求而增长），测试可以断言它为空。
 */
export async function blockExternal(page: Page): Promise<string[]> {
  const blocked: string[] = []
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.protocol === 'file:' || url.hostname === LOCAL_HOST) {
      await route.continue()
      return
    }
    blocked.push(url.href)
    await route.abort('blockedbyclient')
  })
  return blocked
}
