import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'
import { Sheet } from './Sheet'
import { ToastProvider, useToast } from './Toast'

function Harness() {
  const [open, setOpen] = useState(false)
  const toast = useToast()
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>打开面板</button>
      <button type="button" onClick={() => toast.show('已保存')}>提示</button>
      <Sheet
        isOpen={open}
        onClose={() => setOpen(false)}
        titleKey="continueSheet"
        footer={<Button variant="quiet" block onPress={() => setOpen(false)}>取消</Button>}
      >
        <p>两个日期一起提交。</p>
      </Sheet>
    </>
  )
}

const renderHarness = () => render(<ToastProvider><Harness /></ToastProvider>)

describe('Sheet', () => {
  it('moves focus to the title and back to the trigger', async () => {
    renderHarness()
    const trigger = screen.getByRole('button', { name: '打开面板' })
    await userEvent.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '继续遵守这条医嘱' })
    expect(dialog).toHaveClass('sheet')
    expect(dialog).toHaveAttribute('data-tier', 'sheet')
    expect(screen.getByRole('heading', { name: '继续遵守这条医嘱' })).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // React Aria 在下一帧把焦点还给触发处
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('stays solid while taller than forty percent of the viewport', async () => {
    // jsdom 不排版：假的 ResizeObserver 一观察就回调，面板高度由测试给
    let height = 500
    const observers: (() => void)[] = []
    vi.stubGlobal('ResizeObserver', class {
      constructor(private readonly callback: () => void) {}
      observe() {
        observers.push(this.callback)
        this.callback()
      }
      disconnect() {}
      unobserve() {}
    })
    const offset = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => height)
    try {
      renderHarness()
      await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
      const dialog = await screen.findByRole('dialog')
      // 视口 768 高（jsdom 默认）：500 超过 40%，一直是实色
      expect(dialog).toHaveAttribute('data-solid', '')
      height = 300
      act(() => observers.forEach((callback) => callback()))
      expect(dialog).not.toHaveAttribute('data-solid')
    } finally {
      offset.mockRestore()
      vi.unstubAllGlobals()
    }
  })

  it('measures again when the viewport resizes', async () => {
    vi.stubGlobal('ResizeObserver', class {
      constructor(private readonly callback: () => void) {}
      observe() {
        this.callback()
      }
      disconnect() {}
      unobserve() {}
    })
    const offset = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => 300)
    const viewport = window.innerHeight
    try {
      renderHarness()
      await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
      const dialog = await screen.findByRole('dialog')
      expect(dialog).not.toHaveAttribute('data-solid')
      // 横屏或软键盘：视口变矮到 600，300 超过 40%
      window.innerHeight = 600
      act(() => {
        window.dispatchEvent(new Event('resize'))
      })
      expect(dialog).toHaveAttribute('data-solid', '')
    } finally {
      window.innerHeight = viewport
      offset.mockRestore()
      vi.unstubAllGlobals()
    }
  })

  it('closes on escape', async () => {
    renderHarness()
    await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
    await screen.findByRole('dialog')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('has no drag handle', async () => {
    renderHarness()
    await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog.querySelector('[class*="handle"], [class*="grab"], [data-drag]')).toBeNull()
    // 只能用按钮或 Esc 关闭：除了内容里的按钮，没有别的可交互件
    expect(Array.from(dialog.querySelectorAll('button')).map((b) => b.textContent)).toEqual(['取消'])
  })

  it('is solid while entering', async () => {
    renderHarness()
    await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAttribute('data-entering')
    fireEvent.transitionEnd(dialog)
    expect(dialog).not.toHaveAttribute('data-entering')
  })

  it('keeps the root marked until the exit animation ends', async () => {
    // jsdom 没有 Web Animations：给退出中的遮罩层（data-exiting）造一个进行中的动画，由测试决定何时结束
    let finish: () => void = () => {}
    const finished = new Promise<void>((resolve) => { finish = resolve })
    const exiting = { playState: 'running', finished }
    const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'getAnimations')
    Object.defineProperty(HTMLElement.prototype, 'getAnimations', {
      configurable: true,
      value(this: HTMLElement) {
        return this.hasAttribute('data-exiting') ? [exiting] : []
      },
    })
    vi.stubGlobal('CSSTransition', class {})
    try {
      renderHarness()
      await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
      await screen.findByRole('dialog')
      expect(document.documentElement).toHaveAttribute('data-sheet-open')
      await userEvent.keyboard('{Escape}')
      await waitFor(() => expect(document.querySelector('.sheet-layer')).toHaveAttribute('data-exiting'))
      // 退出动画进行中：面板还在，外壳仍不模糊，轻提示也不显示
      expect(screen.getByRole('dialog', { hidden: true })).toBeInTheDocument()
      expect(document.documentElement).toHaveAttribute('data-sheet-open')
      await userEvent.click(screen.getByRole('button', { name: '提示', hidden: true }))
      expect(screen.queryByText('已保存')).not.toBeInTheDocument()
      finish()
      await waitFor(() => expect(screen.queryByRole('dialog', { hidden: true })).not.toBeInTheDocument())
      expect(document.documentElement).not.toHaveAttribute('data-sheet-open')
      expect(screen.getByText('已保存')).toBeInTheDocument()
    } finally {
      if (original) Object.defineProperty(HTMLElement.prototype, 'getAnimations', original)
      else delete (HTMLElement.prototype as unknown as Record<string, unknown>).getAnimations
      vi.unstubAllGlobals()
    }
  })

  it('hides toasts while open', async () => {
    renderHarness()
    await userEvent.click(screen.getByRole('button', { name: '提示' }))
    expect(screen.getByText('已保存')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '打开面板' }))
    await screen.findByRole('dialog')
    expect(screen.queryByText('已保存')).not.toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('data-sheet-open')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(document.documentElement).not.toHaveAttribute('data-sheet-open'))
  })
})
