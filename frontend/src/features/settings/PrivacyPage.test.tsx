import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { formatStamp, todayISO } from '../../lib/dates'
import { AUDITS, GRANTS } from '../../test/fixtures/grants'
import { SAVED_AREA } from '../../test/fixtures/restaurants'
import { grantHandlers, type GrantError } from '../../test/msw/handlers/grants'
import { restaurantHandlers } from '../../test/msw/handlers/restaurants'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderPrivacy({ area = true, revokeErrors }: { area?: boolean; revokeErrors?: GrantError[] } = {}) {
  const restaurants = restaurantHandlers({ settings: { location_consent: 'denied', area: area ? SAVED_AREA : null } })
  const grants = grantHandlers({ revokeErrors })
  server.use(...restaurants.handlers, ...grants.handlers)
  return { ...renderRoute('/settings/privacy'), restaurants, grants }
}

const grantRow = (name: string) => {
  const list = screen.getByRole('list', { name: '外部授权' })
  const item = within(list).getAllByRole('listitem').find((li) => li.querySelector('b')?.textContent === name)
  if (!item) throw new Error(`没有 ${name}`)
  return item
}

beforeAll(async () => {
  await import('./PrivacyPage')
}, 60_000)

describe('privacy page', { timeout: 15_000 }, () => {
  it('explains the cover', async () => {
    renderPrivacy()
    expect(await screen.findByText('打开后医嘱、经期、档案等内容用斜纹盖住；应用切到后台再回来时自动遮盖。')).toBeInTheDocument()
  })

  it('switches the reduce transparency preference', async () => {
    const user = userEvent.setup()
    renderPrivacy()
    const group = await screen.findByRole('radiogroup', { name: '减少透明' })
    expect(within(group).getByRole('radio', { name: '跟随系统' })).toBeChecked()
    expect(screen.getByText('会关掉磨砂玻璃，界面改用实色，更省电。')).toBeInTheDocument()
    await user.click(within(group).getByRole('radio', { name: '开' }))
    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-glass', 'off'))
    await user.click(within(group).getByRole('radio', { name: '关' }))
    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-glass', 'on'))
  })

  it('clears the saved area after confirmation', async () => {
    const user = userEvent.setup()
    const { restaurants } = renderPrivacy()
    const section = (await screen.findByRole('heading', { name: '已保存的大致区域' })).closest('section') as HTMLElement
    expect(await within(section).findByText(SAVED_AREA.name)).toBeInTheDocument()
    expect(within(section).getByText(`保存于 ${todayISO(new Date(SAVED_AREA.saved_at))}`)).toBeInTheDocument()
    await user.click(within(section).getByRole('button', { name: '清除' }))
    const dialog = await screen.findByRole('dialog', { name: '清除大致区域' })
    expect(restaurants.record.clears).toBe(0)
    await user.click(within(dialog).getByRole('button', { name: '清除' }))
    await waitFor(() => expect(restaurants.record.clears).toBe(1))
    expect(await within(section).findByText('没有保存大致区域。')).toBeInTheDocument()
    expect(await screen.findByText('已清除')).toBeInTheDocument()
  })

  it('lists grants and revokes an active one', async () => {
    const user = userEvent.setup()
    const { grants } = renderPrivacy()
    await screen.findByRole('list', { name: '外部授权' })
    const active = grantRow('我的笔记应用')
    expect(active).toHaveTextContent('只读')
    expect(active).toHaveTextContent('有效')
    expect(active).toHaveTextContent(`到期 ${todayISO(new Date('2026-12-31T08:00:00Z'))}`)
    expect(active).toHaveTextContent(`最近使用 ${formatStamp('2026-10-11T12:30:00Z')}`)
    const revoked = grantRow('旧的同步脚本')
    expect(revoked).toHaveTextContent('读写')
    expect(revoked).toHaveTextContent('已吊销')
    expect(revoked).toHaveTextContent('从未使用')
    expect(within(revoked).queryByRole('button', { name: '吊销' })).not.toBeInTheDocument()

    await user.click(within(active).getByRole('button', { name: '吊销' }))
    const dialog = await screen.findByRole('dialog', { name: '吊销这个授权' })
    expect(within(dialog).getByText('我的笔记应用')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '吊销' }))
    await waitFor(() => expect(grants.record.revoked).toEqual([GRANTS[0]?.id]))
    await waitFor(() => expect(grantRow('我的笔记应用')).toHaveTextContent('已吊销'))
    expect(within(grantRow('我的笔记应用')).queryByRole('button', { name: '吊销' })).not.toBeInTheDocument()
  })

  it('shows a revoke error in the sheet and lets the user try again', async () => {
    const user = userEvent.setup()
    const { grants } = renderPrivacy({ revokeErrors: [{ status: 503, code: 'service_unavailable', message: '服务暂时不可用，请稍后再试' }] })
    await screen.findByRole('list', { name: '外部授权' })
    await user.click(within(grantRow('我的笔记应用')).getByRole('button', { name: '吊销' }))
    const dialog = await screen.findByRole('dialog', { name: '吊销这个授权' })
    await user.click(within(dialog).getByRole('button', { name: '吊销' }))
    expect(await within(dialog).findByText('错误码 service_unavailable')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: '取消' })).toBeEnabled()
    await user.click(within(dialog).getByRole('button', { name: '吊销' }))
    await waitFor(() => expect(grants.record.revoked).toHaveLength(2))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('filters the audit list by client name', async () => {
    const user = userEvent.setup()
    const { grants } = renderPrivacy()
    const chips = await screen.findByRole('group', { name: '按客户端筛选' })
    await waitFor(() => expect(within(chips).getAllByRole('button').map((b) => b.textContent)).toEqual(['全部', '应用内助手', 'notes-app']))
    const list = screen.getByRole('list', { name: '调用记录' })
    await waitFor(() => expect(within(list).getAllByRole('listitem')).toHaveLength(AUDITS.length))
    expect(grants.record.auditQueries[0]).toEqual({ limit: '200', client_name: null })
    const failed = within(list).getAllByRole('listitem')[1] as HTMLElement
    expect(failed).toHaveTextContent('notes-app')
    expect(failed).toHaveTextContent('nutrition.daily_summary')
    expect(failed).toHaveTextContent('失败')
    expect(failed).toHaveTextContent('forbidden')
    expect(failed).toHaveTextContent('7 毫秒')
    expect(failed).toHaveTextContent(formatStamp('2026-10-12T08:00:00Z'))

    await user.click(within(chips).getByRole('button', { name: '应用内助手' }))
    expect(within(chips).getByRole('button', { name: '应用内助手' })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(grants.record.auditQueries).toContainEqual({ limit: '50', client_name: 'agent' }))
    await waitFor(() => expect(within(screen.getByRole('list', { name: '调用记录' })).getAllByRole('listitem')).toHaveLength(2))
    for (const item of within(screen.getByRole('list', { name: '调用记录' })).getAllByRole('listitem')) {
      expect(item).toHaveTextContent('应用内助手')
    }
  })

  it('keeps the area, grants and audit in sensitive regions', async () => {
    const { container } = renderPrivacy()
    await screen.findByRole('list', { name: '外部授权' })
    await screen.findByText(SAVED_AREA.name)
    expect(sensitiveAreaMismatch(container)).toEqual({ page: 'privacy', missing: [], unexpected: [] })
  })

  it('shows each failed block with its error code and a retry', async () => {
    const user = userEvent.setup()
    const failure = { error: { code: 'internal_error', message: '服务器内部错误' } }
    renderPrivacy()
    let fail = true
    server.use(
      http.get('/api/restaurants/settings', () => HttpResponse.json(failure, { status: 500 })),
      http.get('/api/agent-grants', () => (fail ? HttpResponse.json(failure, { status: 500 }) : HttpResponse.json([]))),
      http.get('/api/agent-grants/audit', () => HttpResponse.json(failure, { status: 500 })),
    )
    for (const title of ['已保存的大致区域', '外部授权', '调用记录']) {
      const section = (await screen.findByRole('heading', { name: title })).closest('section') as HTMLElement
      const alert = await within(section).findByRole('alert')
      expect(alert, title).toHaveTextContent('服务器内部错误')
      expect(alert, title).toHaveTextContent('错误码 internal_error')
      expect(alert.closest('.plate'), title).not.toBeNull()
      expect(within(alert).getByRole('button', { name: '重试' }), title).toBeInTheDocument()
    }
    fail = false
    const grants = (await screen.findByRole('heading', { name: '外部授权' })).closest('section') as HTMLElement
    await user.click(within(within(grants).getByRole('alert')).getByRole('button', { name: '重试' }))
    expect(await within(grants).findByText('还没有外部授权。')).toBeInTheDocument()
  })

  it('moves focus to the section after revoking the last control in it', async () => {
    const user = userEvent.setup()
    renderPrivacy()
    await screen.findByRole('list', { name: '外部授权' })
    await user.click(within(grantRow('我的笔记应用')).getByRole('button', { name: '吊销' }))
    const dialog = await screen.findByRole('dialog', { name: '吊销这个授权' })
    await user.click(within(dialog).getByRole('button', { name: '吊销' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(screen.getByRole('region', { name: '外部授权' })).toHaveFocus())
  })

  it('moves focus to the section after clearing the saved area', async () => {
    const user = userEvent.setup()
    renderPrivacy()
    const section = (await screen.findByRole('heading', { name: '已保存的大致区域' })).closest('section') as HTMLElement
    await user.click(await within(section).findByRole('button', { name: '清除' }))
    const dialog = await screen.findByRole('dialog', { name: '清除大致区域' })
    await user.click(within(dialog).getByRole('button', { name: '清除' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(section).toHaveFocus())
  })
})
