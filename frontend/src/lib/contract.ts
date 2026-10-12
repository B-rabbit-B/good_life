// 后端固定文案与常量的副本：前端只在这里抄后端的原文，backend/tests/test_frontend_contract.py 逐字核对。
// 改动后端对应的常量时，这里要一起改（那个测试会提醒）。

/** app.agent.safety.HEALTH_DISCLAIMER：拼在助手回答末尾的免责句 */
export const HEALTH_DISCLAIMER = '以上内容仅供日常生活参考，不能替代医生的诊断和建议。'

/** app.agent.guard.NOTICE_HEADER 在 {foods} 之前的部分：输出检查附加的医嘱提醒以它开头 */
export const NOTICE_HEADER_PREFIX = '按你当前生效的医嘱，以下食物不建议：'

/**
 * app.medical.items._due_reason 的四句原文，映射到触发这次复核的是复查日期（review）还是预计结束（end）。
 * 只用于在继续遵守面板里标出触发的那一项，界面上原样显示原文。
 */
export const DUE_REASONS: Record<string, 'review' | 'end'> = {
  '已到复查日期，请确认是否还需要继续遵守': 'review',
  '已过预计结束日期，请确认是否还需要继续遵守': 'end',
  '今天是预计结束日期，请确认是否还需要继续遵守': 'end',
  '即将到预计结束日期，请确认是否还需要继续遵守': 'end',
}

/** app.nutrition.engine.PENDING_REVIEW_NOTE */
export const PENDING_REVIEW_NOTE = '这条医嘱正在待复核，确认解除之前仍按原要求执行。'

/** app.nutrition.engine.SOURCE_NAMES：评价依据的来源名 */
export const SOURCE_NAMES: Record<string, string> = {
  medical: '医嘱',
  cycle: '经期提示',
  goal: '健身目标',
  training: '训练',
  intake: '当日摄入',
  preference: '个人偏好',
}

/** app.photos.matching.REVIEW_REASONS：识别项需要提醒核对的原因代码 */
export const REVIEW_REASON_CODES = ['low_confidence', 'needs_confirmation', 'grams_out_of_range', 'estimated_grams'] as const
export type ReviewReasonCode = (typeof REVIEW_REASON_CODES)[number]

/** app.photos.matching.REVIEW_CONFIDENCE：低于它算“把握较低” */
export const LOW_CONFIDENCE = 0.6

/** app.photos.service.MEAL_NOTE：拍照入库的餐次备注 */
export const PHOTO_MEAL_NOTE = '拍照识别'

/** app.agent.assembly.CLIENT_NAME：应用内助手在审计里的客户端名 */
export const AGENT_CLIENT_NAME = 'agent'

/** app.agent.schemas.MAX_MESSAGE_CHARS */
export const MESSAGE_MAX_CHARS = 2000

/** app.restaurants.needs.MAX_NEEDS */
export const MAX_NEEDS = 3

/** app.agent.loop.RISK_FLAG_PREFIX 与 app.agent.safety.RISK_CATEGORIES：助手回答的风险标记是 risk_ 加类别 */
export const RISK_FLAG_PREFIX = 'risk_'
export const RISK_CATEGORIES = ['medication', 'pregnancy', 'severe_symptom', 'extreme_diet', 'self_harm'] as const
export type RiskCategory = (typeof RISK_CATEGORIES)[number]

/** app.agent.loop.FLAG_CLUE：回答里有医嘱解除的线索（只给“去医嘱页处理”） */
export const FLAG_CLUE = 'resolution_clue'

/** app.agent.loop.FLAG_FALLBACK：输出检查替换成了固定回复 */
export const FLAG_FALLBACK = 'guard_fallback'
