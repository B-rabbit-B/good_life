// 模型服务的测试数据：预设照抄后端（app/llm/kinds.py 的前两个与 Claude），密钥掩码按后端的 key_hint（“****”加末四位），
// 说明原文仿照后端（app/llm/service.py）。密钥都是假的。
import type { AssignmentOut, ConnectionReportOut, ModelOut, PresetOut, ProviderOut } from '../../api/types'

export const GOOD_KEY = 'sk-test-good-key-0001'
export const BAD_KEY = 'sk-test-bad-key-9999'
export const NEW_KEY = 'sk-test-new-key-4242'
export const keyHint = (key: string) => (key.length >= 8 ? `****${key.slice(-4)}` : '****')

export const PRESETS: PresetOut[] = [
  { id: 'qwen', name: '通义千问', kind: 'openai_compatible', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { id: 'deepseek', name: 'DeepSeek', kind: 'openai_compatible', base_url: 'https://api.deepseek.com/v1' },
  { id: 'anthropic', name: 'Claude', kind: 'anthropic', base_url: 'https://api.anthropic.com' },
]

export const INVALID_KEY_MESSAGE = '服务拒绝了这个密钥（401）。请检查密钥是否复制完整、是否属于这个服务，以及账户是否开通了相应权限。'
export const BAD_URL_MESSAGE = '无法连接到服务。请检查服务地址是否拼写正确、本机网络能否访问这个服务。'
export const LISTING_MESSAGE = '服务没有模型列表接口（404）。这个服务可能不提供模型列表接口，也可能是服务地址写错了（例如少了或多了 /v1）；请核对服务地址，或直接手动添加模型编号。'
export const TIMEOUT_MESSAGE = '模型 qwen-plus 在 30 秒内没有回应。请检查网络后重试；服务繁忙时也可以稍后再试。'
export const ASSIGN_WARNING = '该模型已分配为“看图识别”，但现在的能力标注不满足要求，使用时会报错；请重新分配其他模型，或把标注改回来。'
export const LACKS_VISION_MESSAGE = '这个模型的看图能力不是“支持”（对照表标明不支持，或查不到、无法确认）。如果你确认它能看图，请先在模型上手动标注“支持看图”，再分配到看图识别。'

export function provider(over: Partial<ProviderOut> = {}): ProviderOut {
  return {
    id: '71000000-0000-4000-8000-000000000001',
    name: 'DeepSeek',
    kind: 'openai_compatible',
    base_url: 'https://api.deepseek.com/v1',
    key_hint: '****7c2e',
    created_at: '2026-10-01T08:00:00Z',
    updated_at: '2026-10-01T08:00:00Z',
    ...over,
  }
}

type Caps = ModelOut['capabilities']
const caps = (vision: boolean | null, tools: boolean | null, chat: boolean | null): Caps => ({ vision, tools, chat })

export function model(providerId: string, modelId: string, table: Caps, over: Partial<ModelOut> = {}): ModelOut {
  return {
    id: `72000000-0000-4000-8000-${modelId.replace(/[^a-z0-9]/g, '').padStart(12, '0').slice(-12)}`,
    provider_id: providerId,
    model_id: modelId,
    display_name: null,
    source: 'fetched',
    capabilities: table,
    table_capabilities: table,
    overrides: caps(null, null, null),
    capability_note: null,
    ...over,
  }
}

/** 一个服务下获取到的四个模型：一个向量模型（不是对话模型）、一个对话、一个能看图、一个查不到能力 */
export function fetchedModels(providerId: string): ModelOut[] {
  return [
    model(providerId, 'text-embedding-v3', caps(false, false, false)),
    model(providerId, 'qwen-plus', caps(false, true, true)),
    model(providerId, 'qwen-vl-max', caps(true, true, true)),
    model(providerId, 'qwen-custom', caps(null, null, null)),
  ]
}

export function okReport(modelId: string): ConnectionReportOut {
  return {
    conclusion: 'ok', ok: true, message: `连接正常：拉取到 4 个模型，模型 ${modelId} 对话成功。`,
    listing: { ok: true, code: null, message: '拉取到 4 个模型' },
    chat: { ok: true, code: null, message: `模型 ${modelId} 对话成功` },
    models_found: 4, sample_models: [],
  }
}

export function timeoutReport(): ConnectionReportOut {
  return {
    conclusion: 'timeout', ok: false, message: TIMEOUT_MESSAGE,
    listing: { ok: true, code: null, message: '拉取到 4 个模型' },
    chat: { ok: false, code: 'llm_timeout', message: TIMEOUT_MESSAGE },
    models_found: 4, sample_models: [],
  }
}

export function assignment(purpose: AssignmentOut['purpose'], m: ModelOut, providerName: string): AssignmentOut {
  return { purpose, model: m, provider_name: providerName }
}
