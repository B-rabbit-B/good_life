// 验收标准 1：一个新用户只靠界面完成注册、确认免责、建档、添加模型服务、聊天、拍照识别并入库。
// 全程不调用任何种子接口（只读 /__e2e/info 拿本地模拟模型的地址与假密钥）。
import { e2eInfo } from '../support/api'
import { expectRefTag, fillProvider, finishProvider, MEAL_JPG, sendChat, snap } from '../support/flows'
import { expect, test } from '../support/test'

const PASSWORD = 'e2e-pass-123'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('a new user completes the whole flow through the ui only', async ({ page, request }) => {
  const info = await e2eInfo(request)
  const username = `a${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`

  // 注册
  await page.goto('/login')
  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: '注册并继续' }).click()

  // 免责：勾选后才能确认
  await expect(page).toHaveURL(/\/disclaimer$/)
  const accept = page.getByRole('button', { name: '确认并继续' })
  await expect(accept).toBeDisabled()
  await page.getByText('我已阅读并理解以上内容').click()
  await accept.click()

  // 建档第 1 步：拖动身高刻度尺，再用方向键微调
  await expect(page).toHaveURL(/\/onboarding\/1$/)
  const height = page.getByRole('slider', { name: '身高' })
  await expect(height).toHaveAttribute('aria-valuenow', '165')
  const box = await height.boundingBox()
  if (!box) throw new Error('量不到身高刻度尺')
  const y = box.y + box.height / 2
  await page.mouse.move(box.x + box.width / 2, y)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 - 60, y, { steps: 6 })
  await page.mouse.up()
  // 向左拖 60 像素（每厘米 8 像素），指针下的数变大：165 + 7.5 吸附到 173
  await expect(height).toHaveAttribute('aria-valuenow', '173')
  await height.focus()
  await page.keyboard.press('ArrowRight')
  await expect(height).toHaveAttribute('aria-valuenow', '174')
  await page.getByLabel('出生年份').selectOption('1993')
  await page.locator('.opt', { hasText: '女' }).click()
  await page.getByRole('button', { name: '下一步' }).click()

  // 第 2 步：活动与目标
  await expect(page).toHaveURL(/\/onboarding\/2$/)
  await page.locator('.act', { hasText: '轻度' }).click()
  await page.locator('.opt', { hasText: '维持' }).click()
  await page.getByRole('button', { name: '下一步' }).click()

  // 第 3 步：添加一个忌口后完成
  await expect(page).toHaveURL(/\/onboarding\/3$/)
  const avoid = page.locator('.fld', { has: page.locator('.fld-l', { hasText: '忌口' }) })
  await avoid.getByRole('button', { name: '添加' }).click()
  await page.getByLabel('添加忌口').fill('酒精')
  await page.getByLabel('添加忌口').press('Enter')
  await expect(avoid.getByRole('button', { name: '移除酒精' })).toBeVisible()
  await page.getByRole('button', { name: '完成' }).click()

  // 对话页：还没有模型，按提示去添加
  await expect(page).toHaveURL(/\/chat$/)
  await expect(page.getByRole('region', { name: '还没有可用的对话模型' })).toBeVisible()
  await page.getByRole('link', { name: '去添加模型服务' }).click()
  await expect(page).toHaveURL(/\/settings\/models\/new$/)
  await fillProvider(page, info.model_base_url, info.model_key)
  await finishProvider(page, info.chat_model_id, info.vision_model_id)

  // 回到对话（模型服务页是二级页，返回到我的，再从导航进对话）：流式回答、折叠的依据与“仅供参考”
  await page.getByRole('button', { name: '返回' }).click()
  await expect(page).toHaveURL(/\/me$/)
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '对话' }).click()
  await expect(page).toHaveURL(/\/chat$/)
  await expect(page.getByRole('region', { name: '还没有可用的对话模型' })).toHaveCount(0)
  const streamed = page.waitForResponse((r) => r.request().method() === 'POST' && /\/messages$/.test(new URL(r.url()).pathname))
  await sendChat(page, '晚饭吃什么')
  expect((await streamed).headers()['content-type'], '回答是流式的').toContain('text/event-stream')
  const answer = page.locator('.msg-a').last()
  await expect(answer).toContainText('今晚可以吃清蒸鱼配米饭')
  const fold = answer.getByRole('button', { name: /依据/ })
  await expect(fold).toBeVisible()
  await expect(fold).toHaveAttribute('aria-expanded', 'false')
  await expectRefTag(answer)
  await snap(page, 'chat-answer')

  // 对话底座的相册：选 meal.jpg，识别出麻婆豆腐与米饭
  await page.locator('.slab input[type="file"]:not([capture])').setInputFiles(MEAL_JPG)
  await expect(page).toHaveURL(/\/photos\/[0-9a-f-]{36}$/, { timeout: 30_000 })
  const names = page.locator('.item-n>span')
  await expect(names.filter({ hasText: '麻婆豆腐' })).toBeVisible()
  await expect(names.filter({ hasText: '米饭' })).toBeVisible()
  await snap(page, 'photo-result')

  // 确认入库：跳到当天的饮食记录，两项都在且注明来自拍照识别
  await page.getByRole('button', { name: '确认入库' }).click()
  await expect(page).toHaveURL(/\/records\?tab=diet&date=\d{4}-\d{2}-\d{2}$/)
  const meals = page.locator('[data-sensitive-area="meals"]')
  await expect(meals).toContainText('麻婆豆腐')
  await expect(meals).toContainText('米饭')
  await expect(meals.getByText('来自拍照识别').first()).toBeVisible()
  await snap(page, 'diary')
})
