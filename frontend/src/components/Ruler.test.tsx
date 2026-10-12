import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Ruler } from './Ruler'

function Height({ onChange }: { onChange: (v: number) => void }) {
  const [value, setValue] = useState(165)
  return (
    <Ruler
      label="身高" unit="厘米" value={value} min={50} max={250} step={1} major={10} ppu={8}
      hint="左右拖动刻度，或点数字直接输入。"
      onChange={(v) => {
        setValue(v)
        onChange(v)
      }}
    />
  )
}

describe('Ruler', () => {
  it('changes by one step with the arrow keys', async () => {
    const onChange = vi.fn()
    render(<Height onChange={onChange} />)
    const slider = screen.getByRole('slider', { name: '身高' })
    expect(slider).toHaveAttribute('aria-valuenow', '165')
    expect(slider).toHaveAttribute('aria-valuemin', '50')
    expect(slider).toHaveAttribute('aria-valuemax', '250')
    slider.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenLastCalledWith(166)
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(onChange).toHaveBeenLastCalledWith(164)
    await userEvent.keyboard('{PageUp}')
    expect(onChange).toHaveBeenLastCalledWith(174)
    await userEvent.keyboard('{End}')
    expect(onChange).toHaveBeenLastCalledWith(250)
    await userEvent.keyboard('{ArrowRight}')
    // 到了上限再按不再变
    expect(onChange).toHaveBeenCalledTimes(5)
  })

  it('reads the value with its unit', async () => {
    render(<Height onChange={() => {}} />)
    const slider = screen.getByRole('slider', { name: '身高' })
    expect(slider).toHaveAttribute('aria-valuetext', '165 厘米')
    slider.focus()
    await userEvent.keyboard('{ArrowUp}')
    expect(slider).toHaveAttribute('aria-valuetext', '166 厘米')
    expect(screen.getByText('左右拖动刻度，或点数字直接输入。')).toHaveClass('fld-h')
  })

  it('steps by half a kilogram', async () => {
    const onChange = vi.fn()
    render(<Ruler label="体重" unit="千克" value={56.5} min={20} max={300} step={0.5} major={5} ppu={16} onChange={onChange} />)
    const slider = screen.getByRole('slider', { name: '体重' })
    expect(slider).toHaveAttribute('aria-valuetext', '56.5 千克')
    slider.focus()
    await userEvent.keyboard('{ArrowDown}')
    expect(onChange).toHaveBeenLastCalledWith(56)
  })

  it('takes a typed value after tapping the number', async () => {
    const onChange = vi.fn()
    render(<Height onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '身高 165 厘米，点按直接输入' }))
    const input = screen.getByRole('textbox', { name: '身高' })
    expect(input).toHaveAttribute('inputmode', 'decimal')
    expect(input).toHaveFocus()
    await userEvent.clear(input)
    await userEvent.type(input, '172{Enter}')
    expect(onChange).toHaveBeenLastCalledWith(172)
    expect(screen.getByRole('slider', { name: '身高' })).toHaveAttribute('aria-valuetext', '172 厘米')
    expect(screen.queryByRole('textbox', { name: '身高' })).not.toBeInTheDocument()
  })
})
