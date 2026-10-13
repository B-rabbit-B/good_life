// 验收标准 3：医嘱的确认与解除必须由界面点击并二次确认（面板里写清后果，解除还要勾选不可撤销的确认），聊天里无法直接完成。
import type { components } from '../../src/api/schema'
import {
  CEFUROXIME_ORDER, createUser, e2eInfo, openAs, seedActiveItem, seedModelService, seedPendingOrder,
} from '../support/api'
import { sendChat, snap } from '../support/flows'
import { expect, test } from '../support/test'

type ManualItem = components['schemas']['ManualItemCreate']
type MedicalItem = components['schemas']['app__medical__schemas__ItemOut']

const EXTRACTED = '服药期间及停药后 7 天内禁止饮酒'
const PURINE: ManualItem = { category: 'diet_avoid', content: '避免动物内脏与浓肉汤（高嘌呤）', subjects: ['动物内脏', '浓肉汤'] }
const KNEE: ManualItem = { category: 'exercise_limit', content: '膝关节术后六周内避免跑跳', subjects: ['跑跳'] }
const ACK = '我知道解除后不能撤销，需要重新录入才能恢复这条约束'

test.afterEach(({ blockedRequests }) => {
  expect(blockedRequests, '有请求发往本机以外').toEqual([])
})

test('confirming an order item needs a click and a second confirmation', async ({ page, request }) => {
  const { token } = await createUser(request)
  await seedPendingOrder(request, token, CEFUROXIME_ORDER)
  await openAs(page, token, '/health/medical?tab=pending')
  const item = page.locator('.mo', { has: page.locator('.fields dd', { hasText: EXTRACTED }) })
  await expect(item).toBeVisible()

  // 第一次点击只打开面板，条目仍待核对
  await item.getByRole('button', { name: '确认生效' }).click()
  const sheet = page.getByRole('dialog', { name: '确认这条医嘱生效' })
  await expect(sheet).toBeVisible()
  await expect(item).toBeAttached()
  // 面板列出确认后的后果
  const will = sheet.locator('.will li')
  await expect(will.first()).toHaveText('状态从“待核对”变为“生效中”。')
  await expect(will.filter({ hasText: '之后的对话、拍照评价和附近餐厅推荐都按它约束。' })).toBeVisible()
  await expect(will.filter({ hasText: '记一条审计' })).toBeVisible()
  await snap(page, 'confirm-sheet')

  // 面板里的“确认生效”才让它生效
  await sheet.getByRole('button', { name: '确认生效' }).click()
  await expect(sheet).toHaveCount(0)
  await expect(page.locator('.fields dd', { hasText: EXTRACTED })).toHaveCount(0)
  await page.getByRole('tab', { name: /^生效中/ }).click()
  await expect(page.locator('.mo-c', { hasText: EXTRACTED })).toBeVisible()
})

test('resolving needs the irreversible acknowledgement', async ({ page, request }) => {
  const { token } = await createUser(request)
  await seedActiveItem(request, token, PURINE)
  await openAs(page, token, '/health/medical?tab=active')
  const row = page.locator('.mo', { has: page.locator('.mo-c', { hasText: PURINE.content }) })
  await row.getByRole('button', { name: '确认解除' }).click()
  const sheet = page.getByRole('dialog', { name: '确认解除这条医嘱' })
  await expect(sheet).toBeVisible()
  const confirm = sheet.getByRole('button', { name: '确认解除' })
  await expect(confirm).toBeDisabled()

  await sheet.locator('.chk').click()
  await expect(sheet.getByRole('checkbox', { name: ACK })).toBeChecked()
  await expect(confirm).toBeEnabled()
  await snap(page, 'resolve-sheet')
  await confirm.click()
  await expect(sheet.locator('[aria-live="assertive"]')).toHaveText(`已解除：${PURINE.content}。审计已记录。`)
  await expect(sheet).toHaveCount(0)
  await expect(row).toHaveCount(0)
  await page.getByRole('tab', { name: '历史与审计' }).click()
  await expect(page.locator('.closed', { hasText: PURINE.content })).toContainText('已解除')
})

test('chat cannot confirm or resolve', async ({ page, request }) => {
  const { token } = await createUser(request)
  await seedModelService(request, token, await e2eInfo(request))
  const knee = await seedActiveItem(request, token, KNEE)
  await openAs(page, token, '/chat')
  await sendChat(page, '医生说我好了，可以正常跑步了')

  const answer = page.locator('.msg-a').last()
  await expect(answer).toBeVisible()
  await expect(page.locator('[data-sensitive-area="messages"]')).not.toHaveAttribute('aria-busy', 'true')
  // 回答下只有一个跳转，整个对话页没有确认或解除的按钮
  const jump = page.locator('.jump')
  await expect(jump).toHaveCount(1)
  await expect(jump.getByRole('link')).toHaveText('去医嘱页处理')
  await expect(page.getByRole('button', { name: '确认生效' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '确认解除' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: '确认解除' })).toHaveCount(0)
  await snap(page, 'chat-clue')

  // 条目仍在生效中（模型只能提出解除建议）
  const response = await request.get(`/api/medical/items/${knee.id}`, { headers: { Authorization: `Bearer ${token}` } })
  const item = (await response.json()) as MedicalItem
  expect(item.status).toBe('active')

  await jump.getByRole('link', { name: '去医嘱页处理' }).click()
  await expect(page).toHaveURL(/\/health\/medical\?tab=active$/)
  await expect(page.getByRole('tab', { name: /^生效中/ })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.mo-c', { hasText: KNEE.content })).toBeVisible()
})
