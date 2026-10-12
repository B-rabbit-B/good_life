import type { HttpHandler } from 'msw'
import { agentHandlers, chatHandlers } from './agent'
import { authHandlers } from './auth'
import { coreHandlers } from './core'
import { llmHandlers } from './llm'
import { medicalHandlers } from './medical'

// 各模块的默认处理器放在同目录按模块分的文件里，在这里汇总
export const handlers: HttpHandler[] = [
  ...coreHandlers(), ...authHandlers(), ...agentHandlers(), ...chatHandlers().handlers, ...llmHandlers(),
  ...medicalHandlers().handlers,
]
