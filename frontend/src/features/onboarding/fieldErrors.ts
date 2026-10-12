// 把后端的错误归到表单字段上（不是业务判断：说明原文照搬，只决定显示在哪个字段下面）。
// validation_error 的 details 按字段名归位，字段名取 field 的最后一段（列表下标跳过：food_avoidances.2 归到 food_avoidances）；
// username_taken 归到用户名；其余错误（包括 invalid_credentials）归到整个表单。
import { useEffect, type RefObject } from 'react'
import { ApiError } from '../../api/errors'

/** 不属于某个字段、显示在表单上的错误放在这个键下 */
export const FORM_ERROR = 'form'

const FIELD_OF_CODE: Record<string, string> = { username_taken: 'username' }

const fieldName = (field: string) =>
  field.split('.').filter((part) => part !== '' && !/^\d+$/.test(part)).pop() ?? FORM_ERROR

export function fieldErrors(error: ApiError): Record<string, string> {
  if (error.code === 'validation_error' && error.details && error.details.length > 0) {
    const out: Record<string, string> = {}
    for (const { field, message } of error.details) {
      const key = fieldName(field)
      out[key] ??= message
    }
    return out
  }
  return { [FIELD_OF_CODE[error.code] ?? FORM_ERROR]: error.message }
}

/** 档案字段的中文名：给不在字段下显示的错误加上是哪一项 */
export const PROFILE_FIELD_LABELS: Record<string, string> = {
  gender: '性别',
  birth_year: '出生年份',
  height_cm: '身高',
  weight_kg: '体重',
  activity_level: '活动水平',
  goal: '目标',
  diet_preferences: '饮食偏好',
  food_avoidances: '忌口',
  health_conditions: '健康状况',
  cycle_tracking_opt_out: '经期记录',
}

/** 变更（mutation）的错误：没有错误时为空；不是 ApiError 的意外错误归到表单 */
export function errorsOf(error: unknown): Record<string, string> {
  if (error === null || error === undefined) return {}
  if (error instanceof ApiError) return fieldErrors(error)
  return { [FORM_ERROR]: '出了点问题，请稍后再试' }
}

/**
 * 表单上没有字段能显示的那些错误（含表单级错误），按出现顺序。labels 给出字段的中文名时写成“字段名：说明”，
 * 免得一句后端说明离开了字段就不知道说的是哪一项。
 */
export function otherErrors(
  errors: Record<string, string>,
  shown: readonly string[],
  labels: Record<string, string> = {},
): string[] {
  return Object.entries(errors)
    .filter(([key]) => !shown.includes(key))
    .map(([key, message]) => (labels[key] ? `${labels[key]}：${message}` : message))
}

/**
 * 提交失败后把焦点移到 root 里第一个出错的字段（aria-invalid="true"），读屏随之读出它的说明；
 * 没有字段出错时焦点留在原处，表单级错误由 FormError 的 role="alert" 播报。
 */
export function useFocusFirstInvalid(errors: Record<string, string>, root: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    if (Object.keys(errors).length === 0) return
    root.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
  }, [errors, root])
}
