import { describe, expect, it } from 'vitest'
import { fmtBytes, fmtDistance, fmtInt, fmtNum } from './format'

describe('number formats', () => {
  it('groups thousands in integers', () => {
    expect(fmtInt(1085)).toBe('1,085')
    expect(fmtInt(1234567)).toBe('1,234,567')
    expect(fmtInt(999)).toBe('999')
    expect(fmtInt(1084.6)).toBe('1,085')
    expect(fmtInt(-2500)).toBe('-2,500')
  })

  it('keeps the given digits and drops trailing zeros', () => {
    expect(fmtNum(56.5, 1)).toBe('56.5')
    expect(fmtNum(56, 1)).toBe('56')
    expect(fmtNum(0.456, 2)).toBe('0.46')
    expect(fmtNum(1234.5, 1)).toBe('1,234.5')
  })

  it('writes meters below a kilometer and kilometers above', () => {
    expect(fmtDistance(320)).toBe('320 米')
    expect(fmtDistance(999.4)).toBe('999 米')
    expect(fmtDistance(1200)).toBe('1.2 公里')
    expect(fmtDistance(1000)).toBe('1 公里')
    expect(fmtDistance(15340)).toBe('15.3 公里')
  })

  it('writes byte sizes', () => {
    expect(fmtBytes(512)).toBe('512 B')
    expect(fmtBytes(2048)).toBe('2 KB')
    expect(fmtBytes(1.2 * 1024 * 1024)).toBe('1.2 MB')
    expect(fmtBytes(5 * 1024 * 1024)).toBe('5 MB')
  })
})
