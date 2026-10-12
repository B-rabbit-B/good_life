// 端到端测试的数据准备：全部经后端的真实接口（app.e2e_server 启动的测试库），不直接写数据库。
import { expect, type APIRequestContext, type Page } from '@playwright/test'
import type { components } from '../../src/api/schema'

type Schemas = components['schemas']
type MedicalItem = Schemas['app__medical__schemas__ItemOut']

export interface E2EInfo {
  model_base_url: string
  model_key: string
  bad_key: string
  chat_model_id: string
  vision_model_id: string
}

export interface TestUser {
  username: string
  password: string
  token: string
}

export const TOKEN_KEY = 'goodlife.token'
const PASSWORD = 'e2e-pass-123'
// 六项建档字段：填满后按档案开放全部模块
const COMPLETE_PROFILE: Schemas['ProfileUpdate'] = {
  birth_year: 1996, height_cm: 162, weight_kg: 54, activity_level: 'light', goal: 'lose_fat',
}
// 提取器从这句话里提不出任何条目，用它当手动条目的医嘱单
const MANUAL_ORDER_TEXT = '手动补充的医嘱。'

const auth = (token: string) => ({ Authorization: `Bearer ${token}` })

async function call<T>(
  request: APIRequestContext,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH',
  path: string,
  options: { token?: string; data?: unknown } = {},
): Promise<T> {
  const response = await request.fetch(path, {
    method,
    headers: options.token ? auth(options.token) : {},
    ...(options.data === undefined ? {} : { data: options.data }),
  })
  expect(response.ok(), `${method} ${path} 返回 ${response.status()}：${await response.text()}`).toBe(true)
  return (response.status() === 204 ? undefined : await response.json()) as T
}

function localToday(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function e2eInfo(request: APIRequestContext): Promise<E2EInfo> {
  return call<E2EInfo>(request, 'GET', '/__e2e/info')
}

/** 新注册一个用户并登录；默认女性、已接受免责声明、档案已填满。 */
export async function createUser(
  request: APIRequestContext,
  opts: { gender?: 'female' | 'male'; disclaimer?: boolean; profile?: 'complete' | 'empty' } = {},
): Promise<TestUser> {
  const { gender = 'female', disclaimer = true, profile = 'complete' } = opts
  const stamp = Date.now().toString(36)
  const random = Math.random().toString(36).slice(2, 8)
  const username = `u${stamp}_${random}` // 小写字母、数字与下划线，不超过 32 位
  await call(request, 'POST', '/api/auth/register', { data: { username, password: PASSWORD } })
  const { access_token: token } = await call<Schemas['TokenResponse']>(request, 'POST', '/api/auth/login', {
    data: { username, password: PASSWORD },
  })
  if (disclaimer) {
    const { version } = await call<Schemas['DisclaimerOut']>(request, 'GET', '/api/disclaimer', { token })
    await call(request, 'POST', '/api/disclaimer/accept', { token, data: { version } })
  }
  if (profile === 'complete') {
    await call(request, 'PATCH', '/api/profile', { token, data: { ...COMPLETE_PROFILE, gender } })
  }
  return { username, password: PASSWORD, token }
}

/** 添加本地模拟模型服务、获取模型，并把对话与看图两个用途分配好。 */
export async function seedModelService(
  request: APIRequestContext,
  token: string,
  info: E2EInfo,
): Promise<Schemas['ProviderOut']> {
  const provider = await call<Schemas['ProviderOut']>(request, 'POST', '/api/llm/providers', {
    token,
    data: { name: '本地模拟模型', kind: 'openai_compatible', base_url: info.model_base_url, api_key: info.model_key },
  })
  const fetched = await call<Schemas['FetchModelsOut']>(
    request, 'POST', `/api/llm/providers/${provider.id}/fetch-models`, { token },
  )
  for (const [purpose, modelId] of [['chat', info.chat_model_id], ['vision', info.vision_model_id]] as const) {
    const model = fetched.models.find((m) => m.model_id === modelId)
    expect(model, `获取到的模型里没有 ${modelId}`).toBeDefined()
    await call(request, 'PUT', `/api/llm/assignments/${purpose}`, { token, data: { model_id: model?.id } })
  }
  return provider
}

/** 录入一份医嘱，提取出的条目都处于待确认。 */
export function seedPendingOrder(request: APIRequestContext, token: string, text: string): Promise<Schemas['OrderOut']> {
  return call<Schemas['OrderOut']>(request, 'POST', '/api/medical/orders', { token, data: { text } })
}

/** 手动补充一条医嘱条目并确认，使它生效。 */
export async function seedActiveItem(
  request: APIRequestContext,
  token: string,
  fields: Schemas['ManualItemCreate'],
): Promise<MedicalItem> {
  const order = await seedPendingOrder(request, token, MANUAL_ORDER_TEXT)
  const item = await call<MedicalItem>(request, 'POST', `/api/medical/orders/${order.id}/items`, {
    token, data: fields,
  })
  return call<MedicalItem>(request, 'POST', `/api/medical/items/${item.id}/confirm`, { token })
}

/** 复核日期是今天的手动条目（已确认），会出现在待复核列表里。 */
export function seedReviewDueItem(
  request: APIRequestContext,
  token: string,
  fields: Schemas['ManualItemCreate'],
): Promise<MedicalItem> {
  return seedActiveItem(request, token, { ...fields, review_date: localToday() })
}

/** 代表模型对一条生效条目提出解除建议。 */
export function seedProposal(
  request: APIRequestContext,
  token: string,
  itemId: string,
  reason: string,
): Promise<MedicalItem> {
  return call<MedicalItem>(request, 'POST', `/api/medical/items/${itemId}/propose-resolution`, {
    token, data: { reason },
  })
}

/** 新建一个对话并发一句话（非流式），返回这一轮的回答。 */
export async function sendMessage(
  request: APIRequestContext,
  token: string,
  text: string,
): Promise<Schemas['TurnOut'] & { conversation_id: string }> {
  const conversation = await call<Schemas['ConversationOut']>(request, 'POST', '/api/agent/conversations', {
    token, data: {},
  })
  const turn = await call<Schemas['TurnOut']>(request, 'POST', `/api/agent/conversations/${conversation.id}/messages`, {
    token, data: { text, stream: false },
  })
  return { ...turn, conversation_id: conversation.id }
}

/** 以这个令牌登录的身份打开页面：先打开 / 写入令牌，再跳到目标路径。 */
export async function openAs(page: Page, token: string, path: string): Promise<void> {
  await page.goto('/')
  await page.evaluate(([key, value]) => window.localStorage.setItem(key, value), [TOKEN_KEY, token] as const)
  await page.goto(path)
}
