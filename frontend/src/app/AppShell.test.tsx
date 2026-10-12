import { screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { setToken } from '../api/token'
import { Dock } from '../components/Dock'
import { Sensitive } from '../components/Sensitive'
import { TEST_TOKEN } from '../test/fixtures/core'
import { renderRoute, renderRouter } from '../test/render'
import { AppShell, useSensitivePage } from './AppShell'
import type { RouteHandle } from './routes'
import { sensitiveAreaMismatch } from './sensitiveAreas'

const shellRoot = () => document.getElementById('shell-root') as HTMLElement
const scroller = () => document.querySelector('main[data-scroller]') as HTMLElement

describe('app shell', () => {
  it('renders the bottom nav into the shell root on tab pages', async () => {
    renderRoute('/records')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(shellRoot()).toContainElement(nav)
    expect(scroller()).not.toContainElement(nav)
    expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['对话', '记录', '健康', '我的'])
    expect(within(nav).getByRole('link', { name: '记录' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('button', { name: '遮盖敏感内容' })).toBeInTheDocument()
    expect(scroller().style.paddingBottom).toBe('104px')
  })

  it('shows the three item nav when health is closed', async () => {
    renderRoute('/me', { capabilities: { cycle: false, medical: false } })
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['对话', '记录', '我的'])
  })

  it('renders no nav on pages without tabs', async () => {
    renderRoute('/me/profile')
    expect(await screen.findByRole('heading', { name: '个人档案' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument()
    expect(scroller().style.paddingBottom).toBe('28px')
  })

  it('leaves the chat nav to the chat page and pads for its dock', async () => {
    renderRoute('/chat')
    expect(await screen.findByRole('heading', { name: '对话' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument()
    expect(scroller().style.paddingBottom).toBe('196px')
  })

  it('removes the boot shell after the first frame', async () => {
    const boot = document.createElement('div')
    boot.id = 'boot-shell'
    document.body.prepend(boot)
    renderRoute('/records')
    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    await waitFor(() => expect(document.getElementById('boot-shell')).toBeNull())
  })

  it('pads the scroller for a dock while it is mounted', async () => {
    setToken(TEST_TOKEN)
    const handle: RouteHandle = { nav: 'none', sensitive: false }
    function DockPage({ tall }: { tall: boolean }) {
      return <Dock tall={tall}><button type="button">下一步</button></Dock>
    }
    const router = createMemoryRouter([{
      element: <AppShell />,
      children: [
        { path: '/short', element: <DockPage tall={false} />, handle },
        { path: '/tall', element: <DockPage tall />, handle },
        { path: '/plain', element: <p>没有操作坞</p>, handle },
      ],
    }], { initialEntries: ['/short'] })
    renderRouter(router)
    expect(await screen.findByRole('button', { name: '下一步' })).toBeInTheDocument()
    expect(scroller().style.paddingBottom).toBe('112px')
    await router.navigate('/tall')
    await waitFor(() => expect(scroller().style.paddingBottom).toBe('172px'))
    await router.navigate('/plain')
    await waitFor(() => expect(scroller().style.paddingBottom).toBe('28px'))
  })

  it('records which sensitive areas a page registered', async () => {
    const handle: RouteHandle = { nav: 'none', sensitive: true }
    function ProfilePage({ extra }: { extra: boolean }) {
      useSensitivePage('profileEdit')
      return (
        <>
          <Sensitive area="profile"><p>身高 162 厘米</p></Sensitive>
          <Sensitive area="switches"><p>经期记录 开</p></Sensitive>
          {extra && <Sensitive><p>没有登记的敏感区</p></Sensitive>}
        </>
      )
    }
    const router = createMemoryRouter([{
      element: <AppShell />,
      children: [
        { path: '/ok', element: <ProfilePage extra={false} />, handle },
        { path: '/extra', element: <ProfilePage extra />, handle },
        { path: '/plain', element: <p>普通页</p>, handle: { ...handle, sensitive: false } },
      ],
    }], { initialEntries: ['/ok'] })
    renderRouter(router)
    expect(await screen.findByText('身高 162 厘米')).toBeInTheDocument()
    expect(scroller()).toHaveAttribute('data-sensitive-page', 'profileEdit')
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'profileEdit', missing: [], unexpected: [] })

    await router.navigate('/extra')
    expect(await screen.findByText('没有登记的敏感区')).toBeInTheDocument()
    expect(sensitiveAreaMismatch(document).unexpected).toEqual(['(未命名)'])

    await router.navigate('/plain')
    await waitFor(() => expect(scroller()).not.toHaveAttribute('data-sensitive-page'))
  })
})
