// 守卫与外壳用到的四个接口的测试数据：默认是档案填满、已确认免责、开放全部模块的女性用户。
import type { Capabilities, DisclaimerStatus, ProfileOut, UserOut } from '../../api/types'

export const TEST_TOKEN = 'test-token'
export const DISCLAIMER_VERSION = 'test-v1'

export function testUser(over: Partial<UserOut> = {}): UserOut {
  return { id: '00000000-0000-4000-8000-000000000001', username: 'tester', created_at: '2026-10-01T08:00:00Z', ...over }
}

export function completeProfile(over: Partial<ProfileOut> = {}): ProfileOut {
  return {
    gender: 'female',
    birth_year: 1996,
    height_cm: 162,
    weight_kg: 54,
    activity_level: 'light',
    goal: 'lose_fat',
    diet_preferences: [],
    food_avoidances: [],
    health_conditions: null,
    notes: null,
    cycle_tracking_opt_out: false,
    updated_at: '2026-10-01T08:00:00Z',
    ...over,
  }
}

export function capabilities(over: Partial<Capabilities> = {}): Capabilities {
  return { cycle: true, medical: true, nutrition: true, fitness: true, ...over }
}

export function disclaimerStatus(accepted: boolean): DisclaimerStatus {
  return {
    current_version: DISCLAIMER_VERSION,
    accepted,
    accepted_at: accepted ? '2026-10-01T08:00:00Z' : null,
  }
}
