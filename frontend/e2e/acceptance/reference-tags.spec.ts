// 验收标准 8：所有预测与建议内容旁都有“仅供参考”：对话回答、整餐评价、能量账本、经期阶段与预测、训练的估算消耗、
// 医嘱的解除建议、附近餐厅的提示与已避开的类型。
import type { components } from '../../src/api/schema'
import {
  createUser, e2eInfo, KNEE_LIMIT, logMeal, MOCK_CITY, MOCK_PLACE, openAs, recognizePhoto, seedActiveItem, seedDeckCycle,
  seedDeckTraining, seedModelService, seedProposal, setLocationConsent,
} from '../support/api'
import { expectRefTag, MEAL_JPG, sendChat } from '../support/flows'
import { expect, test } from '../support/test'

type ManualItem = components['schemas']['ManualItemCreate']
type MedicalItem = components['schemas']['app__medical__schemas__ItemOut']

const SPICY: ManualItem = { category: 'diet_avoid', content: '两周内忌食辛辣', subjects: ['辛辣'] }

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('every prediction and suggestion carries a reference tag', async ({ page, request }) => {
  test.setTimeout(120_000)
  const { token } = await createUser(request, { gender: 'female' })
  await seedModelService(request, token, await e2eInfo(request))
  const draft = await recognizePhoto(request, token, MEAL_JPG)
  await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:111101x', grams: 50 })
  await seedDeckCycle(request, token)
  await seedDeckTraining(request, token)
  await seedActiveItem(request, token, SPICY)
  const items = (await (await request.get('/api/medical/items?status=active', {
    headers: { Authorization: `Bearer ${token}` },
  })).json()) as MedicalItem[]
  const knee = items.find((item) => item.content === KNEE_LIMIT)
  if (!knee) throw new Error('没有找到运动限制条目')
  await seedProposal(request, token, knee.id, '用户转述医生说膝盖恢复得不错，可以开始慢跑了')
  await setLocationConsent(request, token, 'denied')

  // 对话回答
  await openAs(page, token, '/chat')
  await sendChat(page, '晚饭吃什么')
  const answer = page.locator('.msg-a').last()
  await expect(answer).toContainText('今晚可以吃清蒸鱼配米饭')
  await expectRefTag(answer)

  // 识别结果的整餐评价
  await page.goto(`/photos/${draft.id}`)
  await expectRefTag(page.getByRole('region', { name: '整餐评价' }))

  // 饮食记录的能量账本
  await page.goto('/records')
  await expectRefTag(page.locator('.ledger'))

  // 经期阶段与预测
  await page.goto('/health/cycle')
  await expectRefTag(page.locator('.phase'))
  await expectRefTag(page.locator('.pred'))

  // 训练的估算消耗
  await page.goto('/records?tab=training')
  const burn = page.locator('.wk-figs > div', { hasText: '估算消耗' })
  await expect(burn.locator('.rng')).toBeVisible()
  await expectRefTag(burn)

  // 医嘱的解除建议
  await page.goto('/health/medical?tab=active')
  await expectRefTag(page.locator('.prop'))

  // 附近餐厅：提示与已避开的类型
  await page.goto('/restaurants')
  await page.getByLabel('地名或地标').fill(MOCK_PLACE)
  await page.getByLabel('城市（可不填）').fill(MOCK_CITY)
  await page.getByRole('button', { name: '查找附近的店' }).click()
  await expect(page.getByRole('list', { name: '附近的店' })).toBeVisible()
  await expectRefTag(page.locator('.notice'))
  await expectRefTag(page.getByRole('region', { name: '已避开的类型' }))
})
