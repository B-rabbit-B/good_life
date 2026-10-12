import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
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
