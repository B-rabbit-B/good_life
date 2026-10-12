// 接口类型的别名，全部取自生成的 schema.d.ts。FastAPI 对重名模型会生成带模块前缀的键，别名指向 openapi.json 里实际的键。
import type { components } from './schema'

type S = components['schemas']

export type UserOut = S['UserOut']
export type LoginRequest = S['LoginRequest']
export type RegisterRequest = S['RegisterRequest']
export type TokenResponse = S['TokenResponse']
export type ProfileOut = S['ProfileOut']
export type ProfileUpdate = S['ProfileUpdate']
export type DisclaimerOut = S['DisclaimerOut']
export type DisclaimerStatus = S['DisclaimerStatus']

export type ConversationOut = S['ConversationOut']
export type ConversationDetailOut = S['ConversationDetailOut']
export type MessageOut = S['MessageOut']
export type TurnOut = S['TurnOut']
export type OpeningOut = S['OpeningOut']
export type OpeningResponse = S['OpeningResponse']
export type AgentSettingsOut = S['app__agent__schemas__SettingsOut']
export type AgentSettingsUpdate = S['SettingsUpdate']

export type MedicalItemOut = S['app__medical__schemas__ItemOut']
export type MedicalEventOut = S['MedicalEventOut']
export type EventOut = S['EventOut']
export type OrderOut = S['OrderOut']
export type ConstraintsOut = S['ConstraintsOut']
export type ContinueBody = S['ContinueBody']

export type SummaryOut = S['SummaryOut']
export type MealOut = S['MealOut']
export type MealCreate = S['MealCreate']
export type NutrientsOut = S['NutrientsOut']
export type FoodDetailOut = S['FoodDetailOut']
export type NutritionSearchOut = S['app__nutrition__schemas__SearchOut']

export type RecognitionOut = S['RecognitionOut']
export type RecognitionSummaryOut = S['RecognitionSummaryOut']
export type PhotoItemOut = S['app__photos__schemas__ItemOut']
export type PhotoItemIn = S['ItemIn']
export type PhotoEvaluationOut = S['app__photos__schemas__EvaluationOut']

export type PeriodOut = S['PeriodOut']
export type DayLogOut = S['DayLogOut']
export type DayLogIn = S['DayLogIn']
export type PredictionOut = S['PredictionOut']
export type PhaseOut = S['PhaseOut']
export type TipsOut = S['TipsOut']
export type CycleStatsOut = S['CycleStatsOut']

export type WeekSummaryOut = S['WeekSummaryOut']
export type WorkoutOut = S['WorkoutOut']
export type WorkoutIn = S['WorkoutIn']
export type ExerciseSearchOut = S['ExerciseSearchOut']
export type ExerciseTrendOut = S['ExerciseTrendOut']

export type RestaurantSettingsOut = S['app__restaurants__schemas__SettingsOut']
export type NeedOut = S['NeedOut']
export type RestaurantSearchIn = S['SearchIn']
export type RestaurantSearchOut = S['app__restaurants__schemas__SearchOut']

export type PresetOut = S['PresetOut']
export type ProviderOut = S['ProviderOut']
export type ModelOut = S['ModelOut']
export type ModelUpdatedOut = S['ModelUpdatedOut']
export type AssignmentOut = S['AssignmentOut']
export type ConnectionReportOut = S['ConnectionReportOut']
export type FetchModelsOut = S['FetchModelsOut']

export type GrantOut = S['GrantOut']
export type AuditOut = S['AuditOut']

/** GET /api/me/capabilities：后端声明为 dict[str, bool]，键固定是这四个模块 */
export type CapabilityKey = 'cycle' | 'medical' | 'nutrition' | 'fitness'
export type Capabilities = Record<CapabilityKey, boolean>
