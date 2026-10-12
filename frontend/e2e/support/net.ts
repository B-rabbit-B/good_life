import type { BrowserContext } from '@playwright/test'

const LOCAL_HOST = '127.0.0.1'

const isLocal = (url: URL) => url.protocol === 'file:' || url.hostname === LOCAL_HOST

/**
 * 只放行 127.0.0.1 与本地 file:// 文件（设计稿），其余 HTTP 请求一律 abort（设计稿里的 Google 字体同样被拦下），
 * 非本机的 WebSocket 直接关闭。返回被拦下的地址列表（随页面继续请求而增长），测试可以断言它为空。
 * 由 e2e/support/test.ts 的自动夹具对每个测试的浏览器上下文安装，测试不需要自己调用。
 */
export async function blockExternal(context: BrowserContext): Promise<string[]> {
  const blocked: string[] = []
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (isLocal(url)) {
      await route.continue()
      return
    }
    blocked.push(url.href)
    await route.abort('blockedbyclient')
  })
  await context.routeWebSocket((url) => !isLocal(url), (ws) => {
    blocked.push(ws.url())
    void ws.close()
  })
  return blocked
}
