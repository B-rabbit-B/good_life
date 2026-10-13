// 验收标准 9：密钥在界面上只显示后端给的掩码：页面内容、输入框、本地存储、地址栏与浏览器收到的全部响应里都没有密钥原文。
import type { Response } from '@playwright/test'
import type { components } from '../../src/api/schema'
import { createUser, e2eInfo, openAs } from '../support/api'
import { fillProvider, finishProvider } from '../support/flows'
import { expect, test } from '../support/test'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('a saved key is only ever shown as the backend mask', async ({ page, request }) => {
  const info = await e2eInfo(request)
  const { token } = await createUser(request)
  const bodies: Promise<string>[] = []
  const urls: string[] = []
  // 密钥只可能出现在接口的响应里；在打开目标页之后才开始记，免得读到上一个文档里被导航取消的请求（它的响应体永远读不到）
  const record = (response: Response) => {
    if (!new URL(response.url()).pathname.startsWith('/api/')) return
    urls.push(response.url())
    bodies.push(response.text().catch(() => ''))
  }

  await openAs(page, token, '/settings/models/new')
  await expect(page.getByLabel('密钥', { exact: true })).toBeVisible()
  page.on('response', record)
  await fillProvider(page, info.model_base_url, info.model_key)
  // 保存成功后第 1 步只剩地址与掩码，密钥输入框随之卸下
  await expect(page.locator('[data-step="1"] .fs-sum')).toBeVisible()
  await expect(page.getByLabel('密钥', { exact: true })).toHaveCount(0)
  await finishProvider(page, info.chat_model_id, info.vision_model_id)

  const providers = (await (await request.get('/api/llm/providers', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as components['schemas']['ProviderOut'][]
  const hint = providers[0]?.key_hint
  expect(hint, '后端没有给出掩码').toBeTruthy()
  expect(hint).not.toContain(info.model_key)
  await expect(page.getByRole('img', { name: `密钥 ${hint}` })).toBeVisible()

  const key = info.model_key
  expect(await page.content(), '页面内容含密钥原文').not.toContain(key)
  const values = await page.locator('input, select, textarea').evaluateAll((els) => els.map((el) => (el as HTMLInputElement).value))
  expect(values.join('\n'), '输入框含密钥原文').not.toContain(key)
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }))
  expect(stored, '本地存储含密钥原文').not.toContain(key)
  expect(page.url(), '地址栏含密钥原文').not.toContain(key)
  for (const url of urls) expect(url, '接口地址含密钥原文').not.toContain(key)

  page.off('response', record)
  const texts = await Promise.all(bodies)
  // 至少记下了创建服务、获取模型、测试连通、分配用途与服务列表这些响应
  expect(urls.some((url) => url.endsWith('/api/llm/providers'))).toBe(true)
  expect(texts.length).toBeGreaterThan(4)
  for (const [i, text] of texts.entries()) expect(text, `${urls[i] ?? ''} 的响应含密钥原文`).not.toContain(key)
})
