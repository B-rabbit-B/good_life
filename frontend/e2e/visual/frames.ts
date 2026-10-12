import type { APIRequestContext, Page } from '@playwright/test'

export interface FrameSpec {
  /** 设计稿里的画面编号（例如 03a），状态面板用 st1 至 st12 */
  id: string
  widths: (360 | 390)[]
  /** 准备数据（只调用真实接口），返回要打开的路径 */
  prepare: (ctx: { request: APIRequestContext; page: Page }) => Promise<string>
}

// 每个界面任务往这里加自己的画面
export const FRAMES: FrameSpec[] = []
