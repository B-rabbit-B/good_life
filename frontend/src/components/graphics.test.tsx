import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CycleTicks } from './CycleTicks'
import { Icon, ICON_NAMES } from './Icon'
import { StatusMark } from './StatusMark'
import { ThoughtLine } from './ThoughtLine'
import { WillList } from './WillList'

describe('small graphics', () => {
  it('draws every icon hidden from screen readers', () => {
    expect(ICON_NAMES).toHaveLength(25)
    for (const name of ICON_NAMES) {
      const { container, unmount } = render(<Icon name={name} />)
      const svg = container.querySelector('svg')
      expect(svg, name).toHaveAttribute('aria-hidden', 'true')
      expect(svg).toHaveClass('ic')
      expect(svg?.children.length, name).toBeGreaterThan(0)
      unmount()
    }
    const { container } = render(<Icon name="cover" size={20} onGlass />)
    expect(container.querySelector('svg')).toHaveClass('ic', 'ic-m', 'ic-g')
  })

  it('draws step marks for every state', () => {
    const { container } = render(
      <>
        <StatusMark state="todo" index={2} />
        <StatusMark state="current" index={4} />
        <StatusMark state="ok" index={1} />
        <StatusMark state="bad" index={3} />
        <StatusMark state="running" />
        <StatusMark state="ok" />
      </>,
    )
    const marks = Array.from(container.querySelectorAll('[aria-hidden="true"].fs-m, [aria-hidden="true"].pm'))
    expect(marks.map((m) => m.className)).toEqual(['fs-m', 'fs-m cur', 'fs-m ok', 'fs-m bad', 'pm run', 'pm ok'])
    expect(marks[0]).toHaveTextContent('2')
    expect(marks[2]?.querySelector('svg')).not.toBeNull()
  })

  it('shows a waiting line with a caret as a status', () => {
    render(<ThoughtLine text="正在认菜和份量" />)
    const line = screen.getByRole('status')
    expect(line).toHaveTextContent('正在认菜和份量')
    expect(line.querySelector('.caret')).toHaveAttribute('aria-hidden', 'true')
  })

  it('compresses a cycle into one row of ticks', () => {
    const label = '周期刻度：共约 29 天，第 1 到 5 天为经期，今天第 14 天，下次预计在第 28 到 32 天之间开始'
    const { container } = render(<CycleTicks length={29} periodDays={5} predicted={[28, 32]} today={14} label={label} />)
    expect(screen.getByRole('img', { name: label })).toHaveClass('cyc')
    expect(container.querySelectorAll('.cyc-t i')).toHaveLength(34)
    expect(container.querySelectorAll('.cyc-t i.m')).toHaveLength(5)
    expect(container.querySelectorAll('.cyc-t i.p')).toHaveLength(5)
    expect(screen.getByText('今天')).toBeInTheDocument()
    expect(screen.getByText('第 14 天')).toBeInTheDocument()
    expect(screen.getByText('预计下次')).toBeInTheDocument()
  })

  it('lists what will happen with the irreversible item in red', () => {
    render(<WillList items={[{ text: '状态从“待核对”变为“生效中”。' }, { text: '解除不能撤销。', irreversible: true }]} />)
    const list = screen.getByRole('list')
    expect(list).toHaveClass('will')
    expect(screen.getByText('解除不能撤销。')).toHaveClass('irrev')
    expect(screen.getByText('状态从“待核对”变为“生效中”。')).not.toHaveClass('irrev')
  })
})
