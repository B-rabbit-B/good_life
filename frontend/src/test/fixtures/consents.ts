// 单独同意的测试数据：经期与医嘱两项（顺序同后端），默认都已同意；正文按后端的写法用换行分段。
import type { ConsentKind, ConsentOut } from '../../api/types'

export const CONSENT_VERSION = 'consent-test-v1'

export const CONSENT_TEXTS: Record<ConsentKind, string> = {
  cycle: '经期记录会处理你填写的月经起止日期与每日记录。\n处理的必要性：没有这些信息，就无法推算下次月经。\n你可以随时在“我的”页撤回同意。',
  medical: '医嘱会处理你录入的医嘱原文与上传的原件。\n处理的必要性：没有这些信息，就无法遵守你确认过的医嘱。\n你可以随时在“我的”页撤回同意。',
}

const TITLES: Record<ConsentKind, string> = { cycle: '经期记录', medical: '医嘱' }

export function consent(kind: ConsentKind, granted = true, over: Partial<ConsentOut> = {}): ConsentOut {
  return {
    kind,
    title: TITLES[kind],
    text: CONSENT_TEXTS[kind],
    current_version: CONSENT_VERSION,
    granted,
    granted_at: granted ? (kind === 'cycle' ? '2026-10-02T08:00:00Z' : '2026-10-03T08:00:00Z') : null,
    granted_version: granted ? CONSENT_VERSION : null,
    withdrawn_at: null,
    ...over,
  }
}
