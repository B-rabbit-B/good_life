// 端到端测试一律从这里引入 test 与 expect（ESLint 禁止在 e2e 里直接从 @playwright/test 引入 test）：
// 自动夹具 blockedRequests 给每个测试的浏览器上下文装上外网拦截，值是被拦下的地址列表
// （WebKit 改用死代理，见 net.ts 的 DEAD_PROXY）。
import { test as base } from '@playwright/test'
import { blockExternal, DEAD_PROXY } from './net'

export const test = base.extend<{ blockedRequests: string[] }>({
  // WebKit 的上下文走死代理（外网请求失败，本机直连）；其他浏览器保持原设置，由下面的路由拦截
  proxy: async ({ browserName, proxy }, provide) => {
    await provide(browserName === 'webkit' ? DEAD_PROXY : proxy)
  },
  blockedRequests: [
    async ({ context }, use) => {
      await use(await blockExternal(context))
    },
    { auto: true },
  ],
})

export { expect } from '@playwright/test'
