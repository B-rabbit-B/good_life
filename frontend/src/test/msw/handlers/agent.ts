// 智能体的接口。本任务只有“打开应用时主动提问”的设置；对话与开场由任务 6 补上。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { AgentSettingsOut, AgentSettingsUpdate } from '../../../api/types'
import { agentSettings } from '../../fixtures/profile'

/** 每次调用各有一份设置；会改设置的测试在 renderRoute 之后 server.use(...agentHandlers())，免得改动留给下一个测试。 */
export function agentHandlers(initial: AgentSettingsOut = agentSettings()): HttpHandler[] {
  let settings = initial
  return [
    http.get('/api/agent/settings', () => HttpResponse.json(settings)),
    http.put('/api/agent/settings', async ({ request }) => {
      settings = { ...settings, ...((await request.json()) as AgentSettingsUpdate) }
      return HttpResponse.json(settings)
    }),
  ]
}
