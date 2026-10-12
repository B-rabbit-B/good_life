import type { APIRequestContext, Page } from '@playwright/test'
import { createUser, e2eInfo, seedModelService, TOKEN_KEY } from '../support/api'

export interface FrameSpec {
  /** 设计稿里的画面编号（例如 03a），状态面板用 st1 至 st12 */
  id: string
  widths: (360 | 390)[]
  /** 准备数据（只调用真实接口），返回要打开的路径 */
  prepare: (ctx: { request: APIRequestContext; page: Page }) => Promise<string>
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
  // 设计系统一节对样张页
  { id: 'ds', widths: [360, 390], prepare: galleryBlock('ds') },
  // 状态面板 st1 至 st12 对样张页的对应区块；st10 是“一键遮盖”，打开时就遮盖
  ...Array.from({ length: 12 }, (_, i): FrameSpec => {
    const id = `st${i + 1}`
    return { id, widths: [360, 390], prepare: galleryBlock(id, id === 'st10' ? '?covered=1' : '') }
  }),
]
