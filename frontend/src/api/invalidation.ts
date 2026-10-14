// 数据域的失效依赖：写了一个域的数据，哪些查询要跟着重新取。各模块的写操作与一轮对话里智能体的写入工具都按这张表失效，
// 不再各自挑键（一处漏了，别的页面就显示旧数据）。只标记失效：正在显示的查询会重新取，其余等下次用到时再取。
import type { QueryClient, QueryKey } from '@tanstack/react-query'
import { CONSENT_REQUIRED } from '../lib/contract'
import { ApiError } from './errors'
import { qk } from './keys'
import type { OpeningResponse } from './types'

export type Domain = 'nutrition' | 'fitness' | 'cycle' | 'medical' | 'profile'
export const DOMAINS: readonly Domain[] = ['nutrition', 'fitness', 'cycle', 'medical', 'profile']

// 当日摄入与餐次（按日期的全部查询）；食物搜索与食物详情不随写入变化
const NUTRITION: QueryKey[] = [['nutrition', 'summary'], ['nutrition', 'meals']]

/**
 * 每个域写入后要失效的查询前缀（另外每个域都让拍照识别记录失效：草稿的整餐评价按当日摄入、训练、经期、医嘱与档案算）。
 * - 饮食：饮食
 * - 训练：训练、当日摄入（训练改变当天的目标）
 * - 经期：经期、饮食
 * - 医嘱：医嘱、饮食、训练记录（训练记录标出与医嘱的冲突）
 * - 档案：档案、能力清单、饮食、本周训练汇总、经期
 */
const DERIVED: Record<Domain, QueryKey[]> = {
  nutrition: NUTRITION,
  fitness: [['fitness'], ['nutrition', 'summary']],
  cycle: [['cycle'], ...NUTRITION],
  medical: [['medical'], ...NUTRITION, ['fitness', 'workouts']],
  profile: [qk.profile, qk.capabilities, ...NUTRITION, qk.weekSummary, ['cycle']],
}

/**
 * 拍照识别的列表与每条记录重新取（整餐评价会变）；保留的图片（键的第四段是 image）不变，不重取。
 * except 是刚写进缓存的那一条。
 */
export function invalidateRecognitionRecords(queryClient: QueryClient, except?: string): Promise<void> {
  return queryClient.invalidateQueries({
    queryKey: qk.recognitions,
    predicate: (query) => query.queryKey.length <= 3 && (except === undefined || query.queryKey[2] !== except),
  })
}

/** 写了 domain 的数据之后调用：按上表失效相关查询，全部标记完（正在显示的也重新取完）才返回 */
export async function invalidateDomain(queryClient: QueryClient, domain: Domain): Promise<void> {
  await Promise.all([
    ...DERIVED[domain].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    invalidateRecognitionRecords(queryClient),
  ])
}

/**
 * 撤回单独同意（后端已清除该域的全部数据）：该域与跟着变的查询直接从缓存丢掉，开场问候也丢掉（卡片可能带医嘱原文或经期预测日期）。
 * 只标记失效不够：停用的查询（未同意时 enabled 为假）仍会交出缓存里的旧数据，对话页、运动限制条与训练冲突就会显示已清除的内容。
 */
export async function discardDomain(queryClient: QueryClient, domain: Domain): Promise<void> {
  for (const queryKey of [...DERIVED[domain], qk.opening]) queryClient.removeQueries({ queryKey })
  await invalidateRecognitionRecords(queryClient)
}

/**
 * 清空全部对话（后端同时清掉开场问候的记录）：会话列表与每个会话的消息直接从缓存丢掉；今天的开场已经取过的，改成“没有开场”。
 * 开场不整个丢掉也不失效：重新取会让后端为今天再生成一张卡片、再调一次模型。不动“打开应用时主动提问”的设置。
 */
export function discardConversations(queryClient: QueryClient): void {
  queryClient.removeQueries({ queryKey: qk.conversations })
  if (queryClient.getQueryData(qk.opening) !== undefined) queryClient.setQueryData<OpeningResponse>(qk.opening, { opening: null })
}

/** 任何请求回 403 consent_required（例如在另一台设备上撤回了）：同意状态已过期，重新读取，守门随即回到同意面板 */
export function refreshConsentsOnRequired(queryClient: QueryClient, error: unknown): void {
  if (error instanceof ApiError && error.code === CONSENT_REQUIRED) void queryClient.invalidateQueries({ queryKey: qk.consents })
}
