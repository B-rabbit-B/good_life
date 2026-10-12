// 端到端测试一律从这里引入 test 与 expect（ESLint 禁止在 e2e 里直接从 @playwright/test 引入 test）：
// 自动夹具 blockedRequests 给每个测试的浏览器上下文装上外网拦截，值是被拦下的地址列表。
import { test as base } from '@playwright/test'
import { blockExternal } from './net'

export const test = base.extend<{ blockedRequests: string[] }>({
  blockedRequests: [
    async ({ context }, use) => {
      await use(await blockExternal(context))
    },
    { auto: true },
  ],
})

export { expect } from '@playwright/test'
