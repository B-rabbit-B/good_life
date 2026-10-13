// 添加模型服务的四步状态：1 填写地址与密钥、2 获取模型、3 测试连通、4 选择用途模型。
// 失败写在出错的那一步：stepForError 按错误码与出错时所在的阶段决定落在哪一步、哪个字段、给什么动作。
import {
  LLM_INVALID_URL, LLM_KEY_REQUIRED_FOR_NEW_URL, LLM_PROVIDER_EXISTS, type LlmCallErrorCode,
} from '../../lib/contract'

export type StepNo = 1 | 2 | 3 | 4
export type StepField = 'name' | 'base_url' | 'api_key'
export type StepState = 'todo' | 'current' | 'ok' | 'bad'

export interface StepStatus {
  state: StepState
  /** 失败时后端的说明原文 */
  message?: string
  code?: string
  field?: StepField
}

export interface FlowState {
  providerId: string | null
  steps: Record<StepNo, StepStatus>
}

/** 出错的阶段：保存（创建或修改）、获取模型、测试连通 */
export type FlowPhase = 'save' | 'fetch' | 'test'
/** 失败那一步的动作：重新保存并获取模型、修改地址（回第 1 步地址字段）、重试获取、重新测试 */
export type FlowAction = 'resave' | 'editUrl' | 'retry' | 'retest'

export type FlowEvent =
  | { type: 'saved'; providerId: string }
  | { type: 'fetched' }
  | { type: 'tested' }
  | { type: 'failed'; phase: FlowPhase; code: string; message: string }
  /** 第 2 步的“修改地址”：把这条说明移到第 1 步的地址字段下 */
  | { type: 'editUrl' }
  /** 重试某一步：它回到“当前”，说明清掉 */
  | { type: 'retry'; step: 2 | 3 }

const INVALID_KEY: LlmCallErrorCode = 'llm_invalid_key'
const BAD_URL: LlmCallErrorCode = 'llm_bad_url'
/** 后端说不支持列出模型（也可能地址有误）：第 2 步除了修改地址，还可以手动添加模型编号 */
export const LISTING_UNSUPPORTED: LlmCallErrorCode = 'llm_listing_unsupported_or_bad_url'
const KEY_CODES = new Set<string>([INVALID_KEY, LLM_KEY_REQUIRED_FOR_NEW_URL])
const ADDRESS_CODES = new Set<string>([BAD_URL, LISTING_UNSUPPORTED])

export function stepForError(code: string, phase: FlowPhase): { step: 1 | 2 | 3; field?: StepField; action: FlowAction } {
  if (phase === 'test') return { step: 3, action: 'retest' }
  if (KEY_CODES.has(code)) return { step: 1, field: 'api_key', action: 'resave' }
  if (code === LLM_INVALID_URL) return { step: 1, field: 'base_url', action: 'resave' }
  if (code === LLM_PROVIDER_EXISTS) return { step: 1, field: 'name', action: 'resave' }
  if (ADDRESS_CODES.has(code)) return { step: 2, action: 'editUrl' }
  if (phase === 'save') return { step: 1, action: 'resave' }
  return { step: 2, action: 'retry' }
}

const todo: StepStatus = { state: 'todo' }

export const initialFlow: FlowState = {
  providerId: null,
  steps: { 1: { state: 'current' }, 2: todo, 3: todo, 4: todo },
}

/** 第 n 步是 current（或带着失败），之前的都完成，之后的都待做 */
function at(step: StepNo, status: StepStatus): FlowState['steps'] {
  const steps = {} as FlowState['steps']
  for (const n of [1, 2, 3, 4] as const) steps[n] = n < step ? { state: 'ok' } : n === step ? status : todo
  return steps
}

export function flowReducer(state: FlowState, event: FlowEvent): FlowState {
  switch (event.type) {
    case 'saved':
      return { providerId: event.providerId, steps: at(2, { state: 'current' }) }
    case 'fetched':
      return { ...state, steps: at(3, { state: 'current' }) }
    case 'tested':
      return { ...state, steps: at(4, { state: 'current' }) }
    case 'failed': {
      const { step, field } = stepForError(event.code, event.phase)
      const status: StepStatus = { state: 'bad', message: event.message, code: event.code, ...(field ? { field } : {}) }
      return { ...state, steps: at(step, status) }
    }
    case 'editUrl': {
      const { message, code } = state.steps[2]
      return { ...state, steps: at(1, { state: 'bad', field: 'base_url', ...(message ? { message } : {}), ...(code ? { code } : {}) }) }
    }
    case 'retry':
      return { ...state, steps: at(event.step, { state: 'current' }) }
  }
}
