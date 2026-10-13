import type { APIRequestContext, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { components } from '../../src/api/schema'
import {
  addPendingDish, CEFUROXIME_ORDER, confirmRecognition, createUser, e2eInfo, logMeal, MOCK_CITY, MOCK_PLACE, recognizePhoto,
  resolveItem, seedActiveItem, seedDeckCycle, seedDeckTraining, seedModelService, seedPendingOrder, seedProposal,
  seedReviewDueItem, seedVoidedItem, sendMessage, setLocationConsent, TOKEN_KEY, uploadEvidence,
} from '../support/api'

const FIXTURES = join(fileURLToPath(new URL('.', import.meta.url)), '..', '.fixtures')

export interface FrameSpec {
  /** 设计稿里的画面编号（例如 03a），状态面板用 st1 至 st12 */
  id: string
  widths: (360 | 390)[]
  /** 准备数据（只调用真实接口），返回要打开的路径 */
  prepare: (ctx: { request: APIRequestContext; page: Page }) => Promise<string>
  /** 打开页面之后、截图之前在页面上做的事（例如发一句话、点开面板、滚到某处） */
  after?: (page: Page) => Promise<void>
}

/**
 * 样张页的某个区块：先打开样张页并等字体到齐，再返回带 #编号 的同一地址；
 * frames.spec 打开它时是同一文档内的跳转，页面直接滚到该区块（页头吸顶，区块留出页头的高度）。
 */
function galleryBlock(id: string, query = ''): FrameSpec['prepare'] {
  return async ({ page }) => {
    await page.goto(`/dev/gallery${query}`)
    await page.locator(`#${id}`).waitFor()
    await page.evaluate(() => document.fonts.ready)
    return `/dev/gallery${query}#${id}`
  }
}

/** 先打开 / 写入令牌，返回要打开的路径（frames.spec 随后打开它） */
async function signedIn(page: Page, token: string, path: string): Promise<string> {
  await page.goto('/')
  await page.evaluate(([key, value]) => window.localStorage.setItem(key, value), [TOKEN_KEY, token] as const)
  return path
}

/** 设计稿 13a 与 13b 的档案：1993 年、女、轻度、165 厘米、56.5 千克、维持，两组标签与健康状况 */
async function deckProfileUser(request: APIRequestContext): Promise<string> {
  const user = await createUser(request, { profile: 'complete' })
  const response = await request.patch('/api/profile', {
    headers: { Authorization: `Bearer ${user.token}` },
    data: {
      birth_year: 1993, height_cm: 165, weight_kg: 56.5, activity_level: 'light', goal: 'maintain',
      diet_preferences: ['清淡', '少油'], food_avoidances: ['动物内脏', '酒精'], health_conditions: '膝关节半月板术后（2026-08）',
    },
  })
  if (!response.ok()) throw new Error(`准备档案失败：${response.status()}`)
  return user.token
}

type ManualItem = components['schemas']['ManualItemCreate']
const SALT: ManualItem = { category: 'diet_require', content: '低盐饮食，每日钠不超过 2000 毫克', subjects: ['盐'] }
const KNEE: ManualItem = { category: 'exercise_limit', content: '膝关节术后六周内避免跑跳', subjects: ['跑跳'] }
const SPICY: ManualItem = { category: 'diet_avoid', content: '两周内忌食辛辣', subjects: ['辛辣'] }
const HISTORY = ['练完腿，晚饭吃什么好？', '鸡胸肉吃腻了，换成牛肉可以吗？', '午饭吃了番茄炒蛋和米饭，帮我记一下']

const PURINE: ManualItem = { category: 'diet_avoid', content: '避免动物内脏与浓肉汤（高嘌呤）', subjects: ['动物内脏', '浓肉汤'] }

/**
 * 医嘱页的用户（设计稿 07）：一份头孢的医嘱（证据是“出院小结.jpg”）提取出一条待核对；生效中三条：到了复查日的低盐、
 * 带解除建议的膝关节、没有建议的高嘌呤；history 时再有一条已解除、一条带原因作废的
 */
async function medicalUser(request: APIRequestContext, opts: { history?: boolean } = {}): Promise<string> {
  const user = await createUser(request, { profile: 'complete' })
  if (opts.history) {
    await resolveItem(request, user.token, (await seedActiveItem(request, user.token, { ...SPICY, content: '术后两周内避免辛辣刺激食物' })).id)
    await seedVoidedItem(request, user.token, { category: 'diet_require', content: '每日饮水不少于 1500 毫升', subjects: ['饮水'] }, '重复录入')
  }
  const knee = await seedActiveItem(request, user.token, KNEE)
  await seedProposal(request, user.token, knee.id, '医生复查说膝盖恢复得不错，可以开始慢跑了。')
  await seedActiveItem(request, user.token, PURINE)
  await seedReviewDueItem(request, user.token, SALT)
  const order = await seedPendingOrder(request, user.token, CEFUROXIME_ORDER)
  await uploadEvidence(request, user.token, order.id, join(FIXTURES, 'meal.jpg'), '出院小结.jpg')
  return user.token
}

/** 点开一个底部面板并等它停稳（滑入结束、磨砂淡入） */
async function openSheet(page: Page, button: ReturnType<Page['getByRole']>, title: string): Promise<void> {
  await button.click()
  await page.getByRole('dialog', { name: title }).waitFor()
  await page.waitForTimeout(700)
}

/** 对话页的用户：配好模拟模型、写入几轮历史；due 时有一条到了复查日的医嘱与一条带解除建议的；declined 时先把今天的开场都拒掉 */
async function chatUser(request: APIRequestContext, opts: { history?: string[]; due?: boolean; spicy?: boolean; declined?: boolean } = {}) {
  const user = await createUser(request, { profile: 'complete' })
  await seedModelService(request, user.token, await e2eInfo(request))
  if (opts.due) {
    await seedReviewDueItem(request, user.token, SALT)
    const knee = await seedActiveItem(request, user.token, KNEE)
    await seedProposal(request, user.token, knee.id, '用户转述医生说已经好了')
  }
  if (opts.spicy) await seedActiveItem(request, user.token, SPICY)
  let conversation: string | undefined
  for (const text of opts.history ?? []) conversation = (await sendMessage(request, user.token, text, conversation)).conversation_id
  if (opts.declined) {
    const headers = { Authorization: `Bearer ${user.token}` }
    // 拒到今天没有要问的为止（拒掉一类，下一类才会出现）
    for (let i = 0; i < 5; i += 1) {
      const body = (await (await request.get('/api/agent/opening', { headers })).json()) as { opening: { id: string } | null }
      if (!body.opening) break
      await request.post(`/api/agent/opening/${body.opening.id}/decline`, { headers })
    }
  }
  return user.token
}

async function sendInApp(page: Page, text: string, done: string): Promise<void> {
  await page.getByRole('textbox', { name: '给助手发消息' }).fill(text)
  await page.getByRole('button', { name: '发送' }).click() // 会话列表取到之前不可用，click 会等它可用
  await page.locator(done).last().waitFor()
  await page.waitForTimeout(400) // 依据与附注淡入
}

const scrollToEnd = (page: Page) => page.locator('[data-scroller]').evaluate((el) => el.scrollTo({ top: el.scrollHeight }))

/**
 * 03f：一个用户气泡的中线停在吸顶页头的玻璃下，另一个停在对话底座快捷操作那一行下（逐个滚动位置找第一个满足的）；
 * 找不到就失败，不截一张没有气泡在玻璃下的图
 */
async function bubblesUnderGlass(page: Page): Promise<void> {
  const found = await page.locator('[data-scroller]').evaluate((scroller) => {
    const header = document.querySelector('header.top')?.getBoundingClientRect()
    const slab = document.querySelector('.slab')?.getBoundingClientRect()
    if (!header || !slab) return false
    const bubbles = Array.from(document.querySelectorAll('.msg-u>span')).map((el) => {
      const box = el.getBoundingClientRect()
      return box.top + scroller.scrollTop + box.height / 2
    })
    const max = scroller.scrollHeight - scroller.clientHeight
    for (let top = 0; top <= max; top += 2) {
      const mids = bubbles.map((mid) => mid - top)
      const underHeader = mids.some((mid) => mid > header.top + 16 && mid < header.bottom - 20)
      const underDock = mids.some((mid) => mid > slab.top + 8 && mid < slab.top + 46) // 快捷操作那一行（输入框是 80% 白，会把气泡盖住）
      if (underHeader && underDock) {
        scroller.scrollTo({ top })
        return true
      }
    }
    return false
  })
  if (!found) throw new Error('03f：找不到让两个用户气泡分别停在页头与底座下面的滚动位置')
  await page.waitForTimeout(300)
}

/** 模拟模型的地址与密钥（after 里只有 page：用页面的请求上下文取） */
const e2eInfoFromPage = (page: Page) => e2eInfo(page.request)

/** 添加模型服务的第 1 步：自定义的 OpenAI 兼容格式、模拟模型的地址与给定的密钥，保存并获取模型 */
async function fillProviderForm(page: Page, baseUrl: string, key: string): Promise<void> {
  await page.getByLabel('类型').selectOption('kind:openai_compatible')
  await page.getByLabel('名称').fill('通义千问')
  await page.getByLabel('服务地址').fill(baseUrl)
  await page.getByLabel('密钥', { exact: true }).fill(key)
  await page.getByRole('button', { name: '保存并获取模型' }).click()
}

// 每个界面任务往这里加自己的画面
export const FRAMES: FrameSpec[] = [
  // 01 登录（设计稿画的是注册分段）；01b 新用户的免责页；02 建档第 1 步（性别与年份照设计稿填好）
  { id: '01', widths: [360, 390], prepare: () => Promise.resolve('/login') },
  { id: '01b', widths: [360, 390], prepare: async ({ request, page }) => {
    const user = await createUser(request, { disclaimer: false, profile: 'empty' })
    return signedIn(page, user.token, '/disclaimer')
  } },
  { id: '02', widths: [360, 390], prepare: async ({ request, page }) => {
    const user = await createUser(request, { profile: 'empty' })
    const response = await request.patch('/api/profile', {
      headers: { Authorization: `Bearer ${user.token}` },
      data: { gender: 'female', birth_year: 1993, height_cm: 165, weight_kg: 56.5 },
    })
    if (!response.ok()) throw new Error(`准备档案失败：${response.status()}`)
    return signedIn(page, user.token, '/onboarding/1')
  } },
  // 13a 我的（加一个模型服务，摘要是“1 个，对话已设置”）；13b 修改档案
  { id: '13a', widths: [360, 390], prepare: async ({ request, page }) => {
    const token = await deckProfileUser(request)
    await seedModelService(request, token, await e2eInfo(request))
    return signedIn(page, token, '/me')
  } },
  { id: '13b', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await deckProfileUser(request), '/me/profile') },
  // 03 对话：03a 打开时的开场卡片与待处理条；03b 流式回答完成后滚到底（依据、仅供参考、系统附注）；03c 就医提示；
  // 03d 点开场卡片的“继续遵守”；03e 展开待处理条；03f 两个用户气泡分别在页头与底座下面
  { id: '03a', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await chatUser(request, { history: HISTORY.slice(0, 1), due: true }), '/chat') },
  { id: '03b', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await chatUser(request, { history: HISTORY, due: true, spicy: true, declined: true }), '/chat'),
  after: async (page) => {
    await sendInApp(page, '推荐川菜', '.slip')
    await scrollToEnd(page)
  } },
  { id: '03c', widths: [360, 390], prepare: async ({ request, page }) => signedIn(page, await chatUser(request), '/chat'),
    after: (page) => sendInApp(page, '胸口很闷，一直出冷汗，有点喘不上气', '.care') },
  { id: '03d', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await chatUser(request, { history: HISTORY.slice(0, 1), due: true }), '/chat'),
  after: async (page) => {
    await page.getByRole('group', { name: /你有一条医嘱/ }).getByRole('button', { name: '继续遵守' }).click()
    await page.getByRole('dialog', { name: '继续遵守这条医嘱' }).waitFor()
    await page.waitForTimeout(700) // 滑入停稳、磨砂淡入
  } },
  { id: '03e', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await chatUser(request, { history: ['晚饭想吃卤猪肝配白粥，可以吗？'], due: true, declined: true }), '/chat'),
  after: async (page) => {
    await page.getByRole('button', { name: '医嘱待处理 2 条' }).click()
    // 到期原因与提出人来自各条的事件
    await page.getByText(/^待复核，/).waitFor()
    await page.getByText(/^你在 .* 提出，仍在生效/).waitFor()
    await page.waitForTimeout(300) // 箭头翻转
  } },
  { id: '03f', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await chatUser(request, { history: [
      ...HISTORY, '晚饭吃什么', '那明天早饭照今天这样安排可以吗', '好的，我先按这个来，过两天再问你',
      '谢谢你这么细心地帮我安排', '明白了，晚上我会少放点盐', '晚饭想吃卤猪肝配白粥，可以吗？',
    ], due: true, declined: true }), '/chat'),
  after: bubblesUnderGlass },
  // 04 拍照识别：04a 识别请求挂起，停在“识别中”；04b 模拟看图的结果，再加一道营养库里只有相近名称的菜（待确认）；
  // 04c 白图（没有认出食物）
  { id: '04a', widths: [360, 390], prepare: async ({ request, page }) => signedIn(page, await chatUser(request), '/photos/new'),
    after: async (page) => {
      // 让识别的响应迟迟不到：用 Chromium 的网络模拟加 30 秒延迟（page.route 拦下的请求不会触发上传进度，
      // 而这一帧要的是“上传完成、正在认菜”）
      const cdp = await page.context().newCDPSession(page)
      await cdp.send('Network.enable')
      await cdp.send('Network.emulateNetworkConditions', {
        offline: false, latency: 30_000, downloadThroughput: -1, uploadThroughput: -1,
      })
      await page.locator('input[type="file"]:not([capture])').setInputFiles(join(FIXTURES, 'meal.jpg'))
      // 换步时给读屏的那一句：上传完成、正在认菜
      await page.getByText('上传完成，正在认菜和份量', { exact: true }).waitFor({ state: 'attached' })
      await page.waitForTimeout(300)
    } },
  { id: '04b', widths: [360, 390], prepare: async ({ request, page }) => {
    const token = await chatUser(request)
    const record = await recognizePhoto(request, token, join(FIXTURES, 'meal.jpg'))
    await addPendingDish(request, token, record, { name: '卤猪肝', portion_text: '一小碟' })
    return signedIn(page, token, `/photos/${record.id}`)
  } },
  { id: '04c', widths: [360, 390], prepare: async ({ request, page }) => signedIn(page, await chatUser(request), '/photos/new'),
    after: async (page) => {
      await page.locator('input[type="file"]:not([capture])').setInputFiles(join(FIXTURES, 'white.jpg'))
      await page.getByRole('heading', { name: '没有认出食物' }).waitFor({ timeout: 30_000 })
    } },
  // 05 饮食记录：先确认一次识别（午餐），再手动记两项早餐
  { id: '05', widths: [360, 390], prepare: async ({ request, page }) => {
    const token = await chatUser(request)
    const record = await recognizePhoto(request, token, join(FIXTURES, 'meal.jpg'))
    await confirmRecognition(request, token, record.id, 'lunch')
    await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:111101x', grams: 50 })
    await logMeal(request, token, { meal_type: 'breakfast', food_id: 'cfcd:101101x', grams: 250 })
    return signedIn(page, token, '/records')
  },
  after: (page) => page.waitForTimeout(700) }, // 刻度长出与计数结束
  // 06 经期：四次经期（最近一次 13 天前开始）与两天的当天记录
  { id: '06', widths: [360, 390], prepare: async ({ request, page }) => {
    const { token } = await createUser(request, { profile: 'complete' })
    await seedDeckCycle(request, token)
    return signedIn(page, token, '/health/cycle')
  },
  after: (page) => page.locator('.cal-g .d.today').waitFor() },
  // 07 医嘱：07a 生效中；07b 待核对；07c 待核对条目的确认生效面板；07d 带解除建议的条目的确认解除面板；
  // 07e 历史与审计（一条已解除、一条作废）；07f 录入医嘱（照设计稿填好原文、选一张证据）
  { id: '07a', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await medicalUser(request), '/health/medical?tab=active'),
  after: (page) => page.getByText(/^待复核，/).waitFor() },
  { id: '07b', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await medicalUser(request), '/health/medical?tab=pending') },
  { id: '07c', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await medicalUser(request), '/health/medical?tab=pending'),
  after: (page) => openSheet(page, page.locator('.mo').getByRole('button', { name: '确认生效' }), '确认这条医嘱生效') },
  { id: '07d', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await medicalUser(request), '/health/medical?tab=active'),
  after: (page) => openSheet(page, page.locator('.prop').getByRole('button', { name: '确认解除' }), '确认解除这条医嘱') },
  { id: '07e', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, await medicalUser(request, { history: true }), '/health/medical?tab=history'),
  after: (page) => page.locator('.closed .t-cap').first().waitFor() },
  { id: '07f', widths: [360, 390], prepare: async ({ request, page }) =>
    signedIn(page, (await createUser(request, { profile: 'complete' })).token, '/health/medical/new'),
  after: async (page) => {
    await page.getByLabel('医嘱原文').fill(CEFUROXIME_ORDER)
    await page.locator('input[type="file"]:not([capture])').setInputFiles({
      name: '出院小结.jpg', mimeType: 'image/jpeg', buffer: readFileSync(join(FIXTURES, 'meal.jpg')),
    })
    await page.getByRole('list', { name: '证据' }).waitFor()
    await page.waitForTimeout(300)
  } },
  // 08 训练：一条运动限制与近一周五次训练（开合跳与限制冲突）
  { id: '08', widths: [360, 390], prepare: async ({ request, page }) => {
    const { token } = await createUser(request, { profile: 'complete' })
    await seedDeckTraining(request, token)
    return signedIn(page, token, '/records?tab=training')
  },
  after: async (page) => {
    await page.locator('.trend circle.last').waitFor()
    await page.waitForTimeout(700) // 数字数完
  } },
  // 09 附近餐厅：拒绝定位之后，输入模拟高德认得的地点、选清淡与少油，检索后的样子
  { id: '09', widths: [360, 390], prepare: async ({ request, page }) => {
    const { token } = await createUser(request, { profile: 'complete' })
    await setLocationConsent(request, token, 'denied')
    return signedIn(page, token, '/restaurants')
  },
  after: async (page) => {
    await page.getByLabel('地名或地标').fill(MOCK_PLACE)
    await page.getByLabel('城市（可不填）').fill(MOCK_CITY)
    const needs = page.getByRole('group', { name: '需求' })
    await needs.getByRole('button', { name: '清淡' }).click()
    await needs.getByRole('button', { name: '全部 12 项' }).click()
    await needs.getByRole('button', { name: '少油' }).click()
    await page.getByRole('button', { name: '查找附近的店' }).click()
    await page.getByRole('list', { name: '附近的店' }).waitFor()
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  } },
  // 10a 添加模型服务走到第 4 步（本地模拟模型：获取、测试连通之后）；10b 用模拟模型不认的密钥，停在第 1 步的失败
  { id: '10a', widths: [360, 390], prepare: async ({ request, page }) => {
    const { token } = await createUser(request, { profile: 'complete' })
    return signedIn(page, token, '/settings/models/new')
  },
  after: async (page) => {
    const info = await e2eInfoFromPage(page)
    await fillProviderForm(page, info.model_base_url, info.model_key)
    await page.locator('[data-step="3"]').getByRole('button', { name: '测试连通' }).click()
    await page.locator('[data-step="4"]').getByRole('button', { name: '保存用途' }).waitFor()
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  } },
  { id: '10b', widths: [360, 390], prepare: async ({ request, page }) => {
    const { token } = await createUser(request, { profile: 'complete' })
    return signedIn(page, token, '/settings/models/new')
  },
  after: async (page) => {
    const info = await e2eInfoFromPage(page)
    await fillProviderForm(page, info.model_base_url, info.bad_key)
    await page.getByText('错误码 llm_invalid_key').waitFor()
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  } },
  // 设计系统一节对样张页
  { id: 'ds', widths: [360, 390], prepare: galleryBlock('ds') },
  // 状态面板 st1 至 st12 对样张页的对应区块；st10 是“一键遮盖”，打开时就遮盖
  ...Array.from({ length: 12 }, (_, i): FrameSpec => {
    const id = `st${i + 1}`
    return { id, widths: [360, 390], prepare: galleryBlock(id, id === 'st10' ? '?covered=1' : '') }
  }),
]
