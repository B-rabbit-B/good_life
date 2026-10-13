import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'
import { ButtonLink } from './ButtonLink'
import { IconButton } from './IconButton'

describe('buttons', () => {
  it('renders the class names of every variant', () => {
    const cases = [
      ['primary', ['btn', 'btn-pri']],
      ['quiet', ['btn', 'btn-qt']],
      ['text', ['btn-txt']],
      ['danger', ['btn', 'btn-dng']],
      ['danger-outline', ['btn', 'btn-dng-qt']],
    ] as const
    for (const [variant, classes] of cases) {
      const { unmount } = render(<Button variant={variant} onPress={() => {}}>按钮</Button>)
      const button = screen.getByRole('button', { name: '按钮' })
      expect(button).toHaveClass(...classes)
      expect(button).toHaveAttribute('type', 'button')
      if (variant === 'text') expect(button).not.toHaveClass('btn')
      unmount()
    }
    render(<Button variant="text" ink onField block icon="plus" onPress={() => {}}>录入医嘱</Button>)
    const text = screen.getByRole('button', { name: '录入医嘱' })
    expect(text).toHaveClass('btn-txt', 'ink', 'on-field', 'btn-blk')
    expect(text.querySelector('svg.ic.ic-s')).not.toBeNull()
  })

  it('marks the small size for the 44 hit area', () => {
    render(<Button variant="quiet" size="sm" onPress={() => {}}>继续遵守</Button>)
    const button = screen.getByRole('button', { name: '继续遵守' })
    expect(button).toHaveClass('btn', 'btn-qt', 'btn-sm')
    expect(button).toHaveAttribute('data-hit44')
  })

  it('does not fire when disabled', async () => {
    const onPress = vi.fn()
    render(<Button variant="primary" isDisabled onPress={onPress}>确认入库</Button>)
    const button = screen.getByRole('button', { name: '确认入库' })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(onPress).not.toHaveBeenCalled()
  })

  it('submits when asked', () => {
    render(<form><Button variant="primary" type="submit" onPress={() => {}}>保存</Button></form>)
    expect(screen.getByRole('button', { name: '保存' })).toHaveAttribute('type', 'submit')
  })

  it('navigates with a button link', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<ButtonLink to="/medical" variant="quiet" size="sm">去医嘱页处理</ButtonLink>} />
          <Route path="/medical" element={<p>医嘱页</p>} />
        </Routes>
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: '去医嘱页处理' })
    expect(link).toHaveClass('btn', 'btn-qt', 'btn-sm')
    expect(link).toHaveAttribute('data-hit44')
    await userEvent.click(link)
    expect(screen.getByText('医嘱页')).toBeInTheDocument()
  })

  it('renders icon buttons with a name, the back stud and the pressed state', async () => {
    const onPress = vi.fn()
    render(
      <>
        <IconButton icon="back" label="返回" back onPress={onPress} />
        <IconButton icon="eye" label="显示密码" pressed={false} />
      </>,
    )
    const back = screen.getByRole('button', { name: '返回' })
    expect(back).toHaveClass('ibtn', 'back')
    await userEvent.click(back)
    expect(onPress).toHaveBeenCalledTimes(1)
    const eye = screen.getByRole('button', { name: '显示密码' })
    expect(eye).toHaveClass('ibtn')
    expect(eye).not.toHaveClass('back')
    expect(eye).toHaveAttribute('aria-pressed', 'false')
    expect(eye.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})
