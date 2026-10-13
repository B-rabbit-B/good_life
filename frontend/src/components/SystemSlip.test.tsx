import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SystemSlip } from './SystemSlip'

describe('SystemSlip', () => {
  it('is a still glass note marked as written by the system', () => {
    render(<SystemSlip title="医嘱提醒" lines={['按你当前生效的医嘱，以下食物不建议：卤猪肝。', '卤猪肝：避免动物内脏与浓肉汤']} />)
    const note = screen.getByRole('note', { name: '系统附上的医嘱提醒' })
    expect(note).toHaveClass('slip', 'still')
    expect(note).toHaveAttribute('data-tier', 'still')
    expect(screen.getByText('系统附注')).toBeInTheDocument()
    expect(screen.getByText('医嘱提醒')).toBeInTheDocument()
    expect(screen.getByText('按你当前生效的医嘱，以下食物不建议：卤猪肝。')).toBeInTheDocument()
    expect(screen.getByText('卤猪肝：避免动物内脏与浓肉汤')).toBeInTheDocument()
  })
})
