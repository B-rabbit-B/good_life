import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CoverProvider } from './cover'
import { PageHeader } from './PageHeader'

type Callback = (entries: Pick<IntersectionObserverEntry, 'isIntersecting'>[]) => void
const OriginalObserver = window.IntersectionObserver

function controllableObserver() {
  const callbacks: Callback[] = []
  class Observer {
    constructor(callback: Callback) {
      callbacks.push(callback)
    }
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return []
    }
  }
  window.IntersectionObserver = Observer as unknown as typeof IntersectionObserver
  return (isIntersecting: boolean) => act(() => callbacks.forEach((cb) => cb([{ isIntersecting }])))
}

function renderHeader(ui: ReactNode, path = '/sub') {
  return render(
    <MemoryRouter initialEntries={['/', path]} initialIndex={1}>
      <CoverProvider>
        <Routes>
          <Route path="/" element={<p>首页</p>} />
          <Route path="/sub" element={ui} />
        </Routes>
      </CoverProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  window.IntersectionObserver = OriginalObserver
})

describe('PageHeader', () => {
  it('adds stuck when the sentinel leaves', () => {
    const intersect = controllableObserver()
    renderHeader(<PageHeader titleKey="chat" variant="chat" caption="10月12日 周一" />)
    const header = screen.getByRole('banner')
    expect(header).toHaveClass('top')
    expect(header).not.toHaveClass('stuck')
    expect(screen.getByRole('heading', { name: '对话', level: 1 })).toHaveClass('t-title')
    expect(screen.getByText('10月12日 周一')).toHaveClass('t-cap')
    intersect(false)
    expect(header).toHaveClass('stuck')
    intersect(true)
    expect(header).not.toHaveClass('stuck')
  })

  it('puts the cover button at the top right when asked', async () => {
    renderHeader(<PageHeader titleKey="photoResult" variant="sub" back cover />)
    const cover = screen.getByRole('button', { name: '遮盖敏感内容' })
    expect(cover.closest('.hdr-r')).not.toBeNull()
    await userEvent.click(cover)
    expect(screen.getByRole('button', { name: '已遮盖，点按恢复显示' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('已遮盖，再点右上角恢复显示。')).toHaveClass('cover-note')
  })

  it('has a back key with a 44 hit area', async () => {
    renderHeader(<PageHeader titleKey="photoResult" variant="sub" back />)
    const back = screen.getByRole('button', { name: '返回' })
    expect(back).toHaveClass('ibtn', 'back')
    expect(screen.getByRole('heading', { name: '识别结果' })).toHaveClass('t-title')
    await userEvent.click(back)
    expect(screen.getByText('首页')).toBeInTheDocument()
  })

  it('goes to the given path and offers refresh instead of pull to refresh', async () => {
    const onRefresh = vi.fn()
    renderHeader(<PageHeader titleKey="records" variant="big" back="/" onRefresh={onRefresh} />)
    expect(screen.getByRole('heading', { name: '记录' })).toHaveClass('t-display')
    await userEvent.click(screen.getByRole('button', { name: '刷新' }))
    expect(onRefresh).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: '返回' }))
    expect(screen.getByText('首页')).toBeInTheDocument()
  })
})
