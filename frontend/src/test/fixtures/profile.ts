// 入口流程（注册、免责、建档）与“我的”页的测试数据。
import type { AgentSettingsOut, AssignmentOut, DisclaimerOut, ProfileOut, ProviderOut } from '../../api/types'
import { completeProfile, DISCLAIMER_VERSION } from './core'

export const TEST_PASSWORD = 'secret-123'

/** 刚注册的用户：后端第一次读档案时建的空档案 */
export function emptyProfile(over: Partial<ProfileOut> = {}): ProfileOut {
  return completeProfile({
    gender: null, birth_year: null, height_cm: null, weight_kg: null, activity_level: null, goal: null, ...over,
  })
}

/** 三条换行分开的正文（后端的正文没有标记，按换行切成条目） */
export function disclaimerText(over: Partial<DisclaimerOut> = {}): DisclaimerOut {
  return {
    version: DISCLAIMER_VERSION,
    text: '所有内容仅用于日常生活方式参考。\n如果身体不适，请以医嘱为准并及时就医。\n经期预测不能用于避孕或诊断。',
    ...over,
  }
}

export function agentSettings(over: Partial<AgentSettingsOut> = {}): AgentSettingsOut {
  return { openings_enabled: true, ...over }
}

export function provider(over: Partial<ProviderOut> = {}): ProviderOut {
  return {
    id: '00000000-0000-4000-8000-0000000000a1',
    name: '本地模型',
    kind: 'openai_compatible',
    base_url: 'http://127.0.0.1:9000/v1',
    key_hint: 'sk-…abcd',
    created_at: '2026-10-01T08:00:00Z',
    updated_at: '2026-10-01T08:00:00Z',
    ...over,
  }
}

export function chatAssignment(over: Partial<AssignmentOut> = {}): AssignmentOut {
  return {
    purpose: 'chat',
    provider_name: '本地模型',
    model: {
      id: '00000000-0000-4000-8000-0000000000b1',
      provider_id: '00000000-0000-4000-8000-0000000000a1',
      model_id: 'demo-chat',
      display_name: null,
      source: 'fetched',
      capabilities: { chat: true, tools: true, vision: false },
      table_capabilities: { chat: true, tools: true, vision: false },
      overrides: { chat: null, tools: null, vision: null },
      capability_note: null,
    },
    ...over,
  }
}
