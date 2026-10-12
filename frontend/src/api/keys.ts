// 查询键：按模块分层，失效时可以按前缀一起刷新（例如 ['medical'] 刷新医嘱的全部查询）。
export const qk = {
  me: ['auth', 'me'] as const,
  disclaimer: ['disclaimer', 'text'] as const,
  disclaimerStatus: ['disclaimer', 'status'] as const,
  profile: ['profile'] as const,
  capabilities: ['capabilities'] as const,

  conversations: ['agent', 'conversations'] as const,
  conversation: (id: string) => ['agent', 'conversations', id] as const,
  opening: ['agent', 'opening'] as const,
  agentSettings: ['agent', 'settings'] as const,

  reviews: ['medical', 'reviews'] as const,
  medicalItems: ['medical', 'items'] as const,
  itemEvents: (id: string) => ['medical', 'items', id, 'events'] as const,
  medicalEvents: (limit: number) => ['medical', 'events', limit] as const,
  orders: ['medical', 'orders'] as const,
  constraints: (category?: string) => ['medical', 'constraints', category ?? 'all'] as const,

  summary: (date: string) => ['nutrition', 'summary', date] as const,
  meals: (date: string) => ['nutrition', 'meals', date] as const,
  foodSearch: (q: string) => ['nutrition', 'food-search', q] as const,
  food: (id: string) => ['nutrition', 'foods', id] as const,

  recognitions: ['photos', 'recognitions'] as const,
  recognition: (id: string) => ['photos', 'recognitions', id] as const,
  recognitionImage: (id: string) => ['photos', 'recognitions', id, 'image'] as const,

  periods: ['cycle', 'periods'] as const,
  dayLogs: (start: string, end: string) => ['cycle', 'day-logs', start, end] as const,
  prediction: ['cycle', 'prediction'] as const,
  phase: ['cycle', 'phase'] as const,
  tips: ['cycle', 'tips'] as const,
  cycleStats: ['cycle', 'stats'] as const,

  weekSummary: ['fitness', 'week-summary'] as const,
  workouts: (start: string, end: string) => ['fitness', 'workouts', start, end] as const,
  exerciseSearch: (q: string) => ['fitness', 'exercise-search', q] as const,
  exerciseTrend: (id: string) => ['fitness', 'exercises', id, 'trend'] as const,

  restaurantSettings: ['restaurants', 'settings'] as const,
  /** 附近餐厅的需求选项（GET /api/restaurants/needs） */
  needs: ['restaurants', 'needs'] as const,

  presets: ['llm', 'presets'] as const,
  providers: ['llm', 'providers'] as const,
  providerModels: (id: string) => ['llm', 'providers', id, 'models'] as const,
  assignments: ['llm', 'assignments'] as const,

  grants: ['agent-grants', 'grants'] as const,
  audits: (clientName?: string) => ['agent-grants', 'audits', clientName ?? 'all'] as const,
}
