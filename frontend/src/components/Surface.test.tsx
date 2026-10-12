import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Surface } from './Surface'

describe('Surface', () => {
  it('renders the tier class and data-tier', () => {
    for (const tier of ['plate', 'still', 'chrome', 'sheet'] as const) {
      const { unmount } = render(<Surface tier={tier} className="extra">{tier}</Surface>)
      const el = screen.getByText(tier)
      expect(el).toHaveClass(tier, 'extra')
      expect(el).toHaveAttribute('data-tier', tier)
      expect(el.tagName).toBe('DIV')
      unmount()
    }
  })

  it('renders as the given element', () => {
    render(<Surface tier="chrome" as="nav" aria-label="主导航">导航</Surface>)
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(nav).toHaveClass('chrome')
    expect(nav).toHaveTextContent('导航')
  })
})
