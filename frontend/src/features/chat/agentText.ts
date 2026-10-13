// 助手回答的拆分与跳转：只按后端的两句固定文案（contract.ts）切开，不改写任何内容。
// 后端把 回答、医嘱提醒、健康提示 用空行拼成一段（app/agent/loop.py 的 run_turn 末尾），风险话题的固定回复不带后两者。
import type { Capabilities, CapabilityKey, MessageOut } from '../../api/types'
import {
  HEALTH_DISCLAIMER, NOTICE_HEADER_PREFIX, RISK_CATEGORIES, RISK_FLAG_PREFIX, type JumpTool, type RiskCategory,
} from '../../lib/contract'

const GAP = '\n\n'

export interface AssistantParts {
  answer: string
  /** 输出检查附加的医嘱提醒：第一行是“按你当前生效的医嘱，以下食物不建议：……。”，其余每行“食物：说明” */
  notice: { lines: string[] } | null
  disclaimer: string | null
}

/** 把助手的整段文字拆成回答、医嘱提醒与末尾的免责句 */
export function splitAssistantText(text: string): AssistantParts {
  let rest = text
  let disclaimer: string | null = null
  if (rest.endsWith(GAP + HEALTH_DISCLAIMER)) {
    disclaimer = HEALTH_DISCLAIMER
    rest = rest.slice(0, rest.length - GAP.length - HEALTH_DISCLAIMER.length)
  }
  const at = rest.lastIndexOf(GAP + NOTICE_HEADER_PREFIX)
  if (at === -1) return { answer: rest, notice: null, disclaimer }
  const lines = rest.slice(at + GAP.length).split('\n').filter((line) => line !== '')
  return { answer: rest.slice(0, at), notice: { lines }, disclaimer }
}

const FIXED = [NOTICE_HEADER_PREFIX, HEALTH_DISCLAIMER]
const holdsFixed = (rest: string) => FIXED.some((fixed) => fixed.startsWith(rest) || rest.startsWith(fixed))

/**
 * 流式过程中能显示的部分：某个空行之后的文字是医嘱提醒或免责句的开头（或正是它们）时，只显示到那个空行之前，
 * 免得附注与免责句在流入时闪进气泡（它们在流完后各自出现在气泡外与气泡底部）。末尾单独的换行也先不显示。
 * 回答自己段落之间的空行照常显示。
 */
export function visibleWhileStreaming(acc: string): string {
  for (let at = acc.indexOf(GAP); at !== -1; at = acc.indexOf(GAP, at + 1)) {
    if (holdsFixed(acc.slice(at + GAP.length))) return acc.slice(0, at)
  }
  return acc.endsWith('\n') ? acc.slice(0, -1) : acc
}

/** 回答的风险类别（risk_ 加类别）；不是风险话题或类别不认识时为 null */
export function riskCategory(flags: string[]): RiskCategory | null {
  for (const flag of flags) {
    if (!flag.startsWith(RISK_FLAG_PREFIX)) continue
    const category = flag.slice(RISK_FLAG_PREFIX.length)
    if ((RISK_CATEGORIES as readonly string[]).includes(category)) return category as RiskCategory
  }
  return null
}

/**
 * 后端先保存用户消息再回答，没有删除接口，所以失败后用同一句话重试会存两遍：相邻两条用户消息文字相同时只留后一条。
 */
export function collapseRetriedUserMessages(messages: MessageOut[]): MessageOut[] {
  return messages.filter((message, i) => {
    const next = messages[i + 1]
    return !(message.role === 'user' && next?.role === 'user' && next.text === message.text)
  })
}

/** 依据段每个食物一行（后端用换行分隔） */
export function evidenceLines(evidence: string): string[] {
  return evidence.split('\n').map((line) => line.trim()).filter(Boolean)
}

/** 回答里用过的工具（智能体工具名）对应的“去看看”跳转；模块没有开放的不给 */
const TOOL_JUMPS: Record<JumpTool, { to: string; label: string; module: CapabilityKey }> = {
  nutrition_log_meal: { to: '/records?tab=diet', label: '去看今天的饮食记录', module: 'nutrition' },
  fitness_log_workout: { to: '/records?tab=training', label: '去看训练记录', module: 'fitness' },
  medical_submit_order: { to: '/health/medical?tab=pending', label: '去医嘱页核对', module: 'medical' },
  cycle_record_period: { to: '/health/cycle', label: '去看经期', module: 'cycle' },
  nutrition_nearby_restaurants: { to: '/restaurants', label: '去看附近餐厅', module: 'nutrition' },
}

export function jumpCardsFor(toolsUsed: string[], caps: Capabilities): { to: string; label: string }[] {
  const cards: { to: string; label: string }[] = []
  for (const tool of new Set(toolsUsed)) {
    const jump = (TOOL_JUMPS as Partial<Record<string, (typeof TOOL_JUMPS)[JumpTool]>>)[tool]
    if (jump && caps[jump.module]) cards.push({ to: jump.to, label: jump.label })
  }
  return cards
}
