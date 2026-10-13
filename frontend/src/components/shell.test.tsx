import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CoverButton } from './CoverButton'
import { CoverProvider } from './cover'
import { Dock } from './Dock'
import { Field } from './Field'
import { JumpCard } from './JumpCard'
import { ShellPortal } from './ShellPortal'
import { ToastProvider, useToast } from './Toast'

function addShellRoot() {
  const shell = document.createElement('div')
  shell.id = 'shell-root'
  document.body.appendChild(shell)
  return shell
}

afterEach(() => {
  document.getElementById('shell-root')?.remove()
  vi.useRealTimers()
})

describe('shell pieces', () => {
  it('renders the shell into the shell root', () => {
    const shell = addShellRoot()
    render(
      <div style={{ overflow: 'hidden' }} data-testid="page">
        <ShellPortal><p>外壳</p></ShellPortal>
        <Dock tall><button type="button">下一步</button></Dock>
      </div>,
    )
    expect(shell).toContainElement(screen.getByText('外壳'))
    const dock = screen.getByRole('button', { name: '下一步' }).parentElement
    expect(shell).toContainElement(dock)
    expect(dock).toHaveClass('stick', 'tall', 'chrome')
    expect(dock).toHaveAttribute('data-tier', 'chrome')
    expect(screen.getByTestId('page')).not.toContainElement(dock)
  })

  it('draws the field once as a static background', () => {
    const { container } = render(<Field />)
    const field = container.querySelector('.field')
    expect(field).toHaveAttribute('aria-hidden', 'true')
  })

  it('shows a toast politely and lets it go', () => {
    function Show() {
      const toast = useToast()
      return <button type="button" onClick={() => toast.show('已清除大致区域')}>清除</button>
    }
    vi.useFakeTimers()
    render(<ToastProvider><Show /></ToastProvider>)
    const region = document.querySelector('[aria-live="polite"]')
    expect(region).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '清除' }))
    const toast = screen.getByText('已清除大致区域')
    expect(region).toContainElement(toast)
    expect(toast).toHaveClass('toast', 'chrome')
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(screen.queryByText('已清除大致区域')).not.toBeInTheDocument()
  })

  it('jumps to another page and does nothing else', async () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<JumpCard to="/medical" label="去医嘱页处理" description="医嘱需要你本人在医嘱页处理。" />} />
          <Route path="/medical" element={<p>医嘱页</p>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('医嘱需要你本人在医嘱页处理。')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: '去医嘱页处理' })
    expect(link).toHaveAttribute('data-hit44')
    await userEvent.click(link)
    expect(screen.getByText('医嘱页')).toBeInTheDocument()
  })

  it('shares the cover state and words with the cover cell', async () => {
    render(<CoverProvider><CoverButton /></CoverProvider>)
    const button = screen.getByRole('button', { name: '遮盖敏感内容' })
    expect(button).toHaveClass('ibtn')
    expect(button).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(button)
    expect(screen.getByRole('button', { name: '已遮盖，点按恢复显示' })).toHaveAttribute('aria-pressed', 'true')
  })
})
