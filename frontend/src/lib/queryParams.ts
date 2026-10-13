// 记录页的查询参数（?tab=、?date=、?meal=）。用 useLocation 自己解析，不用 React Router 的 useSearchParams：
// 后者会把一段只有这里用到的代码拉进首屏的入口块（入口块里放着整个 react-router）。
import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router'

export function useQueryParams(): [URLSearchParams, (next: Record<string, string>) => void] {
  const { search } = useLocation()
  const navigate = useNavigate()
  const params = useMemo(() => new URLSearchParams(search), [search])
  const replace = (next: Record<string, string>) => {
    const merged = new URLSearchParams(search)
    for (const [key, value] of Object.entries(next)) merged.set(key, value)
    void navigate({ search: `?${merged.toString()}` }, { replace: true })
  }
  return [params, replace]
}
