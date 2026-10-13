// 验收标准 5：设置页能完成“填地址与密钥、获取模型、测试、选择用途模型”的完整流程（密钥不对时第 1 步报错并给错误码）。
import { createUser, e2eInfo, openAs } from '../support/api'
import { fillProvider, finishProvider, snap } from '../support/flows'
import { expect, test } from '../support/test'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('address, key, fetch, test and assign work end to end', async ({ page, request }) => {
  const info = await e2eInfo(request)
  const { token } = await createUser(request)
  await openAs(page, token, '/me')
  await page.getByRole('link', { name: /模型服务/ }).click()
  await expect(page).toHaveURL(/\/settings\/models$/)
  await page.getByRole('link', { name: /添加模型服务/ }).first().click()
  await expect(page).toHaveURL(/\/settings\/models\/new$/)

  // 密钥不对：错误写在第 1 步，带错误码
  await fillProvider(page, info.model_base_url, info.bad_key)
  const step1 = page.locator('[data-step="1"]')
  await expect(step1).toHaveClass(/\bbad\b/)
  await expect(step1.getByText('错误码 llm_invalid_key')).toBeVisible()
  const key = page.getByLabel('密钥', { exact: true })
  await expect(key).toHaveAttribute('aria-invalid', 'true')
  await snap(page, 'bad-key')

  // 换成正确的假密钥重新保存：获取到两个模型、测试连通、对话与看图各选一个
  await key.fill(info.model_key)
  await page.getByRole('button', { name: '重新保存并获取模型' }).click()
  await finishProvider(page, info.chat_model_id, info.vision_model_id)
  const uses = page.getByRole('list', { name: '当前用途' })
  await expect(uses).toContainText(info.chat_model_id)
  await expect(uses).toContainText(info.vision_model_id)
  await snap(page, 'models')

  // 返回我的页：模型服务一行写“对话已设置”
  await page.getByRole('button', { name: '返回' }).click()
  await expect(page).toHaveURL(/\/me$/)
  await expect(page.getByRole('link', { name: /模型服务/ })).toContainText('1 个，对话已设置')
})
