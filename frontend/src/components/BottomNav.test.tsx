import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { BottomNav, type NavItem } from './BottomNav'
import { CoverProvider } from './cover'

const ITEMS: NavItem[] = [
  { key: 'chat', label: '对话', to: '/' },
  { key: 'records', label: '记录', to: '/records' },
  { key: 'health', label: '健康', to: '/health' },
  { key: 'me', label: '我的', to: '/me' },
]

function renderNav(items: NavItem[], path: string, embedded = false) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CoverProvider>
        <BottomNav items={items} embedded={embedded} />
      </CoverProvider>
    </MemoryRouter>,
  )
}

describe('BottomNav', () => {
  it('marks the current item', () => {
    renderNav(ITEMS, '/records/2026-10-12')
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(nav).toHaveClass('rnav', 'chrome')
    expect(nav).toHaveAttribute('data-tier', 'chrome')
    expect(screen.getByRole('link', { name: '记录' })).toHaveAttribute('aria-current', 'page')
    for (const name of ['对话', '健康', '我的']) {
      expect(screen.getByRole('link', { name })).not.toHaveAttribute('aria-current')
    }
    expect(nav.querySelector('.rnav-glaze')).toHaveStyle({ '--at': '1' })
  })

  it('renders three columns without health', () => {
    renderNav(ITEMS.filter((item) => item.key !== 'health'), '/')
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(nav).toHaveStyle({ '--cols': '3' })
    expect(screen.getAllByRole('link')).toHaveLength(3)
    expect(screen.getByRole('link', { name: '对话' })).toHaveAttribute('aria-current', 'page')
  })

  it('toggles the cover cell label and accessible name', async () => {
    renderNav(ITEMS, '/')
    const cell = screen.getByRole('button', { name: '遮盖敏感内容' })
    expect(cell).toHaveTextContent('遮盖')
    expect(cell).toHaveAttribute('aria-pressed', 'false')
    expect(cell.tagName).toBe('BUTTON')
    expect(screen.getAllByRole('link')).toHaveLength(4)
    await userEvent.click(cell)
    const pressed = screen.getByRole('button', { name: '已遮盖，点按恢复显示' })
    expect(pressed).toHaveTextContent('已遮盖')
    expect(pressed).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(pressed)
    expect(screen.getByRole('button', { name: '遮盖敏感内容' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('drops its own material when embedded', () => {
    renderNav(ITEMS, '/', true)
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(nav).toHaveClass('rnav', 'embedded')
    expect(nav).not.toHaveClass('chrome')
    expect(nav).not.toHaveAttribute('data-tier')
  })
})
