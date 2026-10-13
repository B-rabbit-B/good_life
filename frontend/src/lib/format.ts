// 数字格式：千分位用英文逗号（与设计稿一致：1,085），不依赖浏览器的区域设置。

const group = (digits: string) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')

/** 取整并加千分位：1085 写作 1,085 */
export function fmtInt(n: number): string {
  const rounded = Math.round(n)
  return `${rounded < 0 ? '-' : ''}${group(String(Math.abs(rounded)))}`
}

/** 最多保留 digits 位小数，去掉末尾的 0，整数部分加千分位：56.0 → 56，1234.5 → 1,234.5 */
export function fmtNum(n: number, digits: number): string {
  const fixed = Math.abs(n).toFixed(digits)
  const [whole = '0', fraction = ''] = fixed.split('.')
  const trimmed = fraction.replace(/0+$/, '')
  const sign = n < 0 && Number(fixed) !== 0 ? '-' : ''
  return `${sign}${group(whole)}${trimmed ? `.${trimmed}` : ''}`
}

/** 固定保留 digits 位小数（不去掉末尾的 0），整数部分加千分位：营养表的 128.0 克、52.4 克 */
export function fmtFixed(n: number, digits: number): string {
  const fixed = Math.abs(n).toFixed(digits)
  const [whole = '0', fraction] = fixed.split('.')
  const sign = n < 0 && Number(fixed) !== 0 ? '-' : ''
  return `${sign}${group(whole)}${fraction === undefined ? '' : `.${fraction}`}`
}

/** 不足 1000 米写“320 米”，否则“1.2 公里” */
export function fmtDistance(meters: number): string {
  const rounded = Math.round(meters)
  return rounded < 1000 ? `${rounded} 米` : `${fmtNum(meters / 1000, 1)} 公里`
}

/** 文件大小：“512 B”“2 KB”“1.2 MB” */
export function fmtBytes(n: number): string {
  if (n < 1024) return `${Math.round(n)} B`
  if (n < 1024 * 1024) return `${fmtNum(n / 1024, 1)} KB`
  return `${fmtNum(n / (1024 * 1024), 1)} MB`
}
