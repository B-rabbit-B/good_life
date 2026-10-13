import type { BrowserContext, Page } from '@playwright/test'
import { connect } from 'node:net'

const LOCAL_HOST = '127.0.0.1'

const isLocal = (url: URL) => url.protocol === 'file:' || url.hostname === LOCAL_HOST

/**
 * WebKit 用的“死代理”：除 127.0.0.1 以外的请求都发给本机一个没有服务的端口，连接被拒，请求失败。
 * WebKit 不装请求拦截，因为 Playwright 在 WebKit 里拦截后转发（route.continue）的 multipart 上传会丢掉
 * 由 Blob 组成的文件内容（拍照识别上传成了空文件，后端答 photo_empty；不拦截时不会发生）。
 */
const DEAD_PORT = 9
export const DEAD_PROXY = { server: `http://${LOCAL_HOST}:${DEAD_PORT}`, bypass: LOCAL_HOST }

/** 死代理的端口必须没有服务在听（连接被拒）；有东西在听时外网请求可能被转出去，直接报错停下。 */
function expectDeadPort(): Promise<void> {
  return new Promise((resolve, reject) => {
    const socket = connect({ host: LOCAL_HOST, port: DEAD_PORT })
    socket.setTimeout(2000)
    socket.once('connect', () => {
      socket.destroy()
      reject(new Error(`${LOCAL_HOST}:${DEAD_PORT} 上有服务在监听，WebKit 的死代理不再可靠，先停掉占用这个端口的程序`))
    })
    socket.once('timeout', () => {
      socket.destroy()
      reject(new Error(`连接 ${LOCAL_HOST}:${DEAD_PORT} 超时而不是被拒绝，没法确认死代理会让请求立即失败`))
    })
    socket.once('error', (error: NodeJS.ErrnoException) => {
      socket.destroy()
      if (error.code === 'ECONNREFUSED') resolve()
      else reject(new Error(`检查 ${LOCAL_HOST}:${DEAD_PORT} 时出错：${error.message}`))
    })
  })
}

/** WebKit：不拦截，只记下发往本机以外的请求与 WebSocket（它们经死代理失败）。 */
async function recordExternal(context: BrowserContext): Promise<string[]> {
  await expectDeadPort()
  const attempted: string[] = []
  context.on('request', (request) => {
    const url = new URL(request.url())
    if (!isLocal(url) && !url.protocol.startsWith('data') && !url.protocol.startsWith('blob')) attempted.push(url.href)
  })
  const watchSockets = (page: Page) => page.on('websocket', (ws) => {
    if (!isLocal(new URL(ws.url()))) attempted.push(ws.url())
  })
  context.pages().forEach(watchSockets)
  context.on('page', watchSockets)
  return attempted
}

/**
 * 只放行 127.0.0.1 与本地 file:// 文件（设计稿），其余 HTTP 请求一律 abort（设计稿里的 Google 字体同样被拦下），
 * 非本机的 WebSocket 直接关闭。返回被拦下的地址列表（随页面继续请求而增长），测试可以断言它为空。
 * 由 e2e/support/test.ts 的自动夹具对每个测试的浏览器上下文安装，测试不需要自己调用。
 * WebKit 例外：上下文由夹具配上 DEAD_PROXY，外网请求经它失败，这里只记录（见 DEAD_PROXY 的说明）。
 */
export async function blockExternal(context: BrowserContext): Promise<string[]> {
  if (context.browser()?.browserType().name() === 'webkit') return await recordExternal(context)
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
