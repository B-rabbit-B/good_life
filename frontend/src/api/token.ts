// 登录令牌存在 localStorage；隐私模式等情况下读写会抛错，一律当作没有令牌（写不进去就只在本次请求里用不上）。

export const TOKEN_KEY = 'goodlife.token'

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // 存不下时只能下次重新登录
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // 读不到也就不必清
  }
}
