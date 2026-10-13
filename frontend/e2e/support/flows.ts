// 验收流程（e2e/acceptance）共用的界面步骤：只经界面操作，不调用任何种子接口。
import { expect, type Locator, type Page } from '@playwright/test'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from './test'

/** app.e2e_server 启动时写的两张测试图片：meal.jpg 认作麻婆豆腐加米饭，white.jpg 认作“不是食物” */
export const FIXTURES = join(fileURLToPath(new URL('..', import.meta.url)), '.fixtures')
export const MEAL_JPG = join(FIXTURES, 'meal.jpg')

export const REF_TEXT = '仅供参考'

/** 在对话底座里发一句话（会话列表取到之前不能发送） */
export async function sendChat(page: Page, text: string): Promise<void> {
  await page.getByRole('textbox', { name: '给助手发消息' }).fill(text)
  await expect(page.getByRole('button', { name: '发送' })).toBeEnabled()
  await page.getByRole('button', { name: '发送' }).click()
}

/** 添加模型服务第 1 步：自定义的 OpenAI 兼容格式、给定的地址与密钥，点保存并获取模型 */
export async function fillProvider(page: Page, baseUrl: string, key: string): Promise<void> {
  await page.getByLabel('类型').selectOption('kind:openai_compatible')
  await page.getByLabel('名称').fill('本地模拟模型')
  await page.getByLabel('服务地址').fill(baseUrl)
  await page.getByLabel('密钥', { exact: true }).fill(key)
  await page.getByRole('button', { name: '保存并获取模型' }).click()
}

/**
 * 第 1 步保存后：获取到模型（第 2 步写“N 个”）→ 第 3 步测试连通成功 → 第 4 步对话与看图各选一个模型并保存，
 * 回到模型服务页。
 */
export async function finishProvider(page: Page, chatModel: string, visionModel: string): Promise<void> {
  await expect(page.locator('[data-step="2"] .fs-t small')).toHaveText('2 个')
  await page.locator('[data-step="3"]').getByRole('button', { name: '测试连通' }).click()
  await expect(page.locator('[data-step="3"]')).toHaveClass(/\bok\b/)
  const step4 = page.locator('[data-step="4"]')
  await step4.getByLabel('日常对话', { exact: true }).selectOption(chatModel)
  await step4.getByLabel('看图识别', { exact: true }).selectOption(visionModel)
  await step4.getByRole('button', { name: '保存用途' }).click()
  await expect(page).toHaveURL(/\/settings\/models$/)
}

/** 这块内容里有可见的“仅供参考” */
export async function expectRefTag(scope: Locator): Promise<void> {
  await expect(scope.locator('.ref', { hasText: REF_TEXT }).first()).toBeVisible()
}

/** 模拟应用切到后台再回来：visibilityState 先变 hidden、再变 visible，各派发一次 visibilitychange */
export async function hideAndShowPage(page: Page): Promise<void> {
  await page.evaluate(() => {
    for (const state of ['hidden', 'visible'] as const) {
      Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
      document.dispatchEvent(new Event('visibilitychange'))
    }
  })
}

/**
 * 关键画面截图：写进这个测试自己的结果目录（test-results/ 下，不进仓库）。
 * 先等有限时长的过渡与动画结束（例如吸顶页头的玻璃层淡入），免得拍到半路的画面；无限循环的骨架扫光不等。
 */
export async function snap(page: Page, name: string): Promise<void> {
  await page.evaluate(() => Promise.all(document.getAnimations()
    .filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity)
    .map((animation) => animation.finished.catch(() => undefined))))
  await page.screenshot({ path: test.info().outputPath(`${name}.png`) })
}
