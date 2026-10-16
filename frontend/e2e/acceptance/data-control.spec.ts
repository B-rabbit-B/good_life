// 数据可控（规格“一、数据可控：前端”）：在“我的 → 隐私与数据”页导出压缩包、清空对话历史、删除账号，以及删除模型服务；
// 被验收的动作全部经界面操作，前置数据经真实接口准备。每个用例用新注册的用户，删除账号不影响别的用例。
// 下载只断言响应、文件名与大小（外加压缩包的 PK 开头与内容里没有密码），不解读压缩包里的数据。
import { readFileSync } from 'node:fs'
import { conversationCount, createUser, e2eInfo, openAs, seedConversation, seedModelService } from '../support/api'
import { expect, test } from '../support/test'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('exports a zip after the password', async ({ page, request }) => {
  const { token, password } = await createUser(request)
  await openAs(page, token, '/me')
  await page.getByRole('link', { name: /模型服务/ }).click()
  await page.getByRole('link', { name: '隐私与数据' }).click()
  await expect(page).toHaveURL(/\/settings\/privacy$/)

  await page.getByRole('region', { name: '导出我的数据' }).getByRole('button', { name: '导出我的数据' }).click()
  const sheet = page.getByRole('dialog', { name: '导出我的数据' })
  await expect(sheet.getByText('密钥只含掩码', { exact: false })).toBeVisible()
  await sheet.getByLabel('登录密码').fill(password)
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/account/export'))
  const downloadPromise = page.waitForEvent('download')
  await sheet.getByRole('button', { name: '导出并下载' }).click()

  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect(response.request().method()).toBe('POST')
  expect(response.url()).not.toContain(password)
  expect(response.headers()['content-type']).toBe('application/zip')
  expect(response.headers()['cache-control']).toBe('no-store')
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^good-life-export-\d{8}\.zip$/)
  const bytes = readFileSync(await download.path())
  expect(bytes.length).toBeGreaterThan(100)
  expect(bytes.subarray(0, 2).toString('latin1')).toBe('PK')
  expect(bytes.includes(Buffer.from(password))).toBe(false)

  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已开始下载')).toBeVisible()
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }))
  expect(stored).not.toContain(password)
})

test('clears all conversations', async ({ page, request }) => {
  const { token } = await createUser(request)
  await seedModelService(request, token, await e2eInfo(request))
  const said = '清空之前说的一句话'
  await seedConversation(request, token, said)
  await openAs(page, token, '/')
  await expect(page.getByText(said)).toBeVisible()

  // 在应用里切页（不刷新）：对话页的缓存要随清空一起丢掉
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '我的' }).click()
  await page.getByRole('link', { name: /模型服务/ }).click()
  await page.getByRole('link', { name: '隐私与数据' }).click()
  await page.getByRole('region', { name: '清空对话历史' }).getByRole('button', { name: '清空对话历史' }).click()
  const sheet = page.getByRole('dialog', { name: '清空对话历史' })
  await expect(sheet.getByText('开场问候', { exact: false })).toBeVisible()
  await sheet.locator('.chk').click()
  await sheet.getByRole('button', { name: '清空' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('已清空')).toBeVisible()
  expect(await conversationCount(request, token)).toBe(0)

  await page.getByRole('button', { name: '返回' }).click()
  await expect(page).toHaveURL(/\/me$/)
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '对话' }).click()
  await expect(page.getByRole('textbox', { name: '给助手发消息' })).toBeVisible()
  await expect(page.getByText(said)).toHaveCount(0)
})

test('deletes the account and returns to login', async ({ page, request }) => {
  const { token, username, password } = await createUser(request)
  await openAs(page, token, '/settings/privacy')
  await page.getByRole('region', { name: '删除账号与全部数据' }).getByRole('button', { name: '删除账号' }).click()
  const sheet = page.getByRole('dialog', { name: '删除账号与全部数据' })
  const confirm = sheet.getByRole('button', { name: '删除账号' })
  await expect(confirm).toBeDisabled()
  await sheet.getByLabel('登录密码').fill(password)
  await sheet.locator('.chk').click()
  await confirm.click()

  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByText('账号与全部数据已删除')).toBeVisible()
  await expect(page.getByRole('heading', { name: '登录已过期' })).toHaveCount(0)
  expect(await page.evaluate(() => localStorage.getItem('goodlife.token'))).toBeNull()

  // 原账号已不存在：用原来的用户名与密码登录得到“用户名或密码错误”
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('用户名或密码错误')).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test('deletes a model provider', async ({ page, request }) => {
  const { token } = await createUser(request)
  const info = await e2eInfo(request)
  await seedModelService(request, token, info)
  await openAs(page, token, '/settings/models')
  const list = page.getByRole('list', { name: '模型服务' })
  await expect(list).toContainText('本地模拟模型')
  await expect(page.getByRole('list', { name: '当前用途' })).toContainText(info.chat_model_id)

  await list.getByRole('listitem').filter({ hasText: '本地模拟模型' }).getByRole('button', { name: '删除' }).click()
  const sheet = page.getByRole('dialog', { name: '删除这个模型服务' })
  await expect(sheet.getByText('模型与用途分配', { exact: false })).toBeVisible()
  await sheet.getByRole('button', { name: '删除' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.getByText('还没有模型服务。添加一个，填地址与密钥即可。')).toBeVisible()
  await expect(page.getByRole('list', { name: '当前用途' })).toContainText('日常对话未设置')
  await expect(page.getByText('已删除')).toBeVisible()
})
