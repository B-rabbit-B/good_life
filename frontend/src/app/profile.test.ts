import { describe, expect, it } from 'vitest'
import { completeProfile } from '../test/fixtures/core'
import { firstIncompleteStep, isProfileComplete } from './profile'

describe('profile completeness', () => {
  it('treats a profile with all six onboarding fields as complete', () => {
    expect(isProfileComplete(completeProfile())).toBe(true)
  })

  it('treats a profile missing any one field as incomplete', () => {
    for (const field of ['gender', 'birth_year', 'height_cm', 'weight_kg', 'activity_level', 'goal'] as const) {
      expect(isProfileComplete(completeProfile({ [field]: null })), field).toBe(false)
    }
  })

  it('counts goal none as complete', () => {
    expect(isProfileComplete(completeProfile({ goal: 'none' }))).toBe(true)
  })

  it('does not need the skippable third step', () => {
    const profile = completeProfile({ diet_preferences: [], food_avoidances: [], health_conditions: null })
    expect(isProfileComplete(profile)).toBe(true)
  })

  it('picks step 1 for a missing basic field and step 2 otherwise', () => {
    for (const field of ['gender', 'birth_year', 'height_cm', 'weight_kg'] as const) {
      expect(firstIncompleteStep(completeProfile({ [field]: null })), field).toBe(1)
    }
    expect(firstIncompleteStep(completeProfile({ activity_level: null }))).toBe(2)
    expect(firstIncompleteStep(completeProfile({ goal: null }))).toBe(2)
    expect(firstIncompleteStep(completeProfile({ height_cm: null, goal: null }))).toBe(1)
  })
})
