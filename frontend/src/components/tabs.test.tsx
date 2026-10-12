import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SegmentedTabs } from './SegmentedTabs'
import { TextTabs } from './TextTabs'

describe('tabs', () => {
  it('renders segmented tabs with a badge and reports the selection', async () => {
    const onSelectionChange = vi.fn()
    render(
      <SegmentedTabs ariaLabel="健康" selectedKey="period" onSelectionChange={onSelectionChange}
        items={[{ id: 'period', label: '经期' }, { id: 'medical', label: '医嘱', badge: 2 }]} />,
    )
    const list = screen.getByRole('tablist', { name: '健康' })
    expect(list).toHaveClass('ttabs')
    expect(list).not.toHaveClass('sm')
    expect(screen.getByRole('tab', { name: '经期' })).toHaveAttribute('aria-selected', 'true')
    const medical = screen.getByRole('tab', { name: /医嘱/ })
    expect(medical.querySelector('.cnt')).toHaveTextContent('2')
    await userEvent.click(medical)
    expect(onSelectionChange).toHaveBeenCalledWith('medical')
  })

  it('renders text tabs as the small variant', () => {
    render(
      <TextTabs ariaLabel="医嘱" selectedKey="active" onSelectionChange={() => {}}
        items={[{ id: 'pending', label: '待核对', badge: 1 }, { id: 'active', label: '生效中 3' }, { id: 'history', label: '历史与审计' }]} />,
    )
    expect(screen.getByRole('tablist', { name: '医嘱' })).toHaveClass('ttabs', 'sm')
    expect(screen.getByRole('tab', { name: '生效中 3' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getAllByRole('tab')).toHaveLength(3)
  })
})
