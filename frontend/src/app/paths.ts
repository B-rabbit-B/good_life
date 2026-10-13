/**
 * 全部页面的路径。查询参数约定：
 * - /records?tab=diet|training&date=YYYY-MM-DD
 * - /records/meals/new?date=YYYY-MM-DD&meal=breakfast|lunch|dinner|snack
 * - /health/medical?tab=pending|active|history
 */
export const PATHS = {
  root: '/',
  login: '/login',
  disclaimer: '/disclaimer',
  onboarding: '/onboarding/:step',
  chat: '/chat',
  photoNew: '/photos/new',
  photoResult: '/photos/:recId',
  records: '/records',
  mealNew: '/records/meals/new',
  workoutNew: '/records/workouts/new',
  health: '/health',
  cycle: '/health/cycle',
  medical: '/health/medical',
  medicalNew: '/health/medical/new',
  restaurants: '/restaurants',
  me: '/me',
  profileEdit: '/me/profile',
  models: '/settings/models',
  modelNew: '/settings/models/new',
  privacy: '/settings/privacy',
  disclaimerView: '/settings/disclaimer',
  gallery: '/dev/gallery',
} as const

export type PathKey = keyof typeof PATHS

/** 建档第几步的路径 */
export const onboardingPath = (step: 1 | 2 | 3) => `/onboarding/${step}`
