import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CoverProvider, useCover } from './cover'
import { Sensitive } from './Sensitive'

function Harness() {
  const { covered, toggle } = useCover()
  return (
    <>
      <button type="button" onClick={toggle}>{covered ? '恢复' : '遮盖'}</button>
      <Sensitive className="plate">
        <button type="button">里面的按钮</button>
        <span tabIndex={0}>可聚焦的字</span>
      </Sensitive>
      <Sensitive as="section" square aria-label="消息流">消息</Sensitive>
    </>
  )
}

const regions = () => Array.from(document.querySelectorAll('[data-sensitive]'))

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('cover', () => {
  it('covers every sensitive region with aria-hidden and inert', async () => {
    render(<CoverProvider><Harness /></CoverProvider>)
    expect(regions()).toHaveLength(2)
    for (const el of regions()) {
      expect(el).toHaveClass('sens')
      expect(el).not.toHaveAttribute('aria-hidden')
      expect(el).not.toHaveAttribute('inert')
    }
    await userEvent.click(screen.getByRole('button', { name: '遮盖' }))
    for (const el of regions()) {
      expect(el).toHaveAttribute('aria-hidden', 'true')
      expect(el).toHaveAttribute('inert')
      expect(el).toHaveAttribute('data-covered')
    }
    await userEvent.click(screen.getByRole('button', { name: '恢复' }))
    for (const el of regions()) {
      expect(el).not.toHaveAttribute('aria-hidden')
      expect(el).not.toHaveAttribute('inert')
    }
  })

  it('announces covered and restored', async () => {
    render(<CoverProvider><Harness /></CoverProvider>)
    const live = screen.getByRole('status')
    expect(live).toHaveAttribute('aria-live', 'polite')
    expect(live).toHaveTextContent('')
    await userEvent.click(screen.getByRole('button', { name: '遮盖' }))
    expect(live).toHaveTextContent('已遮盖')
    await userEvent.click(screen.getByRole('button', { name: '恢复' }))
    expect(live).toHaveTextContent('已恢复显示')
  })

  it('falls back to tabindex when inert is unsupported and restores the original values', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'inert')
    delete (HTMLElement.prototype as { inert?: boolean }).inert
    try {
      expect('inert' in HTMLElement.prototype).toBe(false)
      render(<CoverProvider><Harness /></CoverProvider>)
      const inner = screen.getByRole('button', { name: '里面的按钮' })
      const text = screen.getByText('可聚焦的字')
      await userEvent.click(screen.getByRole('button', { name: '遮盖' }))
      expect(inner).toHaveAttribute('tabindex', '-1')
      expect(text).toHaveAttribute('tabindex', '-1')
      await userEvent.click(screen.getByRole('button', { name: '恢复' }))
      expect(inner).not.toHaveAttribute('tabindex')
      expect(text).toHaveAttribute('tabindex', '0')
      expect(inner).not.toHaveAttribute('data-ti')
      expect(text).not.toHaveAttribute('data-ti')
    } finally {
      if (descriptor) Object.defineProperty(HTMLElement.prototype, 'inert', descriptor)
    }
  })

  it('covers when the page becomes hidden', () => {
    render(<CoverProvider><Harness /></CoverProvider>)
    try {
      act(() => setVisibility('hidden'))
      for (const el of regions()) expect(el).toHaveAttribute('aria-hidden', 'true')
      act(() => setVisibility('visible'))
      // 回到前台时保持遮盖，等用户自己恢复
      for (const el of regions()) expect(el).toHaveAttribute('aria-hidden', 'true')
    } finally {
      setVisibility('visible')
    }
  })

  it('uses square corners when asked', () => {
    render(<CoverProvider><Harness /></CoverProvider>)
    const [plate, stream] = regions()
    expect(plate).toHaveClass('plate', 'sens')
    expect(plate).not.toHaveClass('sens-sq')
    expect(stream).toHaveClass('sens', 'sens-sq')
    expect(stream?.tagName).toBe('SECTION')
  })
})
