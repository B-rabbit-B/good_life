// 设置页（模型服务、隐私与数据）的标签映射。只有设置页用，所以不放在 labels.ts（那个文件在对话页首屏的块里）；
// 类型仍取自 labels.ts（生成的接口类型），漏写一项 TypeScript 会报错。
import {
  AGENT_CLIENT_NAME, LLM_INVALID_URL, LLM_KEY_REQUIRED_FOR_NEW_URL, LLM_PROVIDER_EXISTS, type LlmCallErrorCode,
} from './contract'
import type { AuditOutcome, GrantAccess, GrantStatus, ModelCapability, ProviderKind, Purpose } from './labels'

export const ACCESS_LABELS: Record<GrantAccess, string> = { read: '只读', read_write: '读写' }

export const GRANT_STATUS_LABELS: Record<GrantStatus, string> = { active: '有效', expired: '已过期', revoked: '已吊销' }

export const AUDIT_OUTCOME_LABELS: Record<AuditOutcome, string> = { ok: '成功', error: '失败' }

/** 只有应用内助手有中文名，其他客户端名原样显示（用 clientLabel） */
export const CLIENT_LABELS: Record<string, string> = { [AGENT_CLIENT_NAME]: '应用内助手' }
export const clientLabel = (name: string) => CLIENT_LABELS[name] ?? name

export const PURPOSE_LABELS: Record<Purpose, string> = { chat: '日常对话', vision: '看图识别' }

export const PROVIDER_KIND_LABELS: Record<ProviderKind, string> = {
  openai_compatible: 'OpenAI 兼容格式', anthropic: 'Anthropic', gemini: 'Gemini',
}

export const CAPABILITY_LABELS: Record<ModelCapability, string> = { vision: '看图', tools: '工具调用', chat: '对话' }

/** 失败那一步标题右侧的短结论（错误码到中文）；没有列出的错误码写“失败” */
export const LLM_ERROR_SHORT: Record<LlmCallErrorCode, string> = {
  llm_invalid_key: '密钥无效',
  llm_bad_url: '地址有误',
  llm_listing_unsupported_or_bad_url: '列不出模型',
  llm_model_unavailable: '模型不可用',
  llm_quota_exceeded: '额度不足',
  llm_rate_limited: '太频繁',
  llm_timeout: '超时',
  llm_bad_request: '请求被拒',
  llm_provider_error: '服务出错',
}
const OTHER_SHORT: Record<string, string> = {
  [LLM_INVALID_URL]: '地址不合格',
  [LLM_PROVIDER_EXISTS]: '名称重复',
  [LLM_KEY_REQUIRED_FOR_NEW_URL]: '需重填密钥',
}
export const llmErrorShort = (code: string | undefined): string =>
  (code ? (LLM_ERROR_SHORT as Record<string, string>)[code] ?? OTHER_SHORT[code] : undefined) ?? '失败'
