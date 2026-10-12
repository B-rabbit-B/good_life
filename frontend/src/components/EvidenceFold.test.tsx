import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { EvidenceFold } from './EvidenceFold'

const LINES = ['医嘱：每日钠不超过 2000 毫克', '当日摄入：今天已摄入钠 1,640 毫克', '目标：蛋白质还差 17.6 克']

describe('EvidenceFold', () => {
  it('starts folded with a count pill', () => {
    render(<EvidenceFold lines={LINES} />)
    const trigger = screen.getByRole('button', { name: /依据/ })
    expect(trigger).toHaveClass('fold')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger.querySelector('em')).toHaveTextContent('3')
  })

  it('expands when pressed', async () => {
    render(<EvidenceFold lines={LINES} />)
    const trigger = screen.getByRole('button', { name: /依据/ })
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    for (const line of LINES) expect(screen.getByText(line)).toBeVisible()
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })
})
