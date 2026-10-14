// 端到端测试的数据准备：全部经后端的真实接口（app.e2e_server 启动的测试库），不直接写数据库。
import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
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

/** 新注册一个用户并登录；默认女性、已接受免责声明、已单独同意经期与医嘱、档案已填满。 */
export async function createUser(
  request: APIRequestContext,
  opts: { gender?: 'female' | 'male'; disclaimer?: boolean; consents?: boolean; profile?: 'complete' | 'empty' } = {},
): Promise<TestUser> {
  const { gender = 'female', disclaimer = true, consents = true, profile = 'complete' } = opts
  const stamp = Date.now().toString(36)
  const random = Math.random().toString(36).slice(2, 8)
  const username = `u${stamp}_${random}` // 小写字母、数字与下划线，不超过 32 位
  await call(request, 'POST', '/api/auth/register', { data: { username, password: PASSWORD, age_confirmed: true } })
  const { access_token: token } = await call<Schemas['TokenResponse']>(request, 'POST', '/api/auth/login', {
    data: { username, password: PASSWORD },
  })
  if (disclaimer) {
    const { version } = await call<Schemas['DisclaimerOut']>(request, 'GET', '/api/disclaimer', { token })
    await call(request, 'POST', '/api/disclaimer/accept', { token, data: { version } })
    // 单独同意要在确认免责之后才能给出；按后端返回的当前版本同意两项
    if (consents) {
      for (const consent of await call<Schemas['ConsentOut'][]>(request, 'GET', '/api/consents', { token })) {
        await call(request, 'POST', `/api/consents/${consent.kind}`, { token, data: { version: consent.current_version } })
      }
    }
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

/** 设计稿 07f 的样例原文（头孢呋辛酯片）：提取出一条用药相关饮食注意，带预计结束、没有复查日期 */
export const CEFUROXIME_ORDER = '头孢呋辛酯片 0.25g，每日两次，连服 7 天。服药期间及停药后 7 天内禁止饮酒。一周后门诊复查。'

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

/** 给一份医嘱上传一个证据文件（name 是上传时的文件名） */
export async function uploadEvidence(
  request: APIRequestContext,
  token: string,
  orderId: string,
  file: string,
  name: string,
): Promise<Schemas['EvidenceOut']> {
  const response = await request.post(`/api/medical/orders/${orderId}/evidence`, {
    headers: auth(token),
    multipart: { file: { name, mimeType: 'image/jpeg', buffer: readFileSync(file) } },
  })
  expect(response.status(), `上传证据返回 ${response.status()}：${await response.text()}`).toBe(201)
  return (await response.json()) as Schemas['EvidenceOut']
}

/** 确认解除一条生效条目（只有本人的接口能做） */
export function resolveItem(request: APIRequestContext, token: string, itemId: string): Promise<MedicalItem> {
  return call<MedicalItem>(request, 'POST', `/api/medical/items/${itemId}/resolve`, { token })
}

/** 手动补充一条待核对的条目后作废它（带原因） */
export async function seedVoidedItem(
  request: APIRequestContext,
  token: string,
  fields: Schemas['ManualItemCreate'],
  reason: string,
): Promise<MedicalItem> {
  const order = await seedPendingOrder(request, token, MANUAL_ORDER_TEXT)
  const item = await call<MedicalItem>(request, 'POST', `/api/medical/orders/${order.id}/items`, { token, data: fields })
  return call<MedicalItem>(request, 'POST', `/api/medical/items/${item.id}/void`, { token, data: { reason } })
}

/** 发一句话（非流式），返回这一轮的回答；不给 conversationId 时新建一个对话。 */
export async function sendMessage(
  request: APIRequestContext,
  token: string,
  text: string,
  conversationId?: string,
): Promise<Schemas['TurnOut'] & { conversation_id: string }> {
  const id = conversationId ?? (await call<Schemas['ConversationOut']>(request, 'POST', '/api/agent/conversations', {
    token, data: {},
  })).id
  const turn = await call<Schemas['TurnOut']>(request, 'POST', `/api/agent/conversations/${id}/messages`, {
    token, data: { text, stream: false },
  })
  return { ...turn, conversation_id: id }
}

/** 准备一段对话：新建一个会话并发一句话（要先用 seedModelService 配好对话模型），返回会话编号 */
export async function seedConversation(request: APIRequestContext, token: string, text: string): Promise<string> {
  return (await sendMessage(request, token, text)).conversation_id
}

/** 本人现有的会话数 */
export async function conversationCount(request: APIRequestContext, token: string): Promise<number> {
  return (await call<Schemas['ConversationOut'][]>(request, 'GET', '/api/agent/conversations', { token })).length
}

/** 上传一张测试图片识别为草稿（看图模型是本地模拟服务：meal.jpg 认作麻婆豆腐加米饭） */
export async function recognizePhoto(
  request: APIRequestContext,
  token: string,
  file: string,
): Promise<Schemas['RecognitionOut']> {
  const response = await request.post('/api/photos/recognitions', {
    headers: auth(token),
    multipart: {
      file: { name: 'meal.jpg', mimeType: 'image/jpeg', buffer: readFileSync(file) },
      keep_image: 'false',
    },
  })
  expect(response.status(), `识别返回 ${response.status()}：${await response.text()}`).toBe(201)
  return (await response.json()) as Schemas['RecognitionOut']
}

/** 在识别草稿里加一个营养库里没有完全一致名称的菜，出现待确认项（原有的项按 id 与 food_id 原样保留） */
export function addPendingDish(
  request: APIRequestContext,
  token: string,
  record: Schemas['RecognitionOut'],
  dish: { name: string; portion_text: string },
): Promise<Schemas['RecognitionOut']> {
  const items = [
    ...record.items.map((item) => (item.food_id ? { id: item.id, name: item.name, food_id: item.food_id } : { id: item.id, name: item.name })),
    dish,
  ]
  return call(request, 'PUT', `/api/photos/recognitions/${record.id}/items`, { token, data: { items } })
}

/** 确认入库为今天的某一餐 */
export function confirmRecognition(
  request: APIRequestContext,
  token: string,
  id: string,
  mealType: Schemas['ConfirmIn']['meal_type'],
): Promise<Schemas['RecognitionOut']> {
  return call(request, 'POST', `/api/photos/recognitions/${id}/confirm`, {
    token, data: { eaten_on: localToday(), meal_type: mealType },
  })
}

/** 手动记今天的一项 */
export function logMeal(
  request: APIRequestContext,
  token: string,
  meal: { meal_type: Schemas['MealCreate']['meal_type']; food_id: string; grams: number },
): Promise<Schemas['MealOut']> {
  return call(request, 'POST', '/api/nutrition/meals', { token, data: { eaten_on: localToday(), ...meal } })
}

/** 今天加 offset 天（本地日期，YYYY-MM-DD） */
export function localDate(offset = 0): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 记一次经期（end 为 null 时还没结束） */
export function seedPeriod(
  request: APIRequestContext, token: string, start: string, end: string | null,
): Promise<Schemas['PeriodOut']> {
  return call(request, 'POST', '/api/cycle/periods', { token, data: { start_date: start, end_date: end } })
}

/** 写某一天的经期记录 */
export function seedDayLog(
  request: APIRequestContext, token: string, date: string, body: Schemas['DayLogIn'],
): Promise<Schemas['DayLogOut']> {
  return call(request, 'PUT', `/api/cycle/day-logs/${date}`, { token, data: body })
}

/** 记一次训练 */
export function seedWorkout(request: APIRequestContext, token: string, body: Schemas['WorkoutIn']): Promise<Schemas['WorkoutOut']> {
  return call(request, 'POST', '/api/fitness/workouts', { token, data: body })
}

/** 设计稿 06 的经期：最近一次 13 天前开始、持续 5 天，之前三次相隔 29 到 30 天；今天与 3 天前有当天记录 */
export async function seedDeckCycle(request: APIRequestContext, token: string): Promise<void> {
  for (const offset of [-101, -71, -42, -13]) await seedPeriod(request, token, localDate(offset), localDate(offset + 4))
  await seedDayLog(request, token, localDate(), { mood: 'good' })
  await seedDayLog(request, token, localDate(-3), { mood: 'normal', note: '睡得晚' })
}

/** 记下附近餐厅的定位选择（允许或不允许）；不允许之后页面不再询问 */
export function setLocationConsent(
  request: APIRequestContext, token: string, consent: 'granted' | 'denied',
): Promise<Schemas['app__restaurants__schemas__SettingsOut']> {
  return call(request, 'PUT', '/api/restaurants/settings/consent', { token, data: { consent } })
}

/** 模拟高德认得的地点（app.phase2_acceptance 的 PLACE 与 CITY） */
export const MOCK_PLACE = '国贸'
export const MOCK_CITY = '北京'

/** 设计稿 08 的运动限制 */
export const KNEE_LIMIT = '膝关节术后六周内避免跑跳'

/** 设计稿 08 的训练：一条运动限制（跳），近一周五次训练（开合跳与限制冲突、两次哑铃卧推、动感单车、快走） */
export async function seedDeckTraining(request: APIRequestContext, token: string): Promise<void> {
  await seedActiveItem(request, token, {
    category: 'exercise_limit', content: KNEE_LIMIT, subjects: ['跳'], start_date: localDate(-20), end_date: localDate(20),
  })
  const sets = (n: number, weight_kg: number, reps: number) => Array.from({ length: n }, () => ({ weight_kg, reps }))
  const workouts: Schemas['WorkoutIn'][] = [
    { performed_on: localDate(-6), cardio: [{ exercise_id: 'ex:jumping_jacks', duration_minutes: 15 }], strength: [] },
    { performed_on: localDate(-4), duration_minutes: 45, cardio: [], strength: [{ exercise_id: 'ex:dumbbell_bench_press', sets: sets(4, 10, 10) }] },
    { performed_on: localDate(-2), cardio: [{ exercise_id: 'ex:spinning', duration_minutes: 38 }], strength: [] },
    {
      performed_on: localDate(-1), duration_minutes: 50, cardio: [],
      strength: [{ exercise_id: 'ex:dumbbell_bench_press', sets: sets(4, 12, 10) }, { exercise_id: 'ex:leg_extension', sets: sets(3, 25, 12) }],
    },
    { performed_on: localDate(), cardio: [{ exercise_id: 'ex:brisk_walking', duration_minutes: 35 }], strength: [] },
  ]
  for (const workout of workouts) await seedWorkout(request, token, workout)
}

/** 以这个令牌登录的身份打开页面：先打开 / 写入令牌，再跳到目标路径。 */
export async function openAs(page: Page, token: string, path: string): Promise<void> {
  await page.goto('/')
  await page.evaluate(([key, value]) => window.localStorage.setItem(key, value), [TOKEN_KEY, token] as const)
  await page.goto(path)
}
