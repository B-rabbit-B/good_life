// 模型服务的接口。本任务只有“我的”页摘要用到的两个列表；配置流程由任务 10 补上。
import { http, HttpResponse, type HttpHandler } from 'msw'
import type { AssignmentOut, ProviderOut } from '../../../api/types'

export function llmHandlers(opts: { providers?: ProviderOut[]; assignments?: AssignmentOut[] } = {}): HttpHandler[] {
  const { providers = [], assignments = [] } = opts
  return [
    http.get('/api/llm/providers', () => HttpResponse.json(providers)),
    http.get('/api/llm/assignments', () => HttpResponse.json(assignments)),
  ]
}
