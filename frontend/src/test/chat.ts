// 对话页测试的公共准备：按真实路由打开 /chat，并装上会话、开场、待处理列表与模型分配的处理器。
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AssignmentOut, Capabilities } from '../api/types'
import { chatAssignment } from './fixtures/profile'
import { chatHandlers, type ChatOptions } from './msw/handlers/agent'
import { llmHandlers } from './msw/handlers/llm'
import { medicalHandlers, type MedicalOptions } from './msw/handlers/medical'
import { server } from './msw/server'
import { renderRoute } from './render'

export interface ChatSetup extends ChatOptions, MedicalOptions {
  capabilities?: Partial<Capabilities>
  /** 默认已为日常对话选好模型 */
  assignments?: AssignmentOut[]
}

export function renderChat(opts: ChatSetup = {}) {
  const result = renderRoute('/chat', { capabilities: opts.capabilities })
  const chat = chatHandlers(opts)
  const medical = medicalHandlers(opts)
  server.use(...chat.handlers, ...medical.handlers, ...llmHandlers({ assignments: opts.assignments ?? [chatAssignment()] }))
  return { ...result, chat, medical }
}

/** 在输入框里写一句话并按 Enter 发送 */
export async function sendText(user: ReturnType<typeof userEvent.setup>, text: string): Promise<void> {
  const input = await screen.findByRole('textbox', { name: '给助手发消息' })
  await user.type(input, text)
  await user.keyboard('{Enter}')
}

/** 一个可以从测试里放行的闸门 */
export function gate(): { promise: Promise<void>; open: () => void } {
  let open = () => {}
  const promise = new Promise<void>((resolve) => {
    open = resolve
  })
  return { promise, open }
}
