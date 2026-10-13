// 对话与开场的测试数据。助手文字按 app/agent/loop.py 的 run_turn 末尾拼：回答、医嘱提醒、健康提示，用空行隔开。
import type { ConversationDetailOut, MessageOut, OpeningOut } from '../../api/types'
import { HEALTH_DISCLAIMER, NOTICE_HEADER_PREFIX } from '../../lib/contract'

export const CONVERSATION_ID = '00000000-0000-4000-8000-0000000000c1'

let nextId = 1
/** 测试里新生成的编号（UUID 形状） */
export function newId(): string {
  nextId += 1
  return `00000000-0000-4000-8000-${String(nextId).padStart(12, '0')}`
}

/** 回答 + 医嘱提醒 + 免责句 */
export function assistantText(answer: string, opts: { notice?: string[]; disclaimer?: boolean } = {}): string {
  const { notice, disclaimer = true } = opts
  const parts = [answer]
  if (notice) parts.push(notice.join('\n'))
  if (disclaimer) parts.push(HEALTH_DISCLAIMER)
  return parts.join('\n\n')
}

/** 医嘱提醒的几行：第一行是固定句，其余“食物：说明” */
export function noticeLines(foods: [string, string][]): string[] {
  return [`${NOTICE_HEADER_PREFIX}${foods.map(([name]) => name).join('、')}。`, ...foods.map(([name, why]) => `${name}：${why}`)]
}

export function userMessage(text: string, over: Partial<MessageOut> = {}): MessageOut {
  return { id: newId(), role: 'user', text, evidence: '', flags: [], created_at: '2026-10-12T10:40:00Z', ...over }
}

export function assistantMessage(text: string, over: Partial<MessageOut> = {}): MessageOut {
  return { id: newId(), role: 'assistant', text, evidence: '', flags: [], created_at: '2026-10-12T10:40:05Z', ...over }
}

export function conversation(messages: MessageOut[] = [], over: Partial<ConversationDetailOut> = {}): ConversationDetailOut {
  return {
    id: CONVERSATION_ID, title: null, created_at: '2026-10-11T10:00:00Z', updated_at: '2026-10-12T10:40:05Z',
    messages, ...over,
  }
}

export function opening(over: Partial<OpeningOut> = {}): OpeningOut {
  return {
    id: '00000000-0000-4000-8000-0000000000e1',
    kind: 'review_due',
    question: '你有一条医嘱（低盐饮食，每日钠不超过 2000 毫克）到了复查日或到期待复核，要不要现在看看？',
    ...over,
  }
}

/** 就医提示的固定回复（app.agent.safety.SAFE_REPLIES 的严重症状一类） */
export const SEVERE_REPLY = '你描述的情况可能需要尽快就医，我不能在这里判断病情，也不能给出处理建议。'
  + '如果症状严重或正在加重，请立即拨打 120 急救电话，或尽快到最近医院的急诊就诊；等待时尽量不要独自一人。'
