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
export const RISK_CATEGORIES = ['medication', 'pregnancy', 'severe_symptom', 'extreme_diet', 'self_harm', 'minor_weight_loss'] as const
export type RiskCategory = (typeof RISK_CATEGORIES)[number]

/** app.agent.loop.FLAG_CLUE：回答里有医嘱解除的线索（只给“去医嘱页处理”） */
export const FLAG_CLUE = 'resolution_clue'

/** app.agent.loop.FLAG_FALLBACK：输出检查替换成了固定回复 */
export const FLAG_FALLBACK = 'guard_fallback'

/** app.agent.openings.OPENING_KINDS：主动开场的类别（按优先级） */
export const OPENING_KINDS = ['review_due', 'period_soon', 'trained_no_meal_yesterday', 'no_meal_today', 'profile_stale'] as const
export type OpeningKind = (typeof OPENING_KINDS)[number]

/** 回答下面给“去看看”跳转卡片的智能体工具名（app.sdk.tooling.tool_name，都在 agent_registry 里） */
export const JUMP_TOOLS = ['nutrition_log_meal', 'fitness_log_workout', 'medical_submit_order', 'cycle_record_period', 'nutrition_nearby_restaurants'] as const
export type JumpTool = (typeof JUMP_TOOLS)[number]

/**
 * app.medical.items.validate_item_dates 的两句 invalid_item_dates 原文，映射到出错的字段（复查日期 review、预计结束 end）；
 * 继续遵守面板据此把说明写在对应字段下面，界面上原样显示原文。
 */
export const INVALID_DATE_REASONS: Record<string, 'review' | 'end'> = {
  '预计结束日期不能早于生效日期': 'end',
  '复查日期不能早于生效日期': 'review',
}

/** app.llm.service.LLM_ERRORS 的接口错误码（调用模型服务出错时，按后端的顺序）；添加模型服务的四步按它们决定失败落在哪一步 */
export const LLM_CALL_ERROR_CODES = ['llm_invalid_key', 'llm_bad_url', 'llm_listing_unsupported_or_bad_url', 'llm_model_unavailable', 'llm_quota_exceeded', 'llm_rate_limited', 'llm_timeout', 'llm_bad_request', 'llm_provider_error'] as const
export type LlmCallErrorCode = (typeof LLM_CALL_ERROR_CODES)[number]

/** 保存模型服务时落在第 1 步字段上的错误码：app.llm.service 的同名服务与改地址须重填密钥，app.llm.urls 的地址不合格 */
export const LLM_PROVIDER_EXISTS = 'llm_provider_exists'
export const LLM_KEY_REQUIRED_FOR_NEW_URL = 'llm_key_required_for_new_url'
export const LLM_INVALID_URL = 'llm_invalid_url'

/** app.sdk.client 写入审计的结果（成功 ok、失败 error） */
export const AUDIT_OUTCOMES = ['ok', 'error'] as const

/** app.medical.schemas.Content：医嘱条目内容的长度上限 */
export const MAX_CONTENT = 500
/** app.medical.schemas.Reason：作废、解除等理由的长度上限 */
export const MAX_REASON = 500
/** app.cycle.schemas.DayLogIn.note：经期日记录备注的长度上限 */
export const MAX_NOTE = 500
/** app.photos.recognition.MAX_NAME_LENGTH：识别项菜名与份量说法的长度上限 */
export const MAX_NAME_LENGTH = 30
/** app.medical.schemas.OrderCreate.text：医嘱原文的长度上限 */
export const MAX_TEXT = 5000
/** app.common.age.MIN_AGE：注册时确认“已年满 N 周岁”的 N（档案的出生年份不满这个年龄时后端拒绝） */
export const MIN_AGE = 14
/** app.medical.orders.MAX_EVIDENCE_BYTES：医嘱原件文件的大小上限 */
export const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
/** app.medical.orders.MAX_EVIDENCE_PER_ORDER：每份医嘱最多上传的原件份数 */
export const MAX_EVIDENCE_FILES = 10

/** 界面按错误码分支的几个接口错误码（后端没有常量，test_frontend_contract.py 按抛出处的源码原文核对） */
export const STILL_DUE = 'still_due'
export const SUBJECTS_REQUIRED = 'subjects_required'
export const USERNAME_TAKEN = 'username_taken'
export const PHOTO_ITEMS_NEED_CONFIRMATION = 'photo_items_need_confirmation'
export const PHOTO_GRAMS_OUT_OF_RANGE = 'photo_grams_out_of_range'
export const AGENT_MODEL_NOT_CONFIGURED = 'agent_model_not_configured'
export const DISCLAIMER_NOT_ACCEPTED = 'disclaimer_not_accepted'
export const RESTAURANT_LOCATION_NOT_GRANTED = 'restaurant_location_not_granted'
export const CONSENT_REQUIRED = 'consent_required'
export const CONSENT_OUTDATED = 'consent_outdated'
export const PASSWORD_INCORRECT = 'password_incorrect'

/**
 * 会改动用户数据的智能体工具（app.sdk.tooling.agent_registry 里 level 为 write 的，加上 app.agent.assembly 的 remember_preference）
 * 各自改动的数据域；一轮对话结束后按 tools_used 查这张表，让对应页面的缓存失效。
 */
export const WRITE_TOOL_DOMAINS: Record<string, 'nutrition' | 'fitness' | 'cycle' | 'medical' | 'profile'> = {
  nutrition_log_meal: 'nutrition',
  fitness_log_workout: 'fitness',
  cycle_record_period: 'cycle',
  medical_submit_order: 'medical',
  medical_propose_resolution: 'medical',
  remember_preference: 'profile',
}
