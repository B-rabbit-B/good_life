import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { activeItem, dueItem, order, pendingItem, proposalItem } from '../../test/fixtures/medical'
import { consentHandlers } from '../../test/msw/handlers/consents'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderHealth(path: string, opts: MedicalOptions = {}, route: Parameters<typeof renderRoute>[1] = {}) {
  const result = renderRoute(path, route)
  const medical = medicalHandlers({ orders: [order()], ...opts })
  server.use(...medical.handlers)
  return { ...result, medical }
}

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('./HealthPage')
}, 60_000)

describe('health page', { timeout: 15_000 }, () => {
  it('shows cycle and medical segments for a female user', async () => {
    const user = userEvent.setup()
    const { router } = renderHealth('/health/medical', { items: [activeItem()] })
    expect(await screen.findByRole('heading', { name: '健康' })).toBeInTheDocument()
    const segments = await screen.findByRole('tablist', { name: '健康分段' })
    expect(within(segments).getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['经期', '医嘱'])
    expect(within(segments).getByRole('tab', { name: /^医嘱/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tablist', { name: '医嘱分类' })).toBeInTheDocument()
    await user.click(within(segments).getByRole('tab', { name: '经期' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/health/cycle'))
    expect(await screen.findByRole('tablist', { name: '健康分段' })).toBeInTheDocument()
    expect(screen.queryByRole('tablist', { name: '医嘱分类' })).not.toBeInTheDocument()
  })

  it('shows only medical tabs without the cycle module', async () => {
    renderHealth('/health', { items: [activeItem()] }, {
      profile: { gender: 'male' }, capabilities: { cycle: false, medical: true },
    })
    const tabs = await screen.findByRole('tablist', { name: '医嘱分类' })
    await within(tabs).findByRole('tab', { name: '生效中 1' })
    expect(within(tabs).getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['待核对', '生效中 1', '历史与审计'])
    expect(screen.queryByRole('tablist', { name: '健康分段' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('经期')
  })

  it('badges the medical segment with the review count', async () => {
    renderHealth('/health/medical?tab=pending', { items: [dueItem(), proposalItem(), activeItem(), pendingItem()] })
    const segments = await screen.findByRole('tablist', { name: '健康分段' })
    const medical = within(segments).getByRole('tab', { name: /^医嘱/ })
    await waitFor(() => expect(medical.querySelector('.cnt')).toHaveTextContent('2'))
    const tabs = screen.getByRole('tablist', { name: '医嘱分类' })
    await waitFor(() => expect(within(tabs).getByRole('tab', { name: /^待核对/ }).querySelector('.cnt')).toHaveTextContent('1'))
    expect(within(tabs).getByRole('tab', { name: /^待核对/ })).toHaveAttribute('aria-selected', 'true')
    expect(within(tabs).getByRole('tab', { name: /^生效中/ })).toHaveTextContent('生效中 3')
  })

  it('refreshes the medical queries from the header', async () => {
    const user = userEvent.setup()
    const { medical } = renderHealth('/health/medical', { items: [activeItem()] })
    await screen.findByText(activeItem().content, { selector: '.mo-c' })
    medical.items().push(activeItem({ id: '00000000-0000-4000-8000-0000000000d7', content: '新的一条' }))
    await user.click(screen.getByRole('button', { name: '刷新' }))
    expect(await screen.findByText('新的一条', { selector: '.mo-c' })).toBeInTheDocument()
  })

  it('shows the consent panel before the cycle view', async () => {
    const user = userEvent.setup()
    renderHealth('/health/cycle')
    const consents = consentHandlers({ granted: { cycle: false } })
    server.use(...consents.handlers)
    expect(await screen.findByRole('heading', { name: '单独同意：经期记录' })).toBeInTheDocument()
    // 分段仍在（可以去医嘱），经期内容不出现
    expect(screen.getByRole('tablist', { name: '健康分段' })).toBeInTheDocument()
    expect(document.querySelector('[data-sensitive-area="content"]')).toBeNull()
    await user.click(screen.getByRole('checkbox', { name: '我已阅读并同意' }))
    await user.click(screen.getByRole('button', { name: '同意并开始使用' }))
    await waitFor(() => expect(document.querySelector('[data-sensitive-area="content"]')).not.toBeNull())
    expect(screen.queryByRole('heading', { name: '单独同意：经期记录' })).not.toBeInTheDocument()
    expect(consents.record.grants.map((g) => g.kind)).toEqual(['cycle'])
  })

  it('shows the consent panel before the medical tabs', async () => {
    renderHealth('/health/medical?tab=pending', { items: [dueItem(), pendingItem()] })
    server.use(...consentHandlers({ granted: { medical: false } }).handlers)
    expect(await screen.findByRole('heading', { name: '单独同意：医嘱' })).toBeInTheDocument()
    expect(screen.queryByRole('tablist', { name: '医嘱分类' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /录入医嘱/ })).not.toBeInTheDocument()
    // 医嘱段没有待处理徽标（未同意时不请求待处理列表）
    const segments = screen.getByRole('tablist', { name: '健康分段' })
    expect(within(segments).getByRole('tab', { name: /^医嘱/ }).querySelector('.cnt')).toBeNull()
  })
})
