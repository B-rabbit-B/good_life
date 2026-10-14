import type { HttpHandler } from 'msw'
import { agentHandlers, chatHandlers } from './agent'
import { authHandlers } from './auth'
import { consentHandlers } from './consents'
import { coreHandlers } from './core'
import { cycleHandlers } from './cycle'
import { fitnessHandlers } from './fitness'
import { grantHandlers } from './grants'
import { llmHandlers } from './llm'
import { medicalHandlers } from './medical'
import { nutritionHandlers } from './nutrition'
import { photosHandlers } from './photos'
import { restaurantHandlers } from './restaurants'

// 各模块的默认处理器放在同目录按模块分的文件里，在这里汇总。
// 默认的会话仓库（chatHandlers）在全部测试之间共用：会发消息的测试用 test/chat.ts 的 renderChat 装自己的一份。
// 识别记录仓库同理：会改动记录的测试在 renderRoute 之后用 server.use 装自己的 photosHandlers。
export const handlers: HttpHandler[] = [
  ...coreHandlers(), ...authHandlers(), ...agentHandlers(), ...chatHandlers().handlers, ...llmHandlers().handlers,
  ...medicalHandlers().handlers, ...nutritionHandlers().handlers, ...photosHandlers().handlers,
  ...cycleHandlers().handlers, ...fitnessHandlers().handlers, ...restaurantHandlers().handlers,
  ...grantHandlers().handlers, ...consentHandlers().handlers,
]
