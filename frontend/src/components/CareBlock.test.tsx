import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CareBlock } from './CareBlock'

describe('CareBlock', () => {
  it('is an alert with a call button per number and the fixed note', () => {
    render(<CareBlock titleKey="careSevere" text="你描述的胸口发闷可能需要紧急处理。" phones={['120', '12356']} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveClass('care')
    expect(screen.getByRole('heading', { name: '请尽快就医' })).toBeInTheDocument()
    expect(screen.getByText('你描述的胸口发闷可能需要紧急处理。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '拨打 120' })).toHaveAttribute('href', 'tel:120')
    expect(screen.getByRole('link', { name: '拨打 12356' })).toHaveAttribute('href', 'tel:12356')
    expect(screen.getByRole('link', { name: '拨打 120' })).toHaveClass('btn', 'btn-blk')
    expect(screen.getByText('这是一条固定的安全提示，不是模型生成的。')).toBeInTheDocument()
    // 不可折叠、不可关闭
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
