// 数据域的失效依赖：写了一个域的数据，哪些查询要跟着重新取。各模块的写操作与一轮对话里智能体的写入工具都按这张表失效，
// 不再各自挑键（一处漏了，别的页面就显示旧数据）。只标记失效：正在显示的查询会重新取，其余等下次用到时再取。
import type { QueryClient, QueryKey } from '@tanstack/react-query'
import { qk } from './keys'

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
