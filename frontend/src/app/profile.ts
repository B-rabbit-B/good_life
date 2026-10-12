// 建档流程的判断（不是业务规则）：后端没有“建档完成”字段，建档前两步收集的六项都有值即视为填完；第三步可以跳过。
import type { ProfileOut } from '../api/types'

const BASICS = ['gender', 'birth_year', 'height_cm', 'weight_kg'] as const
const ACTIVITY_AND_GOAL = ['activity_level', 'goal'] as const

const filled = (p: ProfileOut, field: keyof ProfileOut) => p[field] !== null && p[field] !== undefined

export function isProfileComplete(p: ProfileOut): boolean {
  return [...BASICS, ...ACTIVITY_AND_GOAL].every((field) => filled(p, field))
}

/** 第 1 步是基本信息（性别、出生年份、身高、体重），第 2 步是活动与目标。 */
export function firstIncompleteStep(p: ProfileOut): 1 | 2 {
  return BASICS.every((field) => filled(p, field)) ? 2 : 1
}
