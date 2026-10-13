import type { BrowserContext } from '@playwright/test'

const LOCAL_HOST = '127.0.0.1'

const isLocal = (url: URL) => url.protocol === 'file:' || url.hostname === LOCAL_HOST

/**
 * WebKit 用的“死代理”：除 127.0.0.1 以外的请求都发给本机一个没有服务的端口，连接被拒，请求失败。
 * WebKit 不装请求拦截，因为 Playwright 在 WebKit 里拦截后转发（route.continue）的 multipart 上传会丢掉
 * 由 Blob 组成的文件内容（拍照识别上传成了空文件，后端答 photo_empty；不拦截时不会发生）。
 */
export const DEAD_PROXY = { server: 'http://127.0.0.1:9', bypass: LOCAL_HOST }

/** WebKit：不拦截，只记下发往本机以外的请求（它们经死代理失败）。 */
function recordExternal(context: BrowserContext): string[] {
  const attempted: string[] = []
  context.on('request', (request) => {
    const url = new URL(request.url())
    if (!isLocal(url) && !url.protocol.startsWith('data') && !url.protocol.startsWith('blob')) attempted.push(url.href)
  })
  return attempted
}

/**
 * 只放行 127.0.0.1 与本地 file:// 文件（设计稿），其余 HTTP 请求一律 abort（设计稿里的 Google 字体同样被拦下），
 * 非本机的 WebSocket 直接关闭。返回被拦下的地址列表（随页面继续请求而增长），测试可以断言它为空。
 * 由 e2e/support/test.ts 的自动夹具对每个测试的浏览器上下文安装，测试不需要自己调用。
 * WebKit 例外：上下文由夹具配上 DEAD_PROXY，外网请求经它失败，这里只记录（见 DEAD_PROXY 的说明）。
 */
export async function blockExternal(context: BrowserContext): Promise<string[]> {
  if (context.browser()?.browserType().name() === 'webkit') return recordExternal(context)
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
