import { screen, within } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'
import { sensitiveAreaMismatch } from '../../app/sensitiveAreas'
import { formatStamp, todayISO } from '../../lib/dates'
import {
  activeItem, dueItem, EXPIRED_REASON, medicalEvent, order, pendingItem, REVIEW_REASON, resolvedItem, voidedItem,
} from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderRoute } from '../../test/render'

function renderHistory(opts: MedicalOptions) {
  const result = renderRoute('/health/medical?tab=history')
  const medical = medicalHandlers({ orders: [order()], ...opts })
  server.use(...medical.handlers)
  return { ...result, medical }
}

// 页面是按路由按需加载的大块：整套并行跑时第一次加载要好几秒，先在这里加载好，第一次 findBy 不必等它
beforeAll(async () => {
  await import('../health/HealthPage')
}, 60_000)

describe('history tab', { timeout: 15_000 }, () => {
  it('lists closed items dimmed with their closing reason', async () => {
    const resolved = resolvedItem()
    const voided = voidedItem()
    const expired = voidedItem({ id: '00000000-0000-4000-8000-0000000000e3', content: '一周内忌食辛辣', closed_at: '2026-09-01T01:00:00Z' })
    renderHistory({
      items: [activeItem(), expired, resolved, voided],
      userEvents: [
        medicalEvent(resolved, 'resolved', { from_status: 'active', to_status: 'resolved', source: 'user', detail: { reason: null } }),
        medicalEvent(voided, 'voided', { from_status: 'pending_confirmation', to_status: 'voided', source: 'user', detail: { reason: '重复录入' } }),
        medicalEvent(expired, 'expired', { from_status: 'pending_confirmation', to_status: 'voided', source: 'system', detail: { reason: EXPIRED_REASON } }),
      ],
    })
    const heading = await screen.findByRole('heading', { name: '已结束' })
    expect(heading.parentElement).toHaveTextContent('已结束3 条')
    const rows = Array.from(document.querySelectorAll('.closed'))
    expect(rows.map((row) => row.querySelector('.mo-c')?.textContent)).toEqual([resolved.content, voided.content, '一周内忌食辛辣'])

    const first = rows[0] as HTMLElement
    expect(within(first).getByText(`已解除 ${todayISO(new Date(resolved.closed_at ?? ''))}`)).toBeInTheDocument()
    expect(await within(first).findByText('由你本人确认解除')).toBeInTheDocument()
    const second = rows[1] as HTMLElement
    expect(within(second).getByText(`已作废 ${todayISO(new Date(voided.closed_at ?? ''))}`)).toBeInTheDocument()
    expect(within(second).getByText('重复录入，由你本人作废')).toBeInTheDocument()
    expect(within(rows[2] as HTMLElement).getByText(`${EXPIRED_REASON}，由系统（打开应用时检查）自动作废`)).toBeInTheDocument()
    // 已结束的条目只读：没有任何动作
    expect(within(first).queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(activeItem().content)).not.toBeInTheDocument()
    expect(sensitiveAreaMismatch(document)).toEqual({ page: 'medical', missing: [], unexpected: [] })
  })

  it('lists audit events across items from the events api', async () => {
    const due = dueItem()
    const pending = pendingItem()
    renderHistory({
      items: [due, pending],
      userEvents: [
        medicalEvent(due, 'review_due', {
          occurred_at: '2026-10-12T10:40:00Z', from_status: 'active', to_status: 'pending_review', source: 'system',
          detail: { reason: REVIEW_REASON },
        }),
        medicalEvent(pending, 'created', {
          occurred_at: '2026-10-11T13:15:00Z', from_status: null, to_status: 'pending_confirmation', source: 'extractor',
        }),
      ],
    })
    const heading = await screen.findByRole('heading', { name: '审计记录' })
    expect(heading.parentElement).toHaveTextContent('审计记录最近 2 条')
    const lines = await screen.findAllByRole('listitem')
    const audit = lines.filter((line) => line.closest('.audit'))
    expect(audit).toHaveLength(2)
    const [stampDay, stampTime] = formatStamp('2026-10-12T10:40:00Z').split(' ')
    expect(within(audit[0] as HTMLElement).getByText(`${stampDay}`, { exact: false })).toBeInTheDocument()
    expect(audit[0]).toHaveTextContent(`${stampDay}${stampTime}进入待复核 ${due.content}生效中 到 待复核，来源：系统（打开应用时检查，${REVIEW_REASON}）`)
    expect(audit[1]).toHaveTextContent('提取为待核对 服药期间及停药后 7 天内禁止饮酒新建为 待核对，来源：提取')
    expect(stampTime).not.toBe('00:00')
  })
})
