import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LedgerTicks } from './LedgerTicks'

const LABEL = '今日能量：早餐 412，午餐 515，加餐 158，共 1085 千卡；需要 1850 千卡'
const SEGMENTS = [
  { kcal: 412, tone: 1 },
  { kcal: 515, tone: 2 },
  { kcal: 158, tone: 3 },
] as const

describe('LedgerTicks', () => {
  it('draws one tick per 25 kcal up to the larger of total and need', () => {
    const view = render(<LedgerTicks segments={[...SEGMENTS]} need={1850} label={LABEL} />)
    expect(document.querySelectorAll('.lt-ticks i')).toHaveLength(74)
    view.unmount()
    render(<LedgerTicks segments={[...SEGMENTS]} need={null} label="今日能量" />)
    expect(document.querySelectorAll('.lt-ticks i')).toHaveLength(43)
    expect(document.querySelector('.lt-need')).toBeNull()
  })

  it('colors each tick by the segment its midpoint falls in', () => {
    render(<LedgerTicks segments={[...SEGMENTS, { kcal: 100, tone: 4 }]} need={1850} label={LABEL} />)
    // 中点 (i + 0.5) × 25：早餐到 412 是前 16 格，午餐到 927 是后 21 格，加餐到 1085 是 6 格，第四段到 1185 是 4 格
    expect(document.querySelectorAll('.lt-ticks i.s1')).toHaveLength(16)
    expect(document.querySelectorAll('.lt-ticks i.s2')).toHaveLength(21)
    expect(document.querySelectorAll('.lt-ticks i.s3')).toHaveLength(6)
    expect(document.querySelectorAll('.lt-ticks i.s4')).toHaveLength(4)
    expect(document.querySelectorAll('.lt-ticks i:not([class])')).toHaveLength(74 - 47)
  })

  it('labels the graphic as given and keeps the need inside', () => {
    render(<LedgerTicks segments={[...SEGMENTS]} need={1850} label={LABEL} />)
    const img = screen.getByRole('img', { name: LABEL })
    expect(img).toHaveClass('lt')
    expect(img.querySelector('.lt-need')).not.toBeNull()
    expect(screen.getByText('需要 1,850')).toHaveClass('need')
    expect(screen.getByText('1000')).toBeInTheDocument()
  })
})
