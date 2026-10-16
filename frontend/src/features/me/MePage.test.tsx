import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, onTestFinished } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { getToken } from '../../api/token'
import { completeProfile } from '../../test/fixtures/core'
import { agentSettings, chatAssignment, provider } from '../../test/fixtures/profile'
import { agentHandlers } from '../../test/msw/handlers/agent'
import { consentHandlers } from '../../test/msw/handlers/consents'
import { profileStore } from '../../test/msw/handlers/auth'
import { llmHandlers } from '../../test/msw/handlers/llm'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

const navLabels = async () =>
  within(await screen.findByRole('navigation', { name: '主导航' })).getAllByRole('link').map((link) => link.textContent)

describe('me page', () => {
  it('shows profile facts inside a sensitive region', async () => {
    renderRoute('/me', { profile: { food_avoidances: ['动物内脏', '酒精'], health_conditions: '膝关节半月板术后', weight_kg: 56.5 } })
    expect(await screen.findByRole('heading', { level: 1, name: '我的' })).toBeInTheDocument()
    expect(await screen.findByText('tester')).toBeInTheDocument()
    expect(screen.getByText('注册于 2026-10-01')).toBeInTheDocument()

    const profile = document.querySelector('[data-sensitive-area="profile"]') as HTMLElement
    for (const text of ['1996', '女', '轻度', '162', '56.5', '减脂', '动物内脏、酒精', '膝关节半月板术后']) {
      expect(within(profile).getByText(text)).toBeInTheDocument()
    }
    expect(within(profile).getByText('1996')).toHaveClass('ns')
    const switches = document.querySelector('[data-sensitive-area="switches"]') as HTMLElement
    expect(within(switches).getByRole('switch', { name: /打开应用时主动提问/ })).toBeInTheDocument()
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'me', missing: [], unexpected: [] })
    expect(screen.getByRole('link', { name: /修改档案/ })).toHaveAttribute('href', '/me/profile')
    expect(screen.getByRole('link', { name: /隐私与数据/ })).toHaveTextContent('含“减少透明”')
    expect(await screen.findByRole('link', { name: /免责声明/ })).toHaveTextContent('已确认 test-v1 版')
  })

  it('toggles openings through the agent settings api', async () => {
    const user = userEvent.setup()
    renderRoute('/me')
    const sent: unknown[] = []
    // server.use 里排在前面的先匹配：记录请求体的 PUT 放在默认设置之前
    server.use(
      http.put('/api/agent/settings', async ({ request }) => {
        const body = (await request.json()) as { openings_enabled: boolean }
        sent.push(body)
        return HttpResponse.json(body)
      }),
      ...agentHandlers(agentSettings({ openings_enabled: true })),
    )
    const toggle = await screen.findByRole('switch', { name: /打开应用时主动提问/ })
    expect(toggle).toBeChecked()
    await user.click(toggle)
    await waitFor(() => expect(sent).toEqual([{ openings_enabled: false }]))
    await waitFor(() => expect(screen.getByRole('switch', { name: /打开应用时主动提问/ })).not.toBeChecked())
  })

  it('shows the cycle switch only for female users and updates capabilities', async () => {
    const user = userEvent.setup()
    const female = renderRoute('/me', { capabilities: { medical: false } })
    const store = profileStore(completeProfile(), { medical: false })
    server.use(...store.handlers)
    expect(await navLabels()).toEqual(['对话', '记录', '健康', '我的'])
    const cycle = await screen.findByRole('switch', { name: /经期记录/ })
    expect(cycle).toBeChecked()
    expect(cycle.closest('[data-sensitive-area="switches"]')).not.toBeNull()

    await user.click(cycle)
    await waitFor(() => expect(store.patches).toEqual([{ cycle_tracking_opt_out: true }]))
    // 后端关掉了经期（这里医嘱也不开放），导航随能力清单变成三项
    await waitFor(async () => expect(await navLabels()).toEqual(['对话', '记录', '我的']))
    expect(screen.getByRole('switch', { name: /经期记录/ })).not.toBeChecked()
    female.unmount()

    renderRoute('/me', { profile: { gender: 'male' }, capabilities: { cycle: false } })
    expect(await screen.findByRole('switch', { name: /打开应用时主动提问/ })).toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: /经期记录/ })).not.toBeInTheDocument()
  })

  it('summarises model services from providers and assignments', async () => {
    const first = renderRoute('/me')
    server.use(...llmHandlers({
      providers: [provider(), provider({ id: '00000000-0000-4000-8000-0000000000a2', name: '第二个' })],
      assignments: [chatAssignment()],
    }).handlers)
    expect(await screen.findByText('2 个，对话已设置')).toBeInTheDocument()
    first.unmount()

    const second = renderRoute('/me')
    server.use(...llmHandlers({ providers: [provider()], assignments: [] }).handlers)
    expect(await screen.findByText('1 个，对话未设置')).toBeInTheDocument()
    second.unmount()

    renderRoute('/me')
    server.use(...llmHandlers().handlers)
    expect(await screen.findByText('未设置')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /模型服务/ })).toHaveAttribute('href', '/settings/models')
  })

  it('logs out and returns to login', async () => {
    const user = userEvent.setup()
    const { router, queryClient } = renderRoute('/me')
    let withoutToken = 0
    const count = ({ request }: { request: Request }) => {
      if (!request.headers.get('Authorization')) withoutToken += 1
    }
    server.events.on('request:start', count)
    onTestFinished(() => server.events.removeListener('request:start', count))
    await user.click(await screen.findByRole('button', { name: '退出登录' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(getToken()).toBeNull()
    expect(await screen.findByRole('heading', { level: 1, name: '登录' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '登录已过期' })).not.toBeInTheDocument()
    // 页面卸载后才清缓存：还挂着的“我的”页不会不带令牌重新请求
    await waitFor(() => expect(queryClient.getQueryCache().getAll()).toHaveLength(0))
    expect(withoutToken).toBe(0)
  })

  it('clears the cache when the user leaves before logout finishes', async () => {
    const user = userEvent.setup()
    const { router, queryClient } = renderRoute('/me')
    server.use(http.post('/api/auth/logout', async () => {
      await new Promise((resolve) => setTimeout(resolve, 300))
      return new HttpResponse(null, { status: 204 })
    }))
    await user.click(await screen.findByRole('button', { name: '退出登录' }))
    // 退出请求还没回来，用户已经去了别的页（“我的”先卸载）
    await act(async () => {
      await router.navigate('/records')
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'), { timeout: 3000 })
    expect(getToken()).toBeNull()
    await waitFor(() => expect(queryClient.getQueryCache().getAll()).toHaveLength(0))
  })

  it('lists both consents with their dates', async () => {
    renderRoute('/me')
    server.use(...consentHandlers({ granted: { cycle: true, medical: false } }).handlers)
    const list = await screen.findByRole('list', { name: '单独同意' })
    expect(screen.getByRole('heading', { name: '单独同意' })).toHaveClass('sec-l')
    const rows = within(list).getAllByRole('listitem')
    expect(rows.map((row) => row.querySelector('b')?.textContent)).toEqual(['经期记录', '医嘱'])
    expect(rows[0]).toHaveTextContent('已同意（2026-10-02）')
    expect(within(rows[0] as HTMLElement).getByRole('button', { name: '撤回' })).toBeInTheDocument()
    expect(rows[1]).toHaveTextContent('未同意')
    expect(within(rows[1] as HTMLElement).queryByRole('button', { name: '撤回' })).not.toBeInTheDocument()
  })

  it('withdraws only after the acknowledgement and offers to keep using', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderRoute('/me')
    const consents = consentHandlers()
    server.use(...consents.handlers)
    const list = await screen.findByRole('list', { name: '单独同意' })
    const medicalRow = () => within(list).getAllByRole('listitem')[1] as HTMLElement
    await waitFor(() => expect(medicalRow()).toHaveTextContent('已同意（2026-10-03）'))
    queryClient.setQueryData(['medical', 'reviews'], [])
    queryClient.setQueryData(['medical', 'constraints', 'exercise_limit'], { constraints: [] })
    queryClient.setQueryData(['fitness', 'workouts', '2026-10-08', '2026-10-14'], [])
    queryClient.setQueryData(['agent', 'opening'], { opening: { id: 'o1', kind: 'review_due', question: '医嘱“忌食辛辣”要不要现在看看？' } })

    // 继续使用：只关闭面板，不撤回
    await user.click(within(medicalRow()).getByRole('button', { name: '撤回' }))
    let sheet = await screen.findByRole('dialog', { name: '撤回医嘱的单独同意' })
    const confirm = within(sheet).getByRole('button', { name: '撤回并清除医嘱数据' })
    expect(confirm).toBeDisabled()
    // 开场问候不随撤回删除：指向“隐私与数据”页的清空对话历史
    expect(within(sheet).getByText('开场问候记录里可能含相关内容，撤回时同样不会自动删除，可在“隐私与数据”页清空对话历史时一并清掉。'))
      .toBeInTheDocument()
    await user.click(within(sheet).getByRole('button', { name: '继续使用' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(consents.record.withdrawn).toEqual([])

    await user.click(within(medicalRow()).getByRole('button', { name: '撤回' }))
    sheet = await screen.findByRole('dialog', { name: '撤回医嘱的单独同意' })
    await user.click(within(sheet).getByRole('button', { name: '撤回并清除医嘱数据' }))
    expect(consents.record.withdrawn).toEqual([])
    await user.click(within(sheet).getByRole('checkbox', { name: '我知道清除后不能恢复' }))
    await user.click(within(sheet).getByRole('button', { name: '撤回并清除医嘱数据' }))
    await waitFor(() => expect(consents.record.withdrawn).toEqual(['medical']))
    await waitFor(() => expect(medicalRow()).toHaveTextContent('未同意'))
    expect(within(medicalRow()).queryByRole('button', { name: '撤回' })).not.toBeInTheDocument()
    expect(within(list).getAllByRole('listitem')[0]).toHaveTextContent('已同意（2026-10-02）')
    // 医嘱的缓存随撤回清掉，不再显示旧的待处理条目；运动限制、训练冲突丢掉，开场问候（可能带医嘱原文）改成没有开场（不丢掉，免得对话页重新请求、后端再生成一张卡片）
    expect(queryClient.getQueryData(['medical', 'reviews'])).toBeUndefined()
    expect(queryClient.getQueryData(['medical', 'constraints', 'exercise_limit'])).toBeUndefined()
    expect(queryClient.getQueryData(['fitness', 'workouts', '2026-10-08', '2026-10-14'])).toBeUndefined()
    expect(queryClient.getQueryData(['agent', 'opening'])).toEqual({ opening: null })
  })

  it('covers the consent rows but not their heading', async () => {
    const user = userEvent.setup()
    renderRoute('/me')
    const list = await screen.findByRole('list', { name: '单独同意' })
    const area = list.closest('[data-sensitive-area="consents"]') as HTMLElement
    expect(area).not.toBeNull()
    expect(screen.getByRole('heading', { name: '单独同意' }).closest('[data-sensitive]')).toBeNull()
    await waitFor(() => expect(sensitiveAreaMismatch(document)).toEqual({ page: 'me', missing: [], unexpected: [] }))
    await user.click(screen.getByRole('button', { name: '遮盖敏感内容' }))
    expect(area).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('list', { name: '单独同意' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '撤回' })).not.toBeInTheDocument()
  })

  it('hides a consent row only when the module is closed and was never granted', async () => {
    const first = renderRoute('/me', { profile: { gender: 'male' }, capabilities: { cycle: false } })
    server.use(...consentHandlers({ granted: { cycle: false, medical: true } }).handlers)
    const list = await screen.findByRole('list', { name: '单独同意' })
    await waitFor(() => expect(within(list).getAllByRole('listitem').map((row) => row.querySelector('b')?.textContent))
      .toEqual(['医嘱']))
    first.unmount()

    // 关了经期记录开关、但以前同意过：这一行留着，才能撤回
    renderRoute('/me', { profile: { cycle_tracking_opt_out: true }, capabilities: { cycle: false } })
    server.use(...consentHandlers().handlers)
    const again = await screen.findByRole('list', { name: '单独同意' })
    await waitFor(() => expect(within(again).getAllByRole('listitem')).toHaveLength(2))
    expect(within(within(again).getAllByRole('listitem')[0] as HTMLElement).getByRole('button', { name: '撤回' }))
      .toBeInTheDocument()
  })
})
