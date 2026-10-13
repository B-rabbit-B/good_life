import { describe, expect, it } from 'vitest'
import type { MessageOut } from '../../api/types'
import { HEALTH_DISCLAIMER, NOTICE_HEADER_PREFIX } from '../../lib/contract'
import { capabilities } from '../../test/fixtures/core'
import {
  collapseRetriedUserMessages, evidenceLines, jumpCardsFor, riskCategory, splitAssistantText, visibleWhileStreaming,
} from './agentText'

// 与 app/agent/loop.py 的 run_turn 末尾一样拼：回答、医嘱提醒（guard.medical_notice）、健康提示，用空行隔开
const ANSWER = '今晚可以换成清蒸鱼或鸡胸肉，配一碗杂粮粥。\n\n想再吃点蔬菜，可以加一份白灼菜心。'
const NOTICE = `${NOTICE_HEADER_PREFIX}卤猪肝、酱牛肉。\n卤猪肝：避免动物内脏与浓肉汤（高嘌呤）\n酱牛肉：每日钠不超过 2000 毫克`
const joined = (...parts: string[]) => parts.filter(Boolean).join('\n\n')

function message(over: Partial<MessageOut>): MessageOut {
  return { id: 'm', role: 'user', text: '', evidence: '', flags: [], created_at: '2026-10-12T10:00:00Z', ...over }
}

describe('agent text', () => {
  it('splits answer, notice and disclaimer', () => {
    expect(splitAssistantText(joined(ANSWER, NOTICE, HEALTH_DISCLAIMER))).toEqual({
      answer: ANSWER,
      notice: { lines: [
        `${NOTICE_HEADER_PREFIX}卤猪肝、酱牛肉。`, '卤猪肝：避免动物内脏与浓肉汤（高嘌呤）', '酱牛肉：每日钠不超过 2000 毫克',
      ] },
      disclaimer: HEALTH_DISCLAIMER,
    })
  })

  it('keeps a risk reply whole', () => {
    const reply = '你描述的情况可能需要尽快就医，我不能在这里判断病情。\n请立即拨打 120 急救电话。'
    expect(splitAssistantText(reply)).toEqual({ answer: reply, notice: null, disclaimer: null })
    expect(riskCategory(['risk_severe_symptom'])).toBe('severe_symptom')
    expect(riskCategory(['resolution_clue', 'risk_self_harm'])).toBe('self_harm')
    expect(riskCategory(['guard_fallback'])).toBeNull()
    expect(riskCategory(['risk_unknown_kind'])).toBeNull()
  })

  it('handles an answer without notice', () => {
    expect(splitAssistantText(joined(ANSWER, HEALTH_DISCLAIMER))).toEqual({
      answer: ANSWER, notice: null, disclaimer: HEALTH_DISCLAIMER,
    })
  })

  it('holds back a partial notice or disclaimer while streaming', () => {
    const full = joined(ANSWER, NOTICE, HEALTH_DISCLAIMER)
    // 回答自己的段落之间的空行照常显示
    expect(visibleWhileStreaming(ANSWER.slice(0, 26))).toBe(ANSWER.slice(0, 26))
    for (let end = ANSWER.length; end <= full.length; end += 1) {
      expect(visibleWhileStreaming(full.slice(0, end))).toBe(ANSWER)
    }
    expect(visibleWhileStreaming(`${ANSWER}\n`)).toBe(ANSWER)
    expect(visibleWhileStreaming(`${ANSWER}\n\n以上内容`)).toBe(ANSWER)
    expect(visibleWhileStreaming(`${ANSWER}\n\n以上就是`)).toBe(`${ANSWER}\n\n以上就是`)
  })

  it('collapses a retried user message', () => {
    const messages = [
      message({ id: 'u1', text: '晚饭吃什么' }),
      message({ id: 'u2', text: '晚饭吃什么' }),
      message({ id: 'a1', role: 'assistant', text: '清蒸鱼' }),
      message({ id: 'u3', text: '好的' }),
      message({ id: 'a2', role: 'assistant', text: '好的' }),
      message({ id: 'u4', text: '好的' }),
    ]
    expect(collapseRetriedUserMessages(messages).map((m) => m.id)).toEqual(['u2', 'a1', 'u3', 'a2', 'u4'])
    expect(evidenceLines('清蒸鱼：适合。依据：【医嘱】……\n\n米饭：适合。\n')).toEqual(['清蒸鱼：适合。依据：【医嘱】……', '米饭：适合。'])
    expect(evidenceLines('')).toEqual([])
  })

  it('maps tools to jump cards only for open modules', () => {
    const tools = ['nutrition_search_foods', 'nutrition_log_meal', 'fitness_log_workout', 'medical_submit_order',
      'cycle_record_period', 'nutrition_nearby_restaurants']
    expect(jumpCardsFor(tools, capabilities())).toEqual([
      { to: '/records?tab=diet', label: '去看今天的饮食记录' },
      { to: '/records?tab=training', label: '去看训练记录' },
      { to: '/health/medical?tab=pending', label: '去医嘱页核对' },
      { to: '/health/cycle', label: '去看经期' },
      { to: '/restaurants', label: '去看附近餐厅' },
    ])
    expect(jumpCardsFor(tools, capabilities({ nutrition: false, cycle: false })).map((card) => card.label))
      .toEqual(['去看训练记录', '去医嘱页核对'])
    expect(jumpCardsFor(['nutrition_log_meal', 'nutrition_log_meal'], capabilities())).toHaveLength(1)
  })
})
