import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { MedicalItemOut } from '../../api/types'
import { CoverProvider } from '../../components/cover'
import { GlassModeProvider } from '../../components/glass/GlassModeProvider'
import { ToastProvider } from '../../components/Toast'
import { addMonths, todayISO } from '../../lib/dates'
import { dueItem, END_SOON_REASON, REVIEW_REASON } from '../../test/fixtures/medical'
import { medicalHandlers, type MedicalOptions } from '../../test/msw/handlers/medical'
import { server } from '../../test/msw/server'
import { renderWithProviders } from '../../test/render'
import { ContinueSheet } from './ContinueSheet'

function renderSheet(item: MedicalItemOut, dueReason: string | null, opts: MedicalOptions = {}) {
  const medical = medicalHandlers({ reviews: [item], ...opts })
  server.use(...medical.handlers)
  const onDone = vi.fn()
  function Harness() {
    const [open, setOpen] = useState(true)
    return (
      <GlassModeProvider>
        <CoverProvider>
          <ToastProvider>
            <ContinueSheet item={item} dueReason={dueReason} isOpen={open} onClose={() => setOpen(false)} onDone={onDone} />
          </ToastProvider>
        </CoverProvider>
      </GlassModeProvider>
    )
  }
  renderWithProviders(<Harness />)
  return { medical, onDone }
}

const dialog = () => screen.findByRole('dialog', { name: '继续遵守这条医嘱' })
const row = (label: string) => screen.getByLabelText(label).closest('.dt-row') as HTMLElement
const willTexts = () => Array.from(document.querySelectorAll('.will li')).map((li) => li.textContent)

describe('continue sheet', () => {
  it('shows both dates prefilled with their old values', async () => {
    renderSheet(dueItem({ review_date: '2026-12-01', end_date: '2026-10-13' }), END_SOON_REASON)
    const sheet = await dialog()
    expect(within(sheet).getByText('饮食要求')).toBeInTheDocument()
    expect(within(sheet).getByText('低盐饮食，每日钠不超过 2000 毫克')).toBeInTheDocument()
    expect(within(sheet).getByText('生效 2026-07-12')).toBeInTheDocument()
    // 医嘱原文在敏感区里（默认是医嘱页的 content；对话页按入口传 opening 或 reviewBar）
    expect(within(sheet).getByText('低盐饮食，每日钠不超过 2000 毫克').closest('[data-sensitive-area="content"]')).not.toBeNull()
    expect(within(sheet).getByText('两个日期一起提交，留空的一项会被清除。')).toBeInTheDocument()
    expect(screen.getByLabelText('复查日期')).toHaveValue('2026-12-01')
    expect(screen.getByLabelText('预计结束')).toHaveValue('2026-10-13')
    expect(within(row('复查日期')).getByText('原 2026-12-01')).toBeInTheDocument()
    expect(within(row('预计结束')).getByText('原 2026-10-13')).toBeInTheDocument()
  })

  it('marks the field that triggered the review with the backend reason', async () => {
    renderSheet(dueItem({ end_date: null }), REVIEW_REASON)
    await dialog()
    const review = row('复查日期')
    expect(review).toHaveClass('due')
    expect(within(review).getByText(REVIEW_REASON)).toBeInTheDocument()
    expect(row('预计结束')).not.toHaveClass('due')
    // 复查日期触发的：默认选中“1 个月后”；预计结束原来没设
    expect(screen.getByLabelText('复查日期')).toHaveValue(addMonths(todayISO(), 1))
    expect(within(review).getByRole('button', { name: '1 个月后' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(row('预计结束')).getByText('原 未设')).toBeInTheDocument()
    expect(within(row('预计结束')).getByText('不设（长期）')).toBeInTheDocument()
  })

  it('always submits both dates', async () => {
    const user = userEvent.setup()
    const { medical } = renderSheet(dueItem({ end_date: '2027-01-31' }), REVIEW_REASON)
    const sheet = await dialog()
    await user.click(within(sheet).getByRole('button', { name: '不再设' }))
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    await waitFor(() => expect(medical.continues).toHaveLength(1))
    const body = medical.continues[0]?.body as Record<string, unknown>
    expect(body).toEqual({ review_date: null, end_date: '2027-01-31' })
    expect(Object.keys(body).sort()).toEqual(['end_date', 'review_date'])
  })

  it('updates the consequence list with the choices', async () => {
    const user = userEvent.setup()
    renderSheet(dueItem({ end_date: null }), REVIEW_REASON)
    const sheet = await dialog()
    const oneMonth = addMonths(todayISO(), 1)
    expect(willTexts()).toEqual([
      '状态从‘待复核’回到‘生效中’，建议继续按它约束。',
      `复查日期改为 ${oneMonth}，那天打开应用时会再次提醒复核。`,
      '预计结束保持不设，继续长期有效。',
      '记一条审计：时间、由你本人确认、两个新日期。',
    ])
    await user.click(within(sheet).getByRole('button', { name: '3 个月后' }))
    expect(willTexts()[1]).toBe(`复查日期改为 ${addMonths(todayISO(), 3)}，那天打开应用时会再次提醒复核。`)
    await user.click(within(sheet).getByRole('button', { name: '不再设' }))
    expect(willTexts()[1]).toBe('不再设复查日期。')
    fireEvent.change(screen.getByLabelText('预计结束'), { target: { value: '2027-03-01' } })
    expect(willTexts()[2]).toBe('预计结束改为 2027-03-01，结束前一天起进入待复核。')
  })

  it('shows still_due under the triggering field', async () => {
    const user = userEvent.setup()
    const message = '新的预计结束日期或复查日期仍然已到期，请设置更晚的日期，或者确认解除'
    renderSheet(dueItem({ end_date: '2026-10-13' }), END_SOON_REASON, {
      continueError: { status: 422, code: 'still_due', message },
    })
    const sheet = await dialog()
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent('错误码 still_due')
    // 用户保留了预填的、本身已到期的预计结束：后端的说明写在这一项下面，这一项标红并拿到焦点；前端不自己拦
    expect(alert.closest('.dt-row')).toBe(row('预计结束'))
    const end = screen.getByLabelText('预计结束')
    await waitFor(() => expect(end).toHaveFocus())
    expect(end).toHaveAttribute('aria-invalid', 'true')
    expect(end).toHaveAttribute('aria-describedby', alert.id)
    expect(end.closest('.sel')).toHaveClass('bad')
    expect(screen.getByLabelText('复查日期').closest('.sel')).not.toHaveClass('bad')
    expect(screen.getByRole('dialog', { name: '继续遵守这条医嘱' })).toBeInTheDocument()
  })

  it('continues once on a double press', async () => {
    const user = userEvent.setup({ delay: null })
    const { medical, onDone } = renderSheet(dueItem(), REVIEW_REASON)
    const sheet = await dialog()
    await user.dblClick(within(sheet).getByRole('button', { name: '继续遵守' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(medical.continues).toHaveLength(1)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('moves focus to the title and closes after success', async () => {
    const user = userEvent.setup()
    const { onDone } = renderSheet(dueItem(), REVIEW_REASON)
    const sheet = await dialog()
    const title = within(sheet).getByRole('heading', { name: '继续遵守这条医嘱' })
    await waitFor(() => expect(title).toHaveFocus())
    await user.click(within(sheet).getByRole('button', { name: '继续遵守' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('已继续遵守')).toBeInTheDocument()
  })
})
