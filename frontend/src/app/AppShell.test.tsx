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
    // 只读的免责声明页：没有导航也没有操作坞（修改档案页现在有操作坞，留白是 112）
    renderRoute('/settings/disclaimer')
    expect(await screen.findByRole('heading', { name: '免责声明' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument()
    expect(scroller().style.paddingBottom).toBe('28px')
  })

  it('leaves the chat nav to the chat page and pads for its dock', async () => {
    renderRoute('/chat')
    expect(await screen.findByRole('heading', { name: '对话' })).toBeInTheDocument()
    // 唯一的导航是对话页自己嵌在底座里的那一个，外壳没有再画一个
    const navs = await screen.findAllByRole('navigation', { name: '主导航' })
    expect(navs).toHaveLength(1)
    expect(navs[0]).toHaveClass('embedded')
    expect(navs[0]?.closest('.slab')).not.toBeNull()
    // 留白跟着底座的实际高度（--dock-h，由底座量出写在根节点上），量到之前按 158 + 38 = 196
    expect(scroller().style.paddingBottom).toBe('calc(var(--dock-h, 158px) + 38px)')
    expect(document.documentElement.style.getPropertyValue('--dock-h')).toMatch(/^\d+px$/)
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
      useSensitivePage('me')
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
    expect(scroller()).toHaveAttribute('data-sensitive-page', 'me')
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'me', missing: [], unexpected: [] })

    await router.navigate('/extra')
    expect(await screen.findByText('没有登记的敏感区')).toBeInTheDocument()
    expect(sensitiveAreaMismatch(document).unexpected).toEqual(['(未命名)'])

    await router.navigate('/plain')
    await waitFor(() => expect(scroller()).not.toHaveAttribute('data-sensitive-page'))
  })

  it('puts the cover button in the header of registered pages without a nav', async () => {
    const first = renderRoute('/me/profile')
    expect(await screen.findByRole('heading', { name: '个人档案' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '遮盖敏感内容' })).toBeInTheDocument()
    first.unmount()

    // 不在登记表里的二级页没有遮盖按钮
    const second = renderRoute('/settings/models')
    expect(await screen.findByRole('heading', { name: '模型服务' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '遮盖敏感内容' })).not.toBeInTheDocument()
    second.unmount()

    // 有底部导航的页面：遮盖在导航里，页头不再放
    renderRoute('/me')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(screen.getAllByRole('button', { name: '遮盖敏感内容' })).toEqual([within(nav).getByRole('button', { name: '遮盖敏感内容' })])
  })
})

